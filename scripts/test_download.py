#!/usr/bin/env python3
"""Test dataset downloads"""
import sys
print("Starting download test...", flush=True)

import os
from huggingface_hub import login
print("Logging in to HuggingFace...", flush=True)
HF_TOKEN = os.environ.get("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)
else:
    print("Warning: HF_TOKEN not set. Set with: set HF_TOKEN=your_token", flush=True)
print("Login successful!", flush=True)

from datasets import load_dataset
import pandas as pd
from pathlib import Path

# Test FNSPID
print("\n[1] Testing FNSPID dataset...", flush=True)
try:
    ds = load_dataset('Zihan1004/FNSPID', split='train')
    print(f"  Loaded {len(ds)} records", flush=True)
    print(f"  Columns: {ds.column_names}", flush=True)
    
    # Save to file
    df = ds.to_pandas()
    output_path = Path("data/raw/fnspid/fnspid_data.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path)
    print(f"  Saved to: {output_path}", flush=True)
    print(f"  Sample row: {df.iloc[0].to_dict()}", flush=True)
except Exception as e:
    print(f"  FNSPID Error: {e}", flush=True)
    import traceback
    traceback.print_exc()

# Test Financial Phrasebank
print("\n[2] Testing Financial Phrasebank...", flush=True)
try:
    pb = load_dataset('financial_phrasebank', 'sentences_allagree', split='train')
    print(f"  Loaded {len(pb)} sentences", flush=True)
    
    df_pb = pb.to_pandas()
    output_path = Path("data/raw/financial_phrasebank/phrasebank.parquet")
    df_pb.to_parquet(output_path)
    print(f"  Saved to: {output_path}", flush=True)
    print(f"  Label distribution: {df_pb['label'].value_counts().to_dict()}", flush=True)
except Exception as e:
    print(f"  Phrasebank Error: {e}", flush=True)

# Download stocks via yfinance as backup
print("\n[3] Downloading stock data via yfinance...", flush=True)
try:
    import yfinance as yf
    from tqdm import tqdm
    
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JPM', 
               'V', 'JNJ', 'WMT', 'PG', 'XOM', 'UNH', 'HD', 'MA', 'BAC', 'PFE',
               'KO', 'DIS', 'CSCO', 'VZ', 'ADBE', 'NFLX', 'CRM', 'INTC', 'AMD',
               'NKE', 'MCD', 'T', 'ORCL', 'IBM', 'GE', 'BA', 'CAT', 'MMM']
    
    all_data = []
    for ticker in tqdm(tickers, desc="  Downloading"):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start="2010-01-01", end="2023-12-31")
            if len(hist) > 0:
                hist = hist.reset_index()
                hist['ticker'] = ticker
                hist.columns = [c.lower().replace(' ', '_') for c in hist.columns]
                all_data.append(hist)
        except:
            pass
    
    if all_data:
        df_stocks = pd.concat(all_data, ignore_index=True)
        output_path = Path("data/raw/fnspid/stock_prices.parquet")
        df_stocks.to_parquet(output_path)
        print(f"  Downloaded {len(df_stocks):,} records for {len(all_data)} stocks", flush=True)
        print(f"  Saved to: {output_path}", flush=True)
        print(f"  Date range: {df_stocks['date'].min()} to {df_stocks['date'].max()}", flush=True)
except Exception as e:
    print(f"  yfinance Error: {e}", flush=True)

print("\nDownload test complete!", flush=True)
