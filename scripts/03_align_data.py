"""
Stage 3: Temporal Alignment
Align news articles with stock prices by date
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def align_news_with_prices(prices_df, news_df):
    """Align news articles with stock prices by date and ticker"""
    print("\n" + "="*60)
    print("ALIGNING NEWS WITH PRICES")
    print("="*60)
    
    print(f"Prices: {len(prices_df):,} records")
    print(f"News: {len(news_df):,} articles")
    
    # Ensure both have date and ticker columns
    if 'date' not in prices_df.columns or 'ticker' not in prices_df.columns:
        print("[ERROR] Prices missing 'date' or 'ticker' column")
        return None
    
    # Check if news has ticker information
    has_ticker = 'ticker' in news_df.columns and news_df['ticker'].notna().sum() > 0
    
    if not has_ticker:
        print("[WARNING] News data doesn't have ticker information")
        print("Will need to infer ticker from news text or use as market-level news")
        # For now, skip ticker-specific alignment
        return None
    
    # Ensure dates are datetime
    prices_df['date'] = pd.to_datetime(prices_df['date']).dt.date
    news_df['date'] = pd.to_datetime(news_df['date']).dt.date
    
    # Aggregate news by ticker and date
    print("\nAggregating news by ticker-date...")
    
    # Group news by ticker and date
    news_grouped = news_df.groupby(['ticker', 'date']).agg({
        'text': lambda x: ' | '.join(x.astype(str)),  # Concatenate all news
        'source': lambda x: ', '.join(set(x.astype(str))) if 'source' in news_df.columns else 'unknown'
    }).reset_index()
    
    news_grouped['news_count'] = news_df.groupby(['ticker', 'date']).size().values
    
    print(f"Aggregated to {len(news_grouped):,} ticker-date combinations")
    
    # Merge with prices
    print("\nMerging news with prices...")
    aligned_df = prices_df.merge(
        news_grouped,
        on=['ticker', 'date'],
        how='left',  # Keep all price records even without news
        suffixes=('', '_news')
    )
    
    # Fill NaN news counts with 0
    aligned_df['news_count'] = aligned_df['news_count'].fillna(0).astype(int)
    
    # Calculate alignment statistics
    records_with_news = (aligned_df['news_count'] > 0).sum()
    alignment_rate = records_with_news / len(aligned_df) * 100
    
    print(f"\n[SUCCESS] Aligned data created")
    print(f"  Total records: {len(aligned_df):,}")
    print(f"  Records with news: {records_with_news:,} ({alignment_rate:.1f}%)")
    print(f"  Records without news: {len(aligned_df) - records_with_news:,}")
    print(f"  Date range: {aligned_df['date'].min()} to {aligned_df['date'].max()}")
    
    return aligned_df


def add_market_context(aligned_df, sp500_df):
    """Add market context from S&P 500"""
    print("\n" + "="*60)
    print("ADDING MARKET CONTEXT")
    print("="*60)
    
    # Ensure dates are same type
    aligned_df['date'] = pd.to_datetime(aligned_df['date']).dt.date
    sp500_df['date'] = pd.to_datetime(sp500_df['date']).dt.date
    
    # Select relevant S&P 500 columns
    sp500_context = sp500_df[['date', 'close', 'sp500_return']].copy() if 'sp500_return' in sp500_df.columns else sp500_df[['date', 'close']].copy()
    sp500_context = sp500_context.rename(columns={'close': 'sp500_close'})
    
    # Merge
    aligned_with_context = aligned_df.merge(
        sp500_context,
        on='date',
        how='left'
    )
    
    # Calculate alignment rate
    records_with_context = aligned_with_context['sp500_close'].notna().sum()
    context_rate = records_with_context / len(aligned_with_context) * 100
    
    print(f"[SUCCESS] Added market context")
    print(f"  Records with S&P 500 data: {records_with_context:,} ({context_rate:.1f}%)")
    
    return aligned_with_context


def create_time_windows(aligned_df):
    """Create time windows for prediction (use day T data to predict day T+1)"""
    print("\n" + "="*60)
    print("CREATING TIME WINDOWS")
    print("="*60)
    
    # Sort by ticker and date
    aligned_df = aligned_df.sort_values(['ticker', 'date'])
    
    # Create next day price for prediction target
    if 'close' in aligned_df.columns:
        aligned_df['next_day_close'] = aligned_df.groupby('ticker')['close'].shift(-1)
        aligned_df['next_day_return'] = (
            (aligned_df['next_day_close'] - aligned_df['close']) / aligned_df['close']
        )
        
        # Create target labels: buy (>2% increase), sell (<-2% decrease), hold (between)
        aligned_df['target'] = 'hold'
        aligned_df.loc[aligned_df['next_day_return'] > 0.02, 'target'] = 'buy'
        aligned_df.loc[aligned_df['next_day_return'] < -0.02, 'target'] = 'sell'
        
        # Remove rows without next day data (last day for each ticker)
        before = len(aligned_df)
        aligned_df = aligned_df.dropna(subset=['next_day_return'])
        print(f"Removed {before - len(aligned_df):,} rows without next-day data")
        
        # Print target distribution
        print(f"\nTarget distribution:")
        print(aligned_df['target'].value_counts())
        print(f"\nTarget percentages:")
        print(aligned_df['target'].value_counts(normalize=True) * 100)
    
    return aligned_df


def create_alignment_summary(aligned_df):
    """Create summary of alignment"""
    print("\n" + "="*60)
    print("ALIGNMENT SUMMARY")
    print("="*60)
    
    summary = {
        "alignment_timestamp": pd.Timestamp.now().isoformat(),
        "total_records": len(aligned_df),
        "num_tickers": aligned_df['ticker'].nunique(),
        "date_range": {
            "start": str(aligned_df['date'].min()),
            "end": str(aligned_df['date'].max())
        },
        "news_coverage": {
            "records_with_news": int((aligned_df['news_count'] > 0).sum()),
            "alignment_rate": float((aligned_df['news_count'] > 0).sum() / len(aligned_df) * 100)
        }
    }
    
    if 'target' in aligned_df.columns:
        summary["target_distribution"] = aligned_df['target'].value_counts().to_dict()
    
    if 'sp500_close' in aligned_df.columns:
        summary["market_context_coverage"] = {
            "records_with_sp500": int(aligned_df['sp500_close'].notna().sum()),
            "coverage_rate": float(aligned_df['sp500_close'].notna().sum() / len(aligned_df) * 100)
        }
    
    print(f"Total records: {summary['total_records']:,}")
    print(f"Unique tickers: {summary['num_tickers']}")
    print(f"Date range: {summary['date_range']['start']} to {summary['date_range']['end']}")
    
    # Save summary
    summary_file = PROCESSED_DIR / "03_alignment_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nSummary saved to: {summary_file}")
    return summary


def main():
    """Main alignment function"""
    print("\n" + "="*80)
    print("STAGE 3: TEMPORAL ALIGNMENT")
    print("="*80)
    
    # Load cleaned data
    print("Loading cleaned datasets...")
    prices_df = pd.read_parquet(PROCESSED_DIR / "fnspid_prices_clean.parquet")
    news_df = pd.read_parquet(PROCESSED_DIR / "fnspid_news_clean.parquet")
    sp500_df = pd.read_parquet(PROCESSED_DIR / "sp500_clean.parquet")
    
    # FILTER TO NEWS-AVAILABLE PERIOD
    # Our multi-agent LLM system requires BOTH stock data AND news for explanations
    # FNSPID news only available from 2009-2023, so filter prices to match
    print("\n" + "="*60)
    print("FILTERING TO NEWS-AVAILABLE PERIOD")
    print("="*60)
    
    prices_df['date'] = pd.to_datetime(prices_df['date']).dt.tz_localize(None)
    news_df['date'] = pd.to_datetime(news_df['date']).dt.tz_localize(None)
    
    news_start = news_df['date'].min()
    news_end = news_df['date'].max()
    
    print(f"News date range: {news_start} to {news_end}")
    print(f"Prices before filtering: {len(prices_df):,} records")
    
    # Filter prices to news-available period
    prices_df = prices_df[(prices_df['date'] >= news_start) & (prices_df['date'] <= news_end)]
    
    print(f"Prices after filtering: {len(prices_df):,} records")
    print(f"Filtered date range: {prices_df['date'].min()} to {prices_df['date'].max()}")
    print(f"\n[SUCCESS] Aligned to period where we have BOTH stock prices AND news")
    
    # Align news with prices
    aligned_df = align_news_with_prices(prices_df, news_df)
    
    if aligned_df is None:
        print("\n[WARNING] Could not perform ticker-level alignment")
        print("Falling back to price-only data with market context")
        aligned_df = prices_df.copy()
    
    # Add market context
    aligned_df = add_market_context(aligned_df, sp500_df)
    
    # Create time windows for prediction
    aligned_df = create_time_windows(aligned_df)
    
    # Save aligned data
    print("\nSaving aligned dataset...")
    output_file = PROCESSED_DIR / "data_aligned.parquet"
    aligned_df.to_parquet(output_file, index=False)
    print(f"Saved to: {output_file}")
    
    # Create summary
    summary = create_alignment_summary(aligned_df)
    
    print("\n" + "="*80)
    print("STAGE 3 COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
