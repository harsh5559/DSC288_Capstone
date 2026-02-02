#!/usr/bin/env python3
"""
Download real datasets for DSC288 Capstone Project.
Downloads FNSPID stock data and Financial Phrasebank from HuggingFace.
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm

# Set HuggingFace token via environment variable
# Run: set HF_TOKEN=your_token (Windows) or export HF_TOKEN=your_token (Linux/Mac)
HF_TOKEN = os.environ.get("HF_TOKEN", None)
if not HF_TOKEN:
    print("Warning: HF_TOKEN environment variable not set. Some datasets may require authentication.")
    print("Set it with: set HF_TOKEN=your_huggingface_token")

# Create data directories
data_dir = Path("data/raw")
fnspid_dir = data_dir / "fnspid"
phrasebank_dir = data_dir / "financial_phrasebank"

fnspid_dir.mkdir(parents=True, exist_ok=True)
phrasebank_dir.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("DSC288 Data Download Script")
print("=" * 60)

# ============================================
# 1. Download FNSPID Stock Data
# ============================================
print("\n[1/3] Downloading FNSPID Stock Prices from HuggingFace...")

try:
    from datasets import load_dataset
    
    # Load FNSPID dataset (stock prices)
    # Using the stock price subset
    dataset = load_dataset("Zihan1004/FNSPID", split="train", token=HF_TOKEN)
    print(f"  Downloaded {len(dataset)} records from FNSPID")
    
    # Convert to DataFrame
    df_fnspid = dataset.to_pandas()
    print(f"  Columns: {list(df_fnspid.columns)}")
    
    # Save to parquet
    output_path = fnspid_dir / "fnspid_stock_data.parquet"
    df_fnspid.to_parquet(output_path)
    print(f"  Saved to: {output_path}")
    print(f"  Total records: {len(df_fnspid):,}")
    
except Exception as e:
    print(f"  Error downloading FNSPID: {e}")
    print("  Trying alternative approach with sample data...")
    
    # Create sample stock data using yfinance as fallback
    try:
        import yfinance as yf
        
        # Top 20 S&P 500 stocks
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 
                   'UNH', 'JNJ', 'JPM', 'V', 'PG', 'XOM', 'HD', 'CVX', 'MA', 'ABBV', 
                   'MRK', 'KO', 'PEP', 'COST', 'AVGO', 'WMT', 'MCD', 'CSCO', 'ACN',
                   'ABT', 'CRM', 'TMO', 'DHR', 'LIN', 'NKE', 'ADBE', 'ORCL', 'TXN',
                   'NFLX', 'PM', 'WFC', 'DIS', 'VZ', 'INTC', 'AMD', 'QCOM', 'NEE',
                   'RTX', 'HON', 'UNP', 'LOW', 'SPGI']
        
        print(f"  Downloading {len(tickers)} stocks from Yahoo Finance (2009-2023)...")
        
        all_data = []
        for ticker in tqdm(tickers, desc="  Downloading stocks"):
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(start="2009-10-01", end="2023-12-31")
                if len(hist) > 0:
                    hist = hist.reset_index()
                    hist['ticker'] = ticker
                    hist.columns = [c.lower().replace(' ', '_') for c in hist.columns]
                    all_data.append(hist)
            except Exception as te:
                pass
        
        if all_data:
            df_stocks = pd.concat(all_data, ignore_index=True)
            df_stocks.to_parquet(fnspid_dir / "stock_prices.parquet")
            print(f"  Saved {len(df_stocks):,} records for {len(all_data)} stocks")
        
    except Exception as e2:
        print(f"  Fallback also failed: {e2}")

# ============================================
# 2. Download Financial Phrasebank
# ============================================
print("\n[2/3] Downloading Financial Phrasebank...")

try:
    from datasets import load_dataset
    
    # Load Financial Phrasebank (sentiment labeled data)
    phrasebank = load_dataset("financial_phrasebank", "sentences_allagree", 
                              split="train")
    print(f"  Downloaded {len(phrasebank)} sentences")
    
    # Convert to DataFrame
    df_phrasebank = phrasebank.to_pandas()
    
    # Save
    output_path = phrasebank_dir / "financial_phrasebank.parquet"
    df_phrasebank.to_parquet(output_path)
    print(f"  Saved to: {output_path}")
    
    # Show label distribution
    if 'label' in df_phrasebank.columns:
        print(f"  Label distribution: {df_phrasebank['label'].value_counts().to_dict()}")
    
except Exception as e:
    print(f"  Error: {e}")

# ============================================
# 3. Load S&P 500 Data (already exists)
# ============================================
print("\n[3/3] Checking S&P 500 data...")

sp500_path = data_dir / "yahoo_sp500" / "sp500_1999_2023.csv"
if sp500_path.exists():
    df_sp500 = pd.read_csv(sp500_path)
    print(f"  S&P 500 data already exists: {len(df_sp500):,} records")
else:
    print("  Downloading S&P 500 data...")
    try:
        import yfinance as yf
        sp500 = yf.Ticker("^GSPC")
        hist = sp500.history(start="1999-01-01", end="2023-12-31")
        hist = hist.reset_index()
        
        sp500_dir = data_dir / "yahoo_sp500"
        sp500_dir.mkdir(parents=True, exist_ok=True)
        hist.to_csv(sp500_path, index=False)
        print(f"  Downloaded {len(hist):,} records")
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "=" * 60)
print("Data download complete!")
print("=" * 60)
