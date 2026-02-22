"""Quick test of Finnhub API endpoints to see what's available."""
import finnhub, json

KEY = "d6diaghr01qm89pjkjcgd6diaghr01qm89pjkjd0"
c = finnhub.Client(api_key=KEY)

endpoints = [
    ("quote",            lambda: c.quote("AAPL")),
    ("profile",          lambda: c.company_profile2(symbol="AAPL")),
    ("financials",       lambda: c.company_basic_financials("AAPL", "all")),
    ("earnings",         lambda: c.company_earnings("AAPL", limit=4)),
    ("recommendations",  lambda: c.recommendation_trends("AAPL")),
    ("peers",            lambda: c.company_peers("AAPL")),
    ("news",             lambda: c.company_news("AAPL", _from="2026-02-01", to="2026-02-22")),
    ("stock_candles",    lambda: c.stock_candles("AAPL", "D", 1704067200, 1706745600)),
    ("news_sentiment",   lambda: c.news_sentiment("AAPL")),
    ("insider_sentiment",lambda: c.stock_insider_sentiment("AAPL", "2024-01-01", "2025-01-01")),
    ("price_target",     lambda: c.price_target("AAPL")),
    ("upgrade_downgrade",lambda: c.upgrade_downgrade(symbol="AAPL", _from="2024-01-01", to="2025-01-01")),
    ("insider_txns",     lambda: c.stock_insider_transactions("AAPL", "2024-01-01", "2025-01-01")),
]

print(f"Testing {len(endpoints)} Finnhub endpoints...\n")
ok, fail = 0, 0
for name, fn in endpoints:
    try:
        r = fn()
        size = len(r) if isinstance(r, (list, dict)) else "?"
        print(f"  OK     {name:<22} ({size} items)")
        ok += 1
    except Exception as e:
        code = str(e)[:60]
        print(f"  FAIL   {name:<22} {code}")
        fail += 1

print(f"\n{ok} OK, {fail} FAIL out of {len(endpoints)}")
