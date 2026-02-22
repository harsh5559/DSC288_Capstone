"""
Fetch stock context from Neo4j for LLM-based explainability.

Used by the MCP server to gather company profile, sector, earnings, news headlines,
recommendations, and peers so the LLM can produce grounded recommendations.
"""

import json
from pathlib import Path
from typing import Any, Optional

import yaml
from neo4j import GraphDatabase

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
NEO4J_CONFIG = REPO_ROOT / "config" / "neo4j.yaml"


def _load_config() -> dict:
    if not NEO4J_CONFIG.exists():
        return {}
    with open(NEO4J_CONFIG) as f:
        return yaml.safe_load(f) or {}


def get_driver():
    cfg = _load_config()
    uri = cfg.get("uri", "bolt://localhost:7687")
    user = cfg.get("user", "neo4j")
    password = cfg.get("password", "dsc288graph")
    return GraphDatabase.driver(uri, auth=(user, password))


def get_stock_context(ticker: str, news_limit: int = 5, earnings_limit: int = 4) -> dict[str, Any]:
    """
    Fetch from Neo4j: profile, sector, latest earnings, recent news headlines, peers, latest recommendation.
    Returns a dict suitable for inclusion in an LLM prompt.
    """
    ticker = ticker.upper().strip()
    driver = get_driver()
    db = _load_config().get("database", "neo4j")
    out: dict[str, Any] = {
        "ticker": ticker,
        "found": False,
        "sector": None,
        "name": None,
        "industry": None,
        "market_cap": None,
        "earnings": [],
        "news_headlines": [],
        "peers": [],
        "recommendation": None,
    }

    try:
        with driver.session(database=db) as session:
            # Stock + sector + profile fields
            r = session.run(
                """
                MATCH (s:Stock {ticker: $ticker})-[:IN_SECTOR]->(sec:Sector)
                RETURN s.ticker AS ticker, s.name AS name, s.sector AS sector,
                       s.industry AS industry, s.market_cap AS market_cap
                """,
                ticker=ticker,
            )
            rec = r.single()
            if not rec:
                return out
            out["found"] = True
            out["sector"] = rec.get("sector")
            out["name"] = rec.get("name")
            out["industry"] = rec.get("industry")
            out["market_cap"] = rec.get("market_cap")

            # Latest earnings
            r = session.run(
                """
                MATCH (s:Stock {ticker: $ticker})-[:HAS_EARNINGS]->(e:Earnings)
                RETURN e.period AS period, e.actual AS actual, e.estimate AS estimate, e.surprise_pct AS surprise_pct
                ORDER BY e.period DESC LIMIT $limit
                """,
                ticker=ticker,
                limit=earnings_limit,
            )
            out["earnings"] = [dict(zip(("period", "actual", "estimate", "surprise_pct"), (x.get("period"), x.get("actual"), x.get("estimate"), x.get("surprise_pct")))) for x in r]

            # Recent news (headlines only)
            r = session.run(
                """
                MATCH (s:Stock {ticker: $ticker})-[:MENTIONED_IN]->(n:NewsArticle)
                RETURN n.headline AS headline, n.source AS source
                LIMIT $limit
                """,
                ticker=ticker,
                limit=news_limit,
            )
            out["news_headlines"] = [{"headline": x.get("headline"), "source": x.get("source")} for x in r]

            # Peers
            r = session.run(
                """
                MATCH (s:Stock {ticker: $ticker})-[:PEERS_WITH]->(p:Stock)
                RETURN p.ticker AS ticker ORDER BY p.ticker
                """,
                ticker=ticker,
            )
            out["peers"] = [x.get("ticker") for x in r if x.get("ticker")]

            # Latest recommendation
            r = session.run(
                """
                MATCH (s:Stock {ticker: $ticker})-[:HAS_RECOMMENDATION]->(r:Recommendation)
                RETURN r.period AS period, r.buy AS buy, r.hold AS hold, r.sell AS sell,
                       r.strong_buy AS strong_buy, r.strong_sell AS strong_sell
                ORDER BY r.period DESC LIMIT 1
                """,
                ticker=ticker,
            )
            rec_rec = r.single()
            if rec_rec:
                out["recommendation"] = dict(rec_rec)
    finally:
        driver.close()

    return out


def get_news_for_ticker(ticker: str, limit: int = 10, query: Optional[str] = None) -> list[dict]:
    """Return list of news articles (headline, summary, source, url) for the ticker."""
    ticker = ticker.upper().strip()
    driver = get_driver()
    db = _load_config().get("database", "neo4j")
    results = []
    try:
        with driver.session(database=db) as session:
            if query:
                # Simple headline filter (Neo4j doesn't have full-text by default)
                r = session.run(
                    """
                    MATCH (s:Stock {ticker: $ticker})-[:MENTIONED_IN]->(n:NewsArticle)
                    WHERE toLower(n.headline) CONTAINS toLower($query)
                    RETURN n.headline AS headline, n.summary AS summary, n.source AS source, n.url AS url
                    LIMIT $limit
                    """,
                    ticker=ticker,
                    query=query,
                    limit=limit,
                )
            else:
                r = session.run(
                    """
                    MATCH (s:Stock {ticker: $ticker})-[:MENTIONED_IN]->(n:NewsArticle)
                    RETURN n.headline AS headline, n.summary AS summary, n.source AS source, n.url AS url
                    LIMIT $limit
                    """,
                    ticker=ticker,
                    limit=limit,
                )
            for x in r:
                results.append({k: x.get(k) for k in ("headline", "summary", "source", "url")})
    finally:
        driver.close()
    return results
