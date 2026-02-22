"""
Load real market data from data/processed (parquet) and optionally data/raw
for use in prompts and LLM-as-judge evaluation.

Provides ticker+date aligned rows: close, next_day_return, target (buy/hold/sell),
and optional news/text so prompts are grounded in real numbers.
"""

from pathlib import Path
from typing import Any, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
RAW_DIR = REPO_ROOT / "data" / "raw"
FH_SECTOR_INDEX = RAW_DIR / "finnhub_stocks" / "_sector_index.json"

# Parquet from pipeline: ticker, date, target, next_day_return, close, ...
VAL_FILE = PROCESSED_DIR / "val_final.parquet"
TEST_FILE = PROCESSED_DIR / "test_final.parquet"

# Cache for Finnhub ticker list (from Neo4j/fin_memory source)
_finnhub_tickers: Optional[list[str]] = None


def get_finnhub_tickers() -> list[str]:
    """Return list of tickers from data/raw/finnhub_stocks/_sector_index.json (Neo4j/fin_memory source)."""
    global _finnhub_tickers
    if _finnhub_tickers is not None:
        return _finnhub_tickers
    if not FH_SECTOR_INDEX.exists():
        _finnhub_tickers = []
        return []
    import json
    with open(FH_SECTOR_INDEX) as f:
        index = json.load(f)
    _finnhub_tickers = sorted((t.strip().upper() for t in index.keys() if t), key=str)
    return _finnhub_tickers


def _load_split_dfs():
    """Lazy-load validation and test dataframes. Returns (val_df, test_df) or (None, None)."""
    val_df = pd.read_parquet(VAL_FILE) if VAL_FILE.exists() else None
    test_df = pd.read_parquet(TEST_FILE) if TEST_FILE.exists() else None
    return val_df, test_df


# Module-level cache so we don't re-read parquet every call
_cached_val: Optional[pd.DataFrame] = None
_cached_test: Optional[pd.DataFrame] = None


def get_processed_df(split: str = "validation") -> Optional[pd.DataFrame]:
    """Return validation or test dataframe. Cached."""
    global _cached_val, _cached_test
    if split == "validation":
        if _cached_val is None and VAL_FILE.exists():
            _cached_val = pd.read_parquet(VAL_FILE)
            _cached_val["date"] = pd.to_datetime(_cached_val["date"]).dt.date
        return _cached_val
    if split == "test":
        if _cached_test is None and TEST_FILE.exists():
            _cached_test = pd.read_parquet(TEST_FILE)
            _cached_test["date"] = pd.to_datetime(_cached_test["date"]).dt.date
        return _cached_test
    return None


def get_row_for_ticker_date(
    ticker: str,
    date: Any,
    split: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Get a single row for (ticker, date) from processed parquet.
    If split is None, search validation then test.
    Returns dict with at least: ticker, date, target, next_day_return, close (if present).
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return None
    try:
        dt = pd.to_datetime(date).date() if date else None
    except Exception:
        return None
    if dt is None:
        return None

    for s in ([split] if split else ["validation", "test"]):
        df = get_processed_df(s)
        if df is None:
            continue
        if "date" not in df.columns:
            continue
        mask = (df["ticker"].astype(str).str.upper() == ticker) & (df["date"].astype("datetime64[ns]").dt.date == dt)
        hit = df.loc[mask]
        if len(hit) == 0:
            continue
        row = hit.iloc[0]
        out: dict[str, Any] = {
            "ticker": str(row.get("ticker", ticker)),
            "date": str(row.get("date")),
            "target": str(row.get("target", "hold")).lower(),
            "next_day_return": float(row["next_day_return"]) if "next_day_return" in row.index and pd.notna(row.get("next_day_return")) else None,
            "close": float(row["close"]) if "close" in row.index and pd.notna(row.get("close")) else None,
        }
        if "open" in df.columns:
            out["open"] = float(row["open"]) if pd.notna(row.get("open")) else None
        if "high" in df.columns:
            out["high"] = float(row["high"]) if pd.notna(row.get("high")) else None
        if "low" in df.columns:
            out["low"] = float(row["low"]) if pd.notna(row.get("low")) else None
        if "news_count" in df.columns:
            out["news_count"] = int(row["news_count"]) if pd.notna(row.get("news_count")) else 0
        if "text" in df.columns and pd.notna(row.get("text")):
            out["news_text_snippet"] = (str(row["text"])[:1500] + "...") if len(str(row["text"])) > 1500 else str(row["text"])
        return out
    return None


def sample_rows_for_judge(
    split: str = "validation",
    n: int = 20,
    tickers: Optional[list[str]] = None,
    seed: int = 42,
    use_finnhub_tickers_only: bool = True,
) -> list[dict[str, Any]]:
    """
    Sample n rows from validation or test for LLM-as-judge evaluation.
    By default restricts to Finnhub/Neo4j tickers so analyst has graph context.
    Returns list of dicts with ticker, date, target, next_day_return, close, etc.
    """
    df = get_processed_df(split)
    if df is None or len(df) == 0:
        return []
    if tickers is not None:
        df = df[df["ticker"].astype(str).str.upper().isin([t.strip().upper() for t in tickers])]
    elif use_finnhub_tickers_only:
        fh = get_finnhub_tickers()
        if fh:
            df = df[df["ticker"].astype(str).str.upper().isin(fh)]
    if len(df) == 0:
        return []
    df = df.sample(n=min(n, len(df)), random_state=seed)
    out = []
    for _, row in df.iterrows():
        out.append({
            "ticker": str(row.get("ticker", "")),
            "date": str(row.get("date")),
            "target": str(row.get("target", "hold")).lower(),
            "next_day_return": float(row["next_day_return"]) if "next_day_return" in row.index and pd.notna(row.get("next_day_return")) else None,
            "close": float(row["close"]) if "close" in row.index and pd.notna(row.get("close")) else None,
        })
    return out
