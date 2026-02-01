"""
Stage 2: Data Cleansing
Handle NULL values, remove duplicates, standardize formats
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


def clean_prices(prices_df):
    """Clean stock price data"""
    print("\n" + "="*60)
    print("CLEANING STOCK PRICES")
    print("="*60)
    
    print(f"Initial records: {len(prices_df):,}")
    initial_count = len(prices_df)
    
    # Standardize column names
    prices_df.columns = prices_df.columns.str.strip().str.lower().str.replace(' ', '_')
    print(f"Columns: {list(prices_df.columns)}")
    
    # Convert date column
    date_col = 'date' if 'date' in prices_df.columns else prices_df.columns[0]
    prices_df[date_col] = pd.to_datetime(prices_df[date_col], errors='coerce')
    prices_df = prices_df.rename(columns={date_col: 'date'})
    
    # Remove rows with invalid dates
    before = len(prices_df)
    prices_df = prices_df.dropna(subset=['date'])
    print(f"Removed {before - len(prices_df):,} rows with invalid dates")
    
    # Handle missing price data (forward fill within each ticker)
    price_cols = ['open', 'high', 'low', 'close', 'volume']
    existing_price_cols = [col for col in price_cols if col in prices_df.columns]
    
    if existing_price_cols:
        # Forward fill within each ticker group
        prices_df = prices_df.sort_values(['ticker', 'date'])
        prices_df[existing_price_cols] = prices_df.groupby('ticker')[existing_price_cols].ffill()
        
        # Drop rows still with missing critical data (close price)
        if 'close' in prices_df.columns:
            before = len(prices_df)
            prices_df = prices_df.dropna(subset=['close'])
            print(f"Removed {before - len(prices_df):,} rows with missing close price")
    
    # Remove duplicates (same ticker-date)
    before = len(prices_df)
    prices_df = prices_df.drop_duplicates(subset=['ticker', 'date'], keep='first')
    print(f"Removed {before - len(prices_df):,} duplicate records")
    
    # Remove outliers (price changes > 50% in a day, likely errors)
    if 'close' in prices_df.columns:
        prices_df = prices_df.sort_values(['ticker', 'date'])
        prices_df['pct_change'] = prices_df.groupby('ticker')['close'].pct_change()
        
        before = len(prices_df)
        outliers = (prices_df['pct_change'].abs() > 0.5) & (prices_df['pct_change'].notna())
        prices_df = prices_df[~outliers]
        print(f"Removed {before - len(prices_df):,} outlier records (>50% daily change)")
        
        prices_df = prices_df.drop(columns=['pct_change'])
    
    # Ensure positive prices and volume
    if existing_price_cols:
        for col in existing_price_cols:
            if col in prices_df.columns:
                before = len(prices_df)
                prices_df = prices_df[prices_df[col] > 0]
                if before > len(prices_df):
                    print(f"Removed {before - len(prices_df):,} rows with non-positive {col}")
    
    print(f"\n[SUCCESS] Cleaned price data")
    print(f"  Initial: {initial_count:,} records")
    print(f"  Final: {len(prices_df):,} records")
    print(f"  Retention: {len(prices_df)/initial_count*100:.1f}%")
    
    return prices_df


def clean_news(news_df):
    """Clean news data"""
    print("\n" + "="*60)
    print("CLEANING NEWS DATA")
    print("="*60)
    
    print(f"Initial records: {len(news_df):,}")
    initial_count = len(news_df)
    
    # Standardize column names
    news_df.columns = news_df.columns.str.strip().str.lower().str.replace(' ', '_')
    print(f"Columns: {list(news_df.columns)}")
    
    # Identify date and ticker columns (they may have different names)
    date_col = None
    ticker_col = None
    text_col = None
    
    for col in news_df.columns:
        if 'date' in col or 'time' in col:
            date_col = col
        if 'ticker' in col or 'symbol' in col or 'stock' in col:
            ticker_col = col
        if 'title' in col or 'headline' in col or 'text' in col or 'content' in col:
            text_col = col
    
    print(f"Detected - Date: {date_col}, Ticker: {ticker_col}, Text: {text_col}")
    
    # Convert date column
    if date_col:
        news_df[date_col] = pd.to_datetime(news_df[date_col], errors='coerce')
        news_df = news_df.rename(columns={date_col: 'date'})
        
        # Remove invalid dates
        before = len(news_df)
        news_df = news_df.dropna(subset=['date'])
        print(f"Removed {before - len(news_df):,} rows with invalid dates")
    
    # Standardize ticker column
    if ticker_col and ticker_col != 'ticker':
        news_df = news_df.rename(columns={ticker_col: 'ticker'})
    
    # Standardize text column
    if text_col and text_col != 'text':
        news_df = news_df.rename(columns={text_col: 'text'})
    
    # Remove rows with missing text
    if 'text' in news_df.columns:
        before = len(news_df)
        news_df = news_df.dropna(subset=['text'])
        news_df = news_df[news_df['text'].str.strip() != '']
        print(f"Removed {before - len(news_df):,} rows with missing text")
    
    # Remove duplicates based on content similarity (exact matches)
    if 'text' in news_df.columns:
        before = len(news_df)
        news_df = news_df.drop_duplicates(subset=['text'], keep='first')
        print(f"Removed {before - len(news_df):,} duplicate articles")
    
    # Remove HTML tags if present
    if 'text' in news_df.columns:
        news_df['text'] = news_df['text'].str.replace(r'<[^>]+>', '', regex=True)
        news_df['text'] = news_df['text'].str.replace(r'\s+', ' ', regex=True)
        news_df['text'] = news_df['text'].str.strip()
    
    # Filter out very short articles (likely noise)
    if 'text' in news_df.columns:
        before = len(news_df)
        news_df = news_df[news_df['text'].str.len() > 20]
        print(f"Removed {before - len(news_df):,} articles with <20 characters")
    
    print(f"\n[SUCCESS] Cleaned news data")
    print(f"  Initial: {initial_count:,} records")
    print(f"  Final: {len(news_df):,} records")
    print(f"  Retention: {len(news_df)/initial_count*100:.1f}%")
    
    return news_df


def clean_phrasebank(phrasebank_df):
    """Clean Financial Phrasebank data"""
    print("\n" + "="*60)
    print("CLEANING FINANCIAL PHRASEBANK")
    print("="*60)
    
    print(f"Initial records: {len(phrasebank_df):,}")
    initial_count = len(phrasebank_df)
    
    # Remove rows with missing values
    before = len(phrasebank_df)
    phrasebank_df = phrasebank_df.dropna()
    print(f"Removed {before - len(phrasebank_df):,} rows with missing values")
    
    # Remove duplicates
    before = len(phrasebank_df)
    phrasebank_df = phrasebank_df.drop_duplicates(subset=['sentence'], keep='first')
    print(f"Removed {before - len(phrasebank_df):,} duplicate sentences")
    
    # Standardize sentiment labels
    phrasebank_df['sentiment'] = phrasebank_df['sentiment'].str.strip().str.lower()
    
    # Map to standard labels
    sentiment_map = {
        'positive': 'positive',
        'negative': 'negative',
        'neutral': 'neutral'
    }
    phrasebank_df['sentiment'] = phrasebank_df['sentiment'].map(sentiment_map)
    
    # Remove rows with invalid sentiment
    before = len(phrasebank_df)
    phrasebank_df = phrasebank_df.dropna(subset=['sentiment'])
    print(f"Removed {before - len(phrasebank_df):,} rows with invalid sentiment")
    
    print(f"\n[SUCCESS] Cleaned phrasebank data")
    print(f"  Initial: {initial_count:,} records")
    print(f"  Final: {len(phrasebank_df):,} records")
    print(f"  Sentiment distribution:\n{phrasebank_df['sentiment'].value_counts()}")
    
    return phrasebank_df


def clean_sp500(sp500_df):
    """Clean S&P 500 data"""
    print("\n" + "="*60)
    print("CLEANING S&P 500 DATA")
    print("="*60)
    
    print(f"Initial records: {len(sp500_df):,}")
    initial_count = len(sp500_df)
    
    # Standardize column names
    sp500_df.columns = sp500_df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    # Convert date column (might be index)
    if 'date' not in sp500_df.columns:
        sp500_df = sp500_df.reset_index()
        sp500_df.columns = ['date'] + list(sp500_df.columns[1:])
    
    sp500_df['date'] = pd.to_datetime(sp500_df['date'], errors='coerce')
    
    # Remove invalid dates
    before = len(sp500_df)
    sp500_df = sp500_df.dropna(subset=['date'])
    print(f"Removed {before - len(sp500_df):,} rows with invalid dates")
    
    # Remove duplicates
    before = len(sp500_df)
    sp500_df = sp500_df.drop_duplicates(subset=['date'], keep='first')
    print(f"Removed {before - len(sp500_df):,} duplicate dates")
    
    # Forward fill missing values
    sp500_df = sp500_df.sort_values('date')
    numeric_cols = sp500_df.select_dtypes(include=[np.number]).columns
    sp500_df[numeric_cols] = sp500_df[numeric_cols].ffill()
    
    # Calculate daily return for market context
    if 'close' in sp500_df.columns:
        sp500_df['sp500_return'] = sp500_df['close'].pct_change()
    
    print(f"\n[SUCCESS] Cleaned S&P 500 data")
    print(f"  Initial: {initial_count:,} records")
    print(f"  Final: {len(sp500_df):,} records")
    print(f"  Date range: {sp500_df['date'].min()} to {sp500_df['date'].max()}")
    
    return sp500_df


def create_cleaning_summary(datasets):
    """Create summary of cleaning operations"""
    print("\n" + "="*60)
    print("DATA CLEANING SUMMARY")
    print("="*60)
    
    summary = {
        "cleaning_timestamp": pd.Timestamp.now().isoformat(),
        "datasets": {}
    }
    
    for name, df in datasets.items():
        if df is not None:
            summary["datasets"][name] = {
                "records": len(df),
                "columns": list(df.columns),
                "null_counts": df.isnull().sum().to_dict(),
                "dtypes": df.dtypes.astype(str).to_dict()
            }
            print(f"{name:25s}: {len(df):>10,} records")
    
    # Save summary
    summary_file = PROCESSED_DIR / "02_cleaning_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\nSummary saved to: {summary_file}")
    return summary


def main():
    """Main cleaning function"""
    print("\n" + "="*80)
    print("STAGE 2: DATA CLEANING")
    print("="*80)
    
    # Load raw data
    prices_df = pd.read_parquet(PROCESSED_DIR / "fnspid_prices_raw.parquet")
    news_df = pd.read_parquet(PROCESSED_DIR / "fnspid_news_raw.parquet")
    phrasebank_df = pd.read_parquet(PROCESSED_DIR / "financial_phrasebank_raw.parquet")
    sp500_df = pd.read_parquet(PROCESSED_DIR / "sp500_raw.parquet")
    
    # Clean each dataset
    prices_clean = clean_prices(prices_df)
    news_clean = clean_news(news_df)
    phrasebank_clean = clean_phrasebank(phrasebank_df)
    sp500_clean = clean_sp500(sp500_df)
    
    # Save cleaned data
    print("\nSaving cleaned datasets...")
    prices_clean.to_parquet(PROCESSED_DIR / "fnspid_prices_clean.parquet", index=False)
    news_clean.to_parquet(PROCESSED_DIR / "fnspid_news_clean.parquet", index=False)
    phrasebank_clean.to_parquet(PROCESSED_DIR / "financial_phrasebank_clean.parquet", index=False)
    sp500_clean.to_parquet(PROCESSED_DIR / "sp500_clean.parquet", index=False)
    
    # Create summary
    datasets = {
        "prices": prices_clean,
        "news": news_clean,
        "phrasebank": phrasebank_clean,
        "sp500": sp500_clean
    }
    summary = create_cleaning_summary(datasets)
    
    print("\n" + "="*80)
    print("STAGE 2 COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
