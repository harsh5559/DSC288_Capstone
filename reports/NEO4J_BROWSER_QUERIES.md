# Viewing Entities in Neo4j Browser

**Neo4j Browser:** http://localhost:7474  
**Login:** `neo4j` / `dsc288graph`

(If Neo4j is not running: `python src/server/manage.py start neo4j` and wait ~30s.)

---

## Queries that show the graph (nodes + relationships)

Paste these into the Neo4j Browser query bar and click **Run**. Switch the result view to **Graph** (icon on the left of the result panel) to see nodes and edges.

### 1. Sectors and all stocks (60 nodes + 60 edges)
```cypher
MATCH (s:Stock)-[:IN_SECTOR]->(sec:Sector)
RETURN s, sec
```
Shows every stock and its sector. For a smaller picture, add `LIMIT 20` before the semicolon.

### 2. One stock with its sector, earnings, and a few news articles
```cypher
MATCH (s:Stock {ticker: 'JPM'})-[:IN_SECTOR]->(sec:Sector)
OPTIONAL MATCH (s)-[:HAS_EARNINGS]->(e:Earnings)
OPTIONAL MATCH (s)-[:MENTIONED_IN]->(n:NewsArticle)
RETURN s, sec, e, n
LIMIT 50
```
Replace `JPM` with any ticker (e.g. `NVDA`, `AMGN`).

### 3. One stock and its peers (graph of stocks only)
```cypher
MATCH (s:Stock {ticker: 'NVDA'})-[:PEERS_WITH]->(p:Stock)
RETURN s, p
```
Shows NVDA and all peers as a star.

### 4. One sector with a few stocks and their latest recommendation
```cypher
MATCH (s:Stock)-[:IN_SECTOR]->(sec:Sector {name: 'finance'})
OPTIONAL MATCH (s)-[:HAS_RECOMMENDATION]->(r:Recommendation)
WHERE r.period STARTS WITH '2026'
RETURN s, sec, r
LIMIT 30
```

### 5. Small subgraph: 3 stocks, their sector, and earnings
```cypher
MATCH (s:Stock)-[:IN_SECTOR]->(sec:Sector)
WHERE s.ticker IN ['JPM', 'NVDA', 'AMGN']
OPTIONAL MATCH (s)-[:HAS_EARNINGS]->(e:Earnings)
RETURN s, sec, e
LIMIT 25
```

---

## Table-style queries (no graph drawing)

Use these to inspect properties in **Table** or **Text** view.

- **Counts by label:**  
  `MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC`

- **Sample stocks:**  
  `MATCH (s:Stock) RETURN s.ticker, s.name, s.sector, s.industry LIMIT 10`

- **Sample earnings:**  
  `MATCH (s:Stock)-[:HAS_EARNINGS]->(e:Earnings) RETURN s.ticker, e.period, e.actual, e.estimate, e.surprise_pct LIMIT 10`

- **Sample news:**  
  `MATCH (s:Stock)-[:MENTIONED_IN]->(n:NewsArticle) RETURN s.ticker, n.headline, n.source LIMIT 5`

---

## Tips in Neo4j Browser

- After running a query, click **Graph** in the result toolbar to see the visualization.
- Double-click a node to expand its relationships (or use the star icon on the node).
- Click a node label in the legend to change its color.
- Use **Fullscreen** (bottom right) for a larger graph view.
