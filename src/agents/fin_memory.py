"""
fin_memory agent: memorize Finnhub master data into Neo4j for financial explainability.

Usage (from repo root):
    python src/agents/fin_memory.py memorize              # All 60 tickers
    python src/agents/fin_memory.py memorize --ticker JPM  # Single ticker
    python src/agents/fin_memory.py stats                  # Graph node/relationship counts
    python src/agents/fin_memory.py query "MATCH (s:Stock) RETURN s.ticker LIMIT 5"
"""

import argparse
import json
import sys
from pathlib import Path

import yaml
from neo4j import GraphDatabase

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FH_BASE = REPO_ROOT / "data" / "raw" / "finnhub_stocks"
NEO4J_CONFIG = REPO_ROOT / "config" / "neo4j.yaml"


def load_neo4j_config():
    if not NEO4J_CONFIG.exists():
        raise FileNotFoundError(f"Config not found: {NEO4J_CONFIG}")
    cfg = yaml.safe_load(NEO4J_CONFIG.read_text())
    return {
        "uri": cfg.get("uri", "bolt://localhost:7687"),
        "user": cfg.get("user", "neo4j"),
        "password": cfg.get("password", "dsc288graph"),
        "database": cfg.get("database", "neo4j"),
    }


def get_driver():
    config = load_neo4j_config()
    return GraphDatabase.driver(
        config["uri"],
        auth=(config["user"], config["password"]),
    )


def ensure_constraints(session):
    for cypher in [
        "CREATE CONSTRAINT stock_ticker IF NOT EXISTS FOR (s:Stock) REQUIRE s.ticker IS UNIQUE",
        "CREATE CONSTRAINT sector_name IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT earnings_uid IF NOT EXISTS FOR (e:Earnings) REQUIRE e.uid IS UNIQUE",
        "CREATE CONSTRAINT news_id IF NOT EXISTS FOR (n:NewsArticle) REQUIRE n.finnhub_id IS UNIQUE",
        "CREATE CONSTRAINT recommendation_uid IF NOT EXISTS FOR (r:Recommendation) REQUIRE r.uid IS UNIQUE",
    ]:
        try:
            session.run(cypher)
        except Exception as e:
            if "EquivalentSchemaRuleAlreadyExists" not in str(e):
                print(f"[WARN] Constraint: {e}")


