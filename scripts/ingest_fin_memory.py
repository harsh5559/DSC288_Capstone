"""
Ingest all Finnhub data into Neo4j (build fin_memory graph).

Prerequisites:
  - Docker running (Neo4j runs in a container)
  - Raw data in data/raw/finnhub_stocks/ (60 tickers)

Usage (from repo root):
  python scripts/ingest_fin_memory.py

This will:
  1. Start Neo4j if not running
  2. Wait for Neo4j to be ready
  3. Run full memorize (all 60 tickers: sectors, stocks, profiles, earnings, news, recommendations, peers)
  4. Print graph stats
"""
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def run(cmd, check=True):
    r = subprocess.run(cmd, cwd=str(REPO), shell=False)
    if check and r.returncode != 0:
        sys.exit(r.returncode)
    return r.returncode


def main():
    print("Fin memory ingest – Neo4j must be running (Docker).")
    print()

    print("1. Starting Neo4j if needed...")
    run([sys.executable, "src/server/manage.py", "start", "neo4j"], check=False)

    print("2. Waiting for Neo4j bolt (up to 60s)...")
    for i in range(60):
        time.sleep(1)
        ret = run([sys.executable, "src/agents/fin_memory.py", "stats"], check=False)
        if ret == 0:
            print(f"   Ready after {i + 1}s.")
            break
    else:
        print("[ERROR] Neo4j did not become ready. Start Docker Desktop and run again.")
        sys.exit(1)

    print()
    print("3. Ingesting all 60 tickers (sectors, stocks, profiles, earnings, news, recommendations, peers)...")
    run([sys.executable, "src/agents/fin_memory.py", "memorize"])

    print()
    print("4. Graph stats:")
    run([sys.executable, "src/agents/fin_memory.py", "stats"])

    print()
    print("Fin memory build complete.")
    print("  Neo4j Browser: http://localhost:7474  (neo4j / dsc288graph)")
    print("  Query from CLI: python src/agents/fin_memory.py query \"MATCH (n) RETURN count(n)\"")


if __name__ == "__main__":
    main()
