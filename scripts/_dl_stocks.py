"""Download comprehensive stock data via Finnhub API (Fundamental-1 plan).

Pulls 9 data types per ticker for popular movers in finance, semiconductor,
and biotech sectors. Saves JSON files organized by sector/ticker/.

Data types: profile, quote, financials, earnings, recommendations,
            peers, news (30d), news_sentiment, insider_sentiment
"""
import os, sys, json, time
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "raw" / "finnhub_stocks"
KEY_FILE = BASE / ".key"

DELAY = 0.35  # Fundamental plan: 300 calls/min

SECTORS = {
    "finance": [
        "JPM", "GS", "MS", "BAC", "C", "WFC", "BLK", "SCHW", "AXP", "V",
        "MA", "COF", "BK", "MET", "AIG", "PRU", "TFC", "USB", "PNC", "CME",
    ],
    "semiconductor": [
        "NVDA", "AMD", "INTC", "AVGO", "QCOM", "TXN", "AMAT", "LRCX", "KLAC",
        "MRVL", "MU", "TSM", "ASML", "ON", "ADI", "NXPI", "MCHP", "SWKS",
        "MPWR", "ARM",
    ],
    "biotech": [
        "AMGN", "GILD", "REGN", "VRTX", "MRNA", "BIIB", "ILMN", "BMRN",
        "ALNY", "INCY", "EXAS", "NBIX", "SRPT", "IONS", "HALO", "UTHR",
        "RARE", "PCVX", "BGNE", "INSM",
    ],
}


def load_key():
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("FINNHUB_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("FINNHUB_API_KEY")


def safe_call(fn, label, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        err = str(e)
        if "403" in err:
            return None
        if "429" in err:
            sys.stdout.write(f"[Stocks]   Rate limited on {label}, waiting 60s ...\n")
            sys.stdout.flush()
            time.sleep(60)
            try:
                return fn(*args, **kwargs)
            except Exception:
                return None
        return None


def save(data, path):
    if data:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    return False


def main():
    import finnhub

    api_key = load_key()
    if not api_key:
        sys.stdout.write("[Stocks] ERROR: No FINNHUB_API_KEY in .key file\n")
        sys.exit(1)

    client = finnhub.Client(api_key=api_key)
    sys.stdout.write(f"[Stocks] Finnhub key: {api_key[:8]}...{api_key[-4:]}\n")

    all_tickers = []
    for sector, tickers in SECTORS.items():
        all_tickers.extend([(t, sector) for t in tickers])

    total = len(all_tickers)
    sys.stdout.write(f"[Stocks] {total} tickers across {len(SECTORS)} sectors\n")
    sys.stdout.write(f"[Stocks] Data: profile, quote, financials, earnings, recommendations, peers, news, news_sentiment, insider_sentiment\n")
    sys.stdout.flush()

    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / "_sector_index.json", "w") as f:
        json.dump({t: s for t, s in all_tickers}, f, indent=2)

    done_file = DATA / "_completed_v2.json"
    completed = set()
    if done_file.exists():
        completed = set(json.load(open(done_file)))

    remaining = [(t, s) for t, s in all_tickers if t not in completed]
    if not remaining:
        sys.stdout.write(f"[Stocks] SKIP - all {total} tickers already downloaded\n")
        sys.stdout.flush()
        return

    sys.stdout.write(f"[Stocks] {len(completed)} done, {len(remaining)} remaining\n")
    sys.stdout.flush()

    today = datetime.now().strftime("%Y-%m-%d")
    news_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    sent_from = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    api_calls = 0
    current_sector = None

    for i, (ticker, sector) in enumerate(remaining):
        if sector != current_sector:
            current_sector = sector
            n = sum(1 for _, s in remaining[i:] if s == sector)
            sys.stdout.write(f"\n[Stocks] === {sector.upper()} ({n} tickers) ===\n")
            sys.stdout.flush()

        ticker_dir = DATA / sector / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        files = 0
        news_n = 0

        calls = [
            ("profile",          "profile.json",          lambda: client.company_profile2(symbol=ticker)),
            ("quote",            "quote.json",            lambda: client.quote(ticker)),
            ("financials",       "financials.json",       lambda: client.company_basic_financials(ticker, "all")),
            ("earnings",         "earnings.json",         lambda: client.company_earnings(ticker, limit=20)),
            ("recommendations",  "recommendations.json",  lambda: client.recommendation_trends(ticker)),
            ("peers",            "peers.json",            lambda: client.company_peers(ticker)),
            ("news",             "news.json",             lambda: client.company_news(ticker, _from=news_from, to=today)),
            ("news_sentiment",   "news_sentiment.json",   lambda: client.news_sentiment(ticker)),
            ("insider_sentiment","insider_sentiment.json", lambda: client.stock_insider_sentiment(ticker, sent_from, today)),
        ]

        for name, fname, fn in calls:
            time.sleep(DELAY)
            api_calls += 1
            r = safe_call(fn, f"{ticker}/{name}")
            if save(r, ticker_dir / fname):
                files += 1
                if name == "news" and isinstance(r, list):
                    news_n = len(r)

        sys.stdout.write(f"[Stocks]   [{i+1}/{len(remaining)}] {ticker}: {files}/9 files, {news_n} news\n")
        sys.stdout.flush()

        completed.add(ticker)
        with open(done_file, "w") as f:
            json.dump(sorted(completed), f)

    total_files = sum(1 for _ in DATA.rglob("*.json")) - 2
    sys.stdout.write(f"\n[Stocks] DONE - {len(completed)}/{total} tickers, {total_files} files, {api_calls} API calls\n")
    for sector, tickers in SECTORS.items():
        n = sum(1 for t in tickers if t in completed)
        sys.stdout.write(f"[Stocks]   {sector}: {n}/{len(tickers)}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stdout.write(f"[Stocks] ERROR: {e}\n")
        import traceback; traceback.print_exc()
        sys.exit(1)
