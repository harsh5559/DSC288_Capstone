# Fin Memory Implementation: Neo4j Knowledge Graph

**DSC288 Capstone — Group 10**  
**Last updated:** February 2026

This document describes the implementation of the **fin_memory** agent: how Finnhub master data is ingested into a Neo4j knowledge graph for financial explainability, how entities and relationships are built, and how they were verified.

---

## 1. What Was Implemented

| Component | Location | Purpose |
|-----------|----------|---------|
| **Unified server management** | `src/server/manage.py` | Single CLI to start/stop/status **LiteLLM** and **Neo4j**. Commands: `start`, `stop`, `restart` (optional: `litellm` \| `neo4j` \| `all`), `status`, `neo4j reset`, `neo4j shell`. |
| **Neo4j config** | `config/neo4j.yaml` | Connection: `bolt://localhost:7687`, user `neo4j`, password `dsc288graph`, database `neo4j`. |
| **fin_memory agent** | `src/agents/fin_memory.py` | Memorize Finnhub data into Neo4j. Commands: `memorize` (optional `--ticker`, `--dry-run`), `stats`, `query "CYPHER"`. |
| **Ingest script** | `scripts/ingest_fin_memory.py` | One-shot: start Neo4j (if needed), wait for Bolt, run full `memorize`, print stats. |
| **Neo4j runtime** | Docker container `dsc288-neo4j` | Neo4j Community image; ports 7474 (browser), 7687 (Bolt); data volume `data/neo4j/` (gitignored). |

**Prerequisites:** Docker running for Neo4j; raw Finnhub data under `data/raw/finnhub_stocks/` (60 tickers, see `_sector_index.json`).

---

## 2. How Entities and Relationships Are Built

The graph is built from **Finnhub** as the master source. All writes use **MERGE** (idempotent); re-running `memorize` updates or adds nodes/relationships without duplicating.

### 2.1 Master Index

- **File:** `data/raw/finnhub_stocks/_sector_index.json`
- **Content:** `{ "TICKER": "sector", ... }` for 60 tickers in `finance`, `semiconductor`, `biotech`.
- **Use:** Drives the list of tickers and their sector; every other entity is built per-ticker from this list.

### 2.2 Entities (Node Labels)

| Entity | Source file(s) | Key properties | Uniqueness |
|--------|----------------|----------------|------------|
| **Sector** | `_sector_index.json` (derived) | `name` (finance / semiconductor / biotech) | `name` |
| **Stock** | `_sector_index.json` + `{sector}/{ticker}/profile.json` | `ticker`, `name`, `sector`, `industry`, `exchange`, `market_cap`, `ipo_date`, `shares_outstanding` | `ticker` |
| **Earnings** | `{sector}/{ticker}/earnings.json` (array) | `uid` (= `ticker_period`), `period`, `quarter`, `year`, `actual`, `estimate`, `surprise`, `surprise_pct` | `uid` |
| **NewsArticle** | `{sector}/{ticker}/news.json` (array) | `finnhub_id` (from `id`), `headline`, `summary`, `source`, `url`, `datetime`, `category` | `finnhub_id` |
| **Recommendation** | `{sector}/{ticker}/recommendations.json` (array) | `uid` (= `ticker_period`), `period`, `buy`, `hold`, `sell`, `strong_buy`, `strong_sell` | `uid` |

- **Sector:** One MERGE per sector name from the unique values in `_sector_index.json`.
- **Stock:** One MERGE per ticker; linked to Sector via `IN_SECTOR`; profile fields (name, industry, exchange, market_cap, ipo_date, shares_outstanding) set from `profile.json` when present.
- **Earnings:** One MERGE per record in `earnings.json` with `uid = ticker + "_" + period`; linked from Stock with `HAS_EARNINGS`.
- **NewsArticle:** One MERGE per article using `finnhub_id`; multiple stocks can point to the same article via `MENTIONED_IN` (same article can mention multiple tickers).
- **Recommendation:** One MERGE per record with `uid = ticker + "_" + period`; linked from Stock with `HAS_RECOMMENDATION`.