def load_sector_index():
    path = FH_BASE / "_sector_index.json"
    if not path.exists():
        raise FileNotFoundError(f"Finnhub sector index not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def ticker_path(ticker, sector, filename):
    return FH_BASE / sector / ticker / filename


def cmd_memorize(args):
    sector_index = load_sector_index()
    tickers = [args.ticker] if args.ticker else list(sector_index.keys())
    if args.ticker and args.ticker not in sector_index:
        print(f"[ERROR] Ticker {args.ticker} not in Finnhub universe.")
        sys.exit(1)

    if getattr(args, "dry_run", False):
        print(f"[dry-run] Would ingest {len(tickers)} tickers from {FH_BASE}")
        for t in tickers[:5]:
            s = sector_index[t]
            pf = ticker_path(t, s, "profile.json")
            print(f"  {t} ({s}): profile={pf.exists()}, earnings={ticker_path(t,s,'earnings.json').exists()}, news={ticker_path(t,s,'news.json').exists()}")
        if len(tickers) > 5:
            print(f"  ... and {len(tickers) - 5} more")
        print("Start Neo4j with: python src/server/manage.py start neo4j")
        return

    driver = get_driver()
    db = load_neo4j_config().get("database", "neo4j")
    with driver.session(database=db) as session:
        ensure_constraints(session)
        for sector_name in sorted(set(sector_index.values())):
            session.run("MERGE (s:Sector {name: $name})", name=sector_name)
        for ticker in tickers:
            sector = sector_index[ticker]
            session.run(
                "MERGE (s:Sector {name: $sector}) MERGE (st:Stock {ticker: $ticker}) "
                "MERGE (st)-[:IN_SECTOR]->(s) SET st.sector = $sector",
                ticker=ticker, sector=sector,
            )
        print(f"[OK] Sectors and {len(tickers)} stocks.")

        for ticker in tickers:
            sector = sector_index[ticker]
            pf = ticker_path(ticker, sector, "profile.json")
            if pf.exists():
                try:
                    p = json.loads(pf.read_text(encoding="utf-8"))
                    if isinstance(p, dict):
                        session.run(
                            "MATCH (st:Stock {ticker: $ticker}) SET st.name = $name, st.industry = $industry, "
                            "st.exchange = $exchange, st.market_cap = $market_cap, st.ipo_date = $ipo, st.shares_outstanding = $shares",
                            ticker=ticker, name=p.get("name") or "", industry=p.get("finnhubIndustry") or "",
                            exchange=(p.get("exchange") or "")[:200], market_cap=float(p.get("marketCapitalization") or 0),
                            ipo=p.get("ipo") or "", shares=float(p.get("shareOutstanding") or 0),
                        )
                except Exception as e:
                    print(f"[WARN] Profile {ticker}: {e}")
        print("[OK] Profiles.")

        for ticker in tickers:
            sector = sector_index[ticker]
            ef = ticker_path(ticker, sector, "earnings.json")
            if not ef.exists():
                continue
            try:
                data = json.loads(ef.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for e in data:
                        uid = f"{ticker}_{e.get('period', '')}"
                        session.run(
                            "MATCH (st:Stock {ticker: $ticker}) MERGE (er:Earnings {uid: $uid}) "
                            "SET er.period=$period, er.quarter=$quarter, er.year=$year, er.actual=$actual, "
                            "er.estimate=$estimate, er.surprise=$surprise, er.surprise_pct=$surprise_pct "
                            "MERGE (st)-[:HAS_EARNINGS]->(er)",
                            ticker=ticker, uid=uid, period=e.get("period") or "", quarter=int(e.get("quarter") or 0),
                            year=int(e.get("year") or 0), actual=float(e.get("actual") or 0),
                            estimate=float(e.get("estimate") or 0), surprise=float(e.get("surprise") or 0),
                            surprise_pct=float(e.get("surprisePercent") or 0),
                        )
            except Exception as e:
                print(f"[WARN] Earnings {ticker}: {e}")
        print("[OK] Earnings.")

        for ticker in tickers:
            sector = sector_index[ticker]
            nf = ticker_path(ticker, sector, "news.json")
            if not nf.exists():
                continue
            try:
                data = json.loads(nf.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for art in data:
                        nid = int(art.get("id") or 0)
                        if nid == 0:
                            continue
                        session.run(
                            "MERGE (n:NewsArticle {finnhub_id: $nid}) SET n.headline=$headline, n.summary=$summary, "
                            "n.source=$source, n.url=$url, n.datetime=$dt, n.category=$category "
                            "WITH n MATCH (st:Stock {ticker: $ticker}) MERGE (st)-[:MENTIONED_IN]->(n)",
                            nid=nid, headline=(art.get("headline") or "")[:1000], summary=(art.get("summary") or "")[:4000],
                            source=(art.get("source") or "")[:200], url=(art.get("url") or "")[:500],
                            dt=int(art.get("datetime") or 0), category=(art.get("category") or "")[:100], ticker=ticker,
                        )
            except Exception as e:
                print(f"[WARN] News {ticker}: {e}")
        print("[OK] News.")

        for ticker in tickers:
            sector = sector_index[ticker]
            rf = ticker_path(ticker, sector, "recommendations.json")
            if not rf.exists():
                continue
            try:
                data = json.loads(rf.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for r in data:
                        uid = f"{ticker}_{r.get('period', '')}"
                        session.run(
                            "MATCH (st:Stock {ticker: $ticker}) MERGE (rec:Recommendation {uid: $uid}) "
                            "SET rec.period=$period, rec.buy=$buy, rec.hold=$hold, rec.sell=$sell, rec.strong_buy=$strong_buy, rec.strong_sell=$strong_sell "
                            "MERGE (st)-[:HAS_RECOMMENDATION]->(rec)",
                            ticker=ticker, uid=uid, period=r.get("period") or "",
                            buy=int(r.get("buy") or 0), hold=int(r.get("hold") or 0), sell=int(r.get("sell") or 0),
                            strong_buy=int(r.get("strongBuy") or 0), strong_sell=int(r.get("strongSell") or 0),
                        )
            except Exception as e:
                print(f"[WARN] Recommendations {ticker}: {e}")
        print("[OK] Recommendations.")

        for ticker in tickers:
            sector = sector_index[ticker]
            pf = ticker_path(ticker, sector, "peers.json")
            if not pf.exists():
                continue
            try:
                peers = json.loads(pf.read_text(encoding="utf-8"))
                if isinstance(peers, list):
                    for peer in peers:
                        if peer != ticker and peer in sector_index:
                            session.run(
                                "MATCH (a:Stock {ticker: $ticker}), (b:Stock {ticker: $peer}) MERGE (a)-[:PEERS_WITH]->(b)",
                                ticker=ticker, peer=peer,
                            )
            except Exception as e:
                print(f"[WARN] Peers {ticker}: {e}")
        print("[OK] Peers.")

    driver.close()
    print("Memorize done.")


def cmd_stats(args):
    driver = get_driver()
    db = load_neo4j_config().get("database", "neo4j")
    with driver.session(database=db) as session:
        r = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c ORDER BY c DESC")
        print("Nodes by label:")
        for rec in r:
            print(f"  {rec['label'] or '(unlabeled)'}: {rec['c']:,}")
        r = session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS c ORDER BY c DESC")
        print("\nRelationships by type:")
        for rec in r:
            print(f"  {rec['type']}: {rec['c']:,}")
    driver.close()


def cmd_query(args):
    if not (args.cypher or "").strip():
        print("[ERROR] Provide a Cypher query string.")
        sys.exit(1)
    driver = get_driver()
    db = load_neo4j_config().get("database", "neo4j")
    with driver.session(database=db) as session:
        result = session.run(args.cypher)
        keys = result.keys()
        rows = list(result)
    driver.close()
    print("Keys:", keys)
    for row in rows[:50]:
        print(row)
    if len(rows) > 50:
        print(f"... and {len(rows) - 50} more")


def main():
    parser = argparse.ArgumentParser(description="fin_memory: memorize Finnhub data into Neo4j")
    sub = parser.add_subparsers(dest="command")
    p_mem = sub.add_parser("memorize")
    p_mem.add_argument("--ticker", type=str, help="Single ticker (default: all 60)")
    p_mem.add_argument("--dry-run", action="store_true", help="Check data paths only, no Neo4j")
    sub.add_parser("stats")
    p_q = sub.add_parser("query")
    p_q.add_argument("cypher", type=str, nargs="?", default="")
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)
    try:
        if args.command == "memorize":
            cmd_memorize(args)
        elif args.command == "stats":
            cmd_stats(args)
        elif args.command == "query":
            cmd_query(args)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
