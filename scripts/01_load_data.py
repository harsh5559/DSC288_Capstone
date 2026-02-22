"""
Stage 1: Data Loading
Load all datasets from raw data directory
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# Create processed directory
PROCESSED_DIR.mkdir(exist_ok=True)


def _get_finnhub_tickers():
    """Tickers from data/raw/finnhub_stocks/_sector_index.json (Neo4j/fin_memory source)."""
    path = RAW_DIR / "finnhub_stocks" / "_sector_index.json"
    if not path.exists():
        return []
    with open(path) as f:
        return [t.strip().upper() for t in json.load(f).keys() if t]


def load_fnspid_prices():
    """Load FNSPID stock price data from individual CSVs.
    Prefers tickers that exist in Finnhub/Neo4j (_sector_index.json) for aligned train/test and eval.
    """
    print("\n" + "="*60)
    print("LOADING FNSPID STOCK PRICES")
    print("="*60)
    
    price_dir = RAW_DIR / "fnspid" / "Stock_price" / "full_history" / "full_history"
    
    if not price_dir.exists():
        print(f"[ERROR] Price directory not found: {price_dir}")
        return None
    
    csv_files = sorted(price_dir.glob("*.csv"), key=lambda f: f.stem)
    available_stems = {f.stem.upper() for f in csv_files}
    print(f"Found {len(csv_files)} stock CSV files")
    
    finnhub_tickers = _get_finnhub_tickers()
    if finnhub_tickers:
        # Use intersection so train/test align with Neo4j/Finnhub for analysis and eval
        intersection = [s for s in finnhub_tickers if s in available_stems]
        if intersection:
            # Keep CSV order by stem so we can look up files
            stem_to_file = {f.stem.upper(): f for f in csv_files}
            selected_files = [stem_to_file[t] for t in sorted(intersection) if t in stem_to_file]
            selection_method = "finnhub_neo4j_intersection"
            print(f"Using {len(selected_files)} tickers (Finnhub/Neo4j intersection with FNSPID)")
        else:
            selected_files = csv_files[:100]
            selection_method = "first_100_alphabetically"
            print(f"No overlap with Finnhub tickers; using first 100 alphabetically")
    else:
        selected_files = csv_files[:100]
        selection_method = "first_100_alphabetically"
        print(f"Finnhub index not found; using first {len(selected_files)} alphabetically")
    
    selected_tickers = [f.stem for f in selected_files]

    ticker_list_file = PROCESSED_DIR / "selected_tickers.json"
    with open(ticker_list_file, 'w') as f:
        json.dump({
            "selection_method": selection_method,
            "count": len(selected_tickers),
            "tickers": selected_tickers
        }, f, indent=2)
    print(f"Selected {len(selected_tickers)} tickers. Saved to: {ticker_list_file}")
    
    # Load a sample first to check structure
    if selected_files:
        sample = pd.read_csv(selected_files[0])
        print(f"\nSample file columns: {list(sample.columns)}")
        print(f"Sample shape: {sample.shape}")
    
    # Load all price data
    all_prices = []
    
    print("\nLoading stock prices...")
    for csv_file in tqdm(selected_files, desc="Loading prices"):
        try:
            df = pd.read_csv(csv_file)
            ticker = csv_file.stem  # Filename without extension
            df['ticker'] = ticker
            all_prices.append(df)
        except Exception as e:
            print(f"[WARNING] Failed to load {csv_file.name}: {e}")
            continue
    
    if all_prices:
        print("\n[INFO] Concatenating dataframes...")
        prices_df = pd.concat(all_prices, ignore_index=True)
        print(f"[SUCCESS] Loaded {len(all_prices)} stocks")
        print(f"Total records: {len(prices_df):,}")
        print(f"Date range: {prices_df['Date'].min()} to {prices_df['Date'].max()}" if 'Date' in prices_df.columns else "")
        
        # Save to processed
        print("\n[INFO] Saving to parquet...")
        output_file = PROCESSED_DIR / "fnspid_prices_raw.parquet"
        prices_df.to_parquet(output_file, index=False)
        print(f"[SUCCESS] Saved to: {output_file}")
        
        return prices_df
    else:
        print("[ERROR] No price data loaded")
        return None


def load_fnspid_news():
    """Load FNSPID news data"""
    print("\n" + "="*60)
    print("LOADING FNSPID NEWS DATA")
    print("="*60)
    
    news_dir = RAW_DIR / "fnspid" / "Stock_news"
    
    # Load external news
    all_external_file = news_dir / "All_external.csv"
    nasdaq_file = news_dir / "nasdaq_exteral_data.csv"
    
    news_dfs = []
    
    if all_external_file.exists():
        print(f"\n[INFO] Found: {all_external_file.name}")
        file_size_gb = all_external_file.stat().st_size / (1024*1024*1024)
        print(f"[INFO] File size: {file_size_gb:.2f} GB")
        
        if file_size_gb > 1:
            print(f"[WARNING] File is very large ({file_size_gb:.2f} GB)")
            print("[INFO] Loading only first 10,000 rows for validation...")
            df = pd.read_csv(all_external_file, nrows=10000)
        else:
            print("[INFO] Reading CSV...")
            df = pd.read_csv(all_external_file)
        
        print("[INFO] CSV loaded, processing...")
        df['source'] = 'external'
        news_dfs.append(df)
        print(f"[SUCCESS] Records: {len(df):,}")
        print(f"  Columns: {list(df.columns)}")
    
    if nasdaq_file.exists():
        print(f"\n[INFO] Found: {nasdaq_file.name}")
        file_size_gb = nasdaq_file.stat().st_size / (1024*1024*1024)
        print(f"[INFO] File size: {file_size_gb:.2f} GB")
        
        if file_size_gb > 1:
            print(f"[WARNING] File is very large ({file_size_gb:.2f} GB)")
            print("[INFO] Loading only first 10,000 rows for validation...")
            df = pd.read_csv(nasdaq_file, nrows=10000)
        else:
            print("[INFO] Reading CSV...")
            df = pd.read_csv(nasdaq_file)
        
        print("[INFO] CSV loaded, processing...")
        df['source'] = 'nasdaq'
        news_dfs.append(df)
        print(f"[SUCCESS] Records: {len(df):,}")
    
    if news_dfs:
        print("\n[INFO] Concatenating news dataframes...")
        news_df = pd.concat(news_dfs, ignore_index=True)
        print(f"[SUCCESS] Loaded {len(news_df):,} news articles")
        
        # Save to processed
        print("\n[INFO] Saving news to parquet...")
        output_file = PROCESSED_DIR / "fnspid_news_raw.parquet"
        news_df.to_parquet(output_file, index=False)
        print(f"[SUCCESS] Saved to: {output_file}")
        
        return news_df
    else:
        print("[ERROR] No news data loaded")
        return None


def load_financial_phrasebank():
    """Load Financial Phrasebank for sentiment analysis"""
    print("\n" + "="*60)
    print("LOADING FINANCIAL PHRASEBANK")
    print("="*60)
    
    phrasebank_dir = RAW_DIR / "financial_phrasebank" / "data" / "FinancialPhraseBank-v1.0"
    
    # Load the all-agree file (highest quality)
    all_agree_file = phrasebank_dir / "Sentences_AllAgree.txt"
    
    if not all_agree_file.exists():
        print(f"[ERROR] File not found: {all_agree_file}")
        return None
    
    # Parse the file (format: sentence@sentiment)
    print("[INFO] Parsing sentences...")
    sentences = []
    sentiments = []
    
    with open(all_agree_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if '@' in line:
                parts = line.rsplit('@', 1)
                if len(parts) == 2:
                    sentence, sentiment = parts
                    sentences.append(sentence.strip())
                    sentiments.append(sentiment.strip())
    
    print(f"[INFO] Parsed {len(sentences)} sentences")
    
    print("[INFO] Creating dataframe...")
    phrasebank_df = pd.DataFrame({
        'sentence': sentences,
        'sentiment': sentiments
    })
    
    print(f"[SUCCESS] Loaded {len(phrasebank_df):,} sentences")
    print(f"Sentiment distribution:\n{phrasebank_df['sentiment'].value_counts()}")
    
    # Save to processed
    print("\n[INFO] Saving phrasebank to parquet...")
    output_file = PROCESSED_DIR / "financial_phrasebank_raw.parquet"
    phrasebank_df.to_parquet(output_file, index=False)
    print(f"[SUCCESS] Saved to: {output_file}")
    
    return phrasebank_df


def load_yahoo_sp500():
    """Load Yahoo S&P 500 data for market context"""
    print("\n" + "="*60)
    print("LOADING YAHOO S&P 500")
    print("="*60)
    
    sp500_file = RAW_DIR / "yahoo_sp500" / "sp500_1999_2023.csv"
    
    if not sp500_file.exists():
        print(f"[ERROR] File not found: {sp500_file}")
        return None
    
    print("[INFO] Loading S&P 500 CSV...")
    sp500_df = pd.read_csv(sp500_file)
    print(f"[SUCCESS] Loaded {len(sp500_df):,} trading days")
    print(f"Columns: {list(sp500_df.columns)}")
    print(f"Date range: {sp500_df['Date'].min()} to {sp500_df['Date'].max()}" if 'Date' in sp500_df.columns else "")
    
    # Save to processed
    print("\n[INFO] Saving S&P 500 to parquet...")
    output_file = PROCESSED_DIR / "sp500_raw.parquet"
    sp500_df.to_parquet(output_file, index=False)
    print(f"[SUCCESS] Saved to: {output_file}")
    
    return sp500_df


def load_finqa():
    """Load FinQA for explanation benchmarking"""
    print("\n" + "="*60)
    print("LOADING FINQA")
    print("="*60)
    
    finqa_dir = RAW_DIR / "finqa"
    
    finqa_data = {}
    
    for split in ['train', 'validation', 'test']:
        file_path = finqa_dir / f"finqa_{split}.json"
        if file_path.exists():
            print(f"\n[INFO] Loading {split}...")
            try:
                # Try reading as JSON lines first
                df = pd.read_json(file_path, lines=True)
                finqa_data[split] = df
                print(f"[SUCCESS] Loaded {split}: {len(df):,} records")
            except ValueError:
                # If that fails, try as regular JSON array
                try:
                    print("[INFO] Trying alternative JSON format...")
                    with open(file_path, 'r', encoding='utf-8') as f:
                        import json
                        data = json.load(f)
                        df = pd.DataFrame(data)
                        finqa_data[split] = df
                        print(f"[SUCCESS] Loaded {split}: {len(df):,} records")
                except Exception as e:
                    print(f"[WARNING] Could not load {split}: {e}")
                    continue
        else:
            print(f"[WARNING] Not found: {file_path}")
    
    if finqa_data:
        # Save each split (as CSV due to complex nested structures)
        print("\n[INFO] Saving FinQA splits...")
        for split, df in finqa_data.items():
            output_file = PROCESSED_DIR / f"finqa_{split}_raw.csv"
            df.to_csv(output_file, index=False)
            print(f"[SUCCESS] Saved: {output_file}")
    
    return finqa_data


def create_loading_summary():
    """Create a summary of loaded data"""
    print("\n" + "="*60)
    print("DATA LOADING SUMMARY")
    print("="*60)
    
    summary = {
        "loading_timestamp": pd.Timestamp.now().isoformat(),
        "datasets": {}
    }
    
    # Check what was loaded
    processed_files = list(PROCESSED_DIR.glob("*_raw.parquet"))
    
    for file in processed_files:
        try:
            df = pd.read_parquet(file)
            dataset_name = file.stem.replace("_raw", "")
            summary["datasets"][dataset_name] = {
                "file": str(file.name),
                "records": len(df),
                "columns": list(df.columns),
                "size_mb": round(file.stat().st_size / (1024*1024), 2)
            }
            print(f"{dataset_name:25s}: {len(df):>10,} records")
        except Exception as e:
            print(f"[WARNING] Could not read {file.name}: {e}")
    
    # Save summary
    summary_file = PROCESSED_DIR / "01_loading_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nSummary saved to: {summary_file}")
    return summary


def main():
    """Main loading function"""
    print("\n" + "="*80)
    print("STAGE 1: DATA LOADING")
    print("="*80)
    
    # Load all datasets
    prices = load_fnspid_prices()
    news = load_fnspid_news()
    phrasebank = load_financial_phrasebank()
    sp500 = load_yahoo_sp500()
    finqa = load_finqa()
    
    # Create summary
    summary = create_loading_summary()
    
    print("\n" + "="*80)
    print("STAGE 1 COMPLETE")
    print("="*80)
    print(f"Processed data saved to: {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