### 2.3 Relationships

| Relationship | From | To | Built from |
|--------------|------|-----|------------|
| **IN_SECTOR** | Stock | Sector | `_sector_index.json`: each ticker → one sector. |
| **HAS_EARNINGS** | Stock | Earnings | Each row in `earnings.json` for that ticker. |
| **MENTIONED_IN** | Stock | NewsArticle | Each row in `news.json` for that ticker (article merged by `finnhub_id`). |
| **HAS_RECOMMENDATION** | Stock | Recommendation | Each row in `recommendations.json` for that ticker. |
| **PEERS_WITH** | Stock | Stock | `{sector}/{ticker}/peers.json` (array of ticker strings). Only pairs where both tickers exist in `_sector_index.json` are created. |

### 2.4 Build Order in Code

1. Create uniqueness constraints (Stock.ticker, Sector.name, Earnings.uid, NewsArticle.finnhub_id, Recommendation.uid).
2. MERGE all Sector nodes; MERGE all Stock nodes and `(Stock)-[:IN_SECTOR]->(Sector)`.
3. For each ticker: load `profile.json` → SET Stock properties.
4. For each ticker: load `earnings.json` → MERGE Earnings, MERGE `(Stock)-[:HAS_EARNINGS]->(Earnings)`.
5. For each ticker: load `news.json` → MERGE NewsArticle, MERGE `(Stock)-[:MENTIONED_IN]->(NewsArticle)`.
6. For each ticker: load `recommendations.json` → MERGE Recommendation, MERGE `(Stock)-[:HAS_RECOMMENDATION]->(Recommendation)`.
7. For each ticker: load `peers.json` → MERGE `(Stock)-[:PEERS_WITH]->(Stock)` for each peer in universe.

Implementation: `src/agents/fin_memory.py`, function `cmd_memorize()`.

---

## 3. Verification: How It Was Verified

### 3.1 Server and Connectivity

- **Neo4j running:** `python src/server/manage.py status` → Neo4j section shows RUNNING, container `dsc288-neo4j`, Bolt and Browser URLs.
- **Bolt connectivity:** `python src/agents/fin_memory.py stats` returns node/relationship counts (no connection error).

### 3.2 Schema (Node Labels and Properties)

Cypher used:

```cypher
CALL db.schema.nodeTypeProperties() YIELD nodeLabels, propertyName, propertyTypes
RETURN nodeLabels, collect(propertyName) AS properties ORDER BY nodeLabels
```

**Verified result:**

| Node label     | Properties |
|----------------|------------|
| Sector         | `name` |
| Stock          | `ticker`, `name`, `sector`, `industry`, `exchange`, `market_cap`, `ipo_date`, `shares_outstanding` |
| Earnings       | `uid`, `period`, `quarter`, `year`, `actual`, `estimate`, `surprise`, `surprise_pct` |
| NewsArticle    | `finnhub_id`, `headline`, `datetime`, `category`, `summary`, `url`, `source` |
| Recommendation | `uid`, `period`, `buy`, `sell`, `strong_sell`, `strong_buy`, `hold` |

### 3.3 Counts (After Full Ingest)

- **Nodes by label:** Sector 3, Stock 60, Earnings 220, NewsArticle 6,960, Recommendation 232.
- **Relationships by type:** IN_SECTOR 60, HAS_EARNINGS 220, MENTIONED_IN 8,344, HAS_RECOMMENDATION 232, PEERS_WITH 193.

Obtained via:

```bash
python src/agents/fin_memory.py stats
```

### 3.4 Sample Content and Relationships

- **Sectors:** `MATCH (n:Sector) RETURN n.name` → biotech, finance, semiconductor.
- **Stocks per sector:** `MATCH (a:Stock)-[:IN_SECTOR]->(s:Sector) RETURN s.name, count(a) AS stocks` → 20 per sector.
- **Stock profile sample:** `MATCH (s:Stock) RETURN s.ticker, s.sector, s.name, s.industry, s.market_cap LIMIT 12` → tickers with names and industries.
- **Earnings sample:** `MATCH (s:Stock {ticker: 'JPM'})-[:HAS_EARNINGS]->(e:Earnings) RETURN e.period, e.actual, e.estimate, e.surprise_pct ORDER BY e.period DESC LIMIT 4` → quarterly earnings with surprise.
- **News sample:** `MATCH (n:NewsArticle) RETURN n.finnhub_id, left(n.headline,60), n.source, n.datetime LIMIT 4` → headlines and source.
- **Recommendation sample:** `MATCH (r:Recommendation) RETURN r.uid, r.period, r.buy, r.hold, r.sell, r.strong_buy, r.strong_sell LIMIT 5` → analyst consensus counts.
- **Relationship mix from Stock:** `MATCH (a:Stock)-[r]->(b) RETURN type(r), labels(b)[0], count(r) ORDER BY count(r) DESC` → confirms IN_SECTOR, HAS_EARNINGS, MENTIONED_IN, HAS_RECOMMENDATION, PEERS_WITH with expected targets.
- **Peers sample:** `MATCH (a:Stock)-[:PEERS_WITH]->(b:Stock) RETURN a.ticker, count(b) AS peer_count ORDER BY peer_count DESC LIMIT 8` → peer counts per stock.

### 3.5 Constraints

Uniqueness constraints created in code and verified by successful MERGE behavior and no duplicate-key errors:

- `Stock.ticker`
- `Sector.name`
- `Earnings.uid`
- `NewsArticle.finnhub_id`
- `Recommendation.uid`

---

## 4. How to Run

**Start Neo4j (requires Docker):**

```bash
python src/server/manage.py start neo4j
# Wait ~30–60s for Bolt; then:
python src/server/manage.py status
```

**Ingest (build fin memory):**

```bash
python src/agents/fin_memory.py memorize
# Or single ticker:
python src/agents/fin_memory.py memorize --ticker JPM
# Or dry-run (no Neo4j):
python src/agents/fin_memory.py memorize --dry-run
```

**One-shot (start Neo4j + full ingest + stats):**

```bash
python scripts/ingest_fin_memory.py
```

**Inspect graph:**

```bash
python src/agents/fin_memory.py stats
python src/agents/fin_memory.py query "MATCH (s:Stock)-[:IN_SECTOR]->(sec:Sector {name: 'finance'}) RETURN s.ticker, s.name LIMIT 5"
```

**Neo4j Browser:** http://localhost:7474 (login `neo4j` / `dsc288graph`).

**Wipe graph (for a clean re-ingest):**

```bash
python src/server/manage.py neo4j reset
```

---

## 5. Summary Table: Entities and Relationships

| Entity / Relationship | Source data | Count (verified) |
|------------------------|------------|-------------------|
| Sector                 | `_sector_index.json` | 3 |
| Stock                  | `_sector_index.json` + `profile.json` | 60 |
| Earnings               | `earnings.json` per ticker | 220 |
| NewsArticle            | `news.json` per ticker | 6,960 |
| Recommendation         | `recommendations.json` per ticker | 232 |
| IN_SECTOR              | Stock → Sector | 60 |
| HAS_EARNINGS           | Stock → Earnings | 220 |
| MENTIONED_IN           | Stock → NewsArticle | 8,344 |
| HAS_RECOMMENDATION     | Stock → Recommendation | 232 |
| PEERS_WITH             | Stock → Stock | 193 |

This graph supports explainability queries such as: stocks by sector, earnings surprises, news per ticker, analyst consensus, and peer comparisons.
