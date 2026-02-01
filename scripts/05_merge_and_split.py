"""
Stage 5: Data Merging and Train/Val/Test Split
Create final datasets with temporal splits
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def create_temporal_split(df, train_end='2021-12-31', val_end='2022-12-31'):
    """
    Split data temporally to prevent look-ahead bias
    Train: up to train_end
    Validation: train_end to val_end
    Test: after val_end
    """
    print("\n" + "="*60)
    print("CREATING TEMPORAL TRAIN/VAL/TEST SPLIT")
    print("="*60)
    
    # Ensure date is datetime
    df['date'] = pd.to_datetime(df['date'])
    
    # Get date range
    print(f"Full date range: {df['date'].min()} to {df['date'].max()}")
    
    # Create splits
    train_df = df[df['date'] <= train_end].copy()
    val_df = df[(df['date'] > train_end) & (df['date'] <= val_end)].copy()
    test_df = df[df['date'] > val_end].copy()
    
    print(f"\nSplit sizes:")
    print(f"  Train: {len(train_df):,} records ({len(train_df)/len(df)*100:.1f}%)")
    print(f"  Val:   {len(val_df):,} records ({len(val_df)/len(df)*100:.1f}%)")
    print(f"  Test:  {len(test_df):,} records ({len(test_df)/len(df)*100:.1f}%)")
    
    print(f"\nTrain date range: {train_df['date'].min()} to {train_df['date'].max()}")
    print(f"Val date range:   {val_df['date'].min()} to {val_df['date'].max()}")
    print(f"Test date range:  {test_df['date'].min()} to {test_df['date'].max()}")
    
    # Check target distribution in each split
    if 'target' in df.columns:
        print(f"\nTarget distribution:")
        print(f"\nTrain:")
        print(train_df['target'].value_counts(normalize=True) * 100)
        print(f"\nValidation:")
        print(val_df['target'].value_counts(normalize=True) * 100)
        print(f"\nTest:")
        print(test_df['target'].value_counts(normalize=True) * 100)
    
    return train_df, val_df, test_df


def select_model_features(df):
    """Select relevant features for modeling"""
    print("\n" + "="*60)
    print("SELECTING MODEL FEATURES")
    print("="*60)
    
    # Essential columns to keep
    essential_cols = ['ticker', 'date', 'target', 'next_day_return']
    essential_cols = [col for col in essential_cols if col in df.columns]
    
    # Feature columns (exclude raw price/volume, keep indicators)
    feature_cols = []
    
    # Technical indicators
    technical_patterns = ['sma_', 'ema_', 'macd', 'rsi_', 'bb_', 'return_', 'volatility']
    for col in df.columns:
        if any(pattern in col for pattern in technical_patterns):
            feature_cols.append(col)
    
    # Sentiment features
    sentiment_patterns = ['sentiment']
    for col in df.columns:
        if any(pattern in col for pattern in sentiment_patterns):
            feature_cols.append(col)
    
    # Volume features
    volume_patterns = ['volume_ratio', 'volume_sma']
    for col in df.columns:
        if any(pattern in col for pattern in volume_patterns):
            feature_cols.append(col)
    
    # Market context
    market_patterns = ['sp500_return']
    for col in df.columns:
        if any(pattern in col for pattern in market_patterns):
            feature_cols.append(col)
    
    # News count
    if 'news_count' in df.columns:
        feature_cols.append('news_count')
    
    # Combine
    selected_cols = essential_cols + feature_cols
    selected_cols = list(dict.fromkeys(selected_cols))  # Remove duplicates while preserving order
    
    # Keep only available columns
    selected_cols = [col for col in selected_cols if col in df.columns]
    
    print(f"Selected {len(selected_cols)} columns:")
    print(f"  Essential: {len(essential_cols)}")
    print(f"  Features: {len(feature_cols)}")
    
    df_selected = df[selected_cols].copy()
    
    # Fill any remaining NaNs with forward fill, then 0
    df_selected = df_selected.ffill().fillna(0)
    
    return df_selected


def create_rag_context_file(df):
    """
    Create a file mapping ticker-date to source information for RAG
    This will help agents cite their sources
    """
    print("\n" + "="*60)
    print("CREATING RAG CONTEXT FILE")
    print("="*60)
    
    # Select relevant columns for RAG
    rag_cols = ['ticker', 'date']
    
    if 'text' in df.columns:
        rag_cols.append('text')
    if 'news_count' in df.columns:
        rag_cols.append('news_count')
    if 'source' in df.columns:
        rag_cols.append('source')
    
    rag_cols = [col for col in rag_cols if col in df.columns]
    
    if len(rag_cols) > 2:  # More than just ticker and date
        rag_df = df[rag_cols].copy()
        rag_df = rag_df[rag_df['text'].notna()] if 'text' in rag_df.columns else rag_df
        
        output_file = PROCESSED_DIR / "rag_context.parquet"
        rag_df.to_parquet(output_file, index=False)
        print(f"[SUCCESS] Created RAG context file: {output_file}")
        print(f"  Records: {len(rag_df):,}")
        return True
    else:
        print("[WARNING] Insufficient data for RAG context file")
        return False


def create_final_summary(train_df, val_df, test_df):
    """Create final pipeline summary"""
    print("\n" + "="*60)
    print("FINAL PIPELINE SUMMARY")
    print("="*60)
    
    summary = {
        "pipeline_completion_timestamp": pd.Timestamp.now().isoformat(),
        "splits": {
            "train": {
                "records": len(train_df),
                "date_range": {
                    "start": str(train_df['date'].min()),
                    "end": str(train_df['date'].max())
                },
                "tickers": train_df['ticker'].nunique(),
                "features": len(train_df.columns) - 4  # Exclude ticker, date, target, next_day_return
            },
            "validation": {
                "records": len(val_df),
                "date_range": {
                    "start": str(val_df['date'].min()),
                    "end": str(val_df['date'].max())
                },
                "tickers": val_df['ticker'].nunique(),
                "features": len(val_df.columns) - 4
            },
            "test": {
                "records": len(test_df),
                "date_range": {
                    "start": str(test_df['date'].min()),
                    "end": str(test_df['date'].max())
                },
                "tickers": test_df['ticker'].nunique(),
                "features": len(test_df.columns) - 4
            }
        },
        "feature_columns": list(train_df.columns)
    }
    
    if 'target' in train_df.columns:
        summary["splits"]["train"]["target_distribution"] = train_df['target'].value_counts().to_dict()
        summary["splits"]["validation"]["target_distribution"] = val_df['target'].value_counts().to_dict()
        summary["splits"]["test"]["target_distribution"] = test_df['target'].value_counts().to_dict()
    
    print(f"\nFinal dataset summary:")
    print(f"  Train:      {summary['splits']['train']['records']:,} records, {summary['splits']['train']['tickers']} tickers")
    print(f"  Validation: {summary['splits']['validation']['records']:,} records, {summary['splits']['validation']['tickers']} tickers")
    print(f"  Test:       {summary['splits']['test']['records']:,} records, {summary['splits']['test']['tickers']} tickers")
    print(f"  Features:   {summary['splits']['train']['features']}")
    
    # Save summary
    summary_file = PROCESSED_DIR / "05_final_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Also create a README
    readme_content = f"""# Processed Financial Data

## Pipeline Completion
- Date: {summary['pipeline_completion_timestamp']}
- Pipeline Version: 1.0

## Dataset Splits

### Train Set
- Records: {summary['splits']['train']['records']:,}
- Date Range: {summary['splits']['train']['date_range']['start']} to {summary['splits']['train']['date_range']['end']}
- Tickers: {summary['splits']['train']['tickers']}
- Features: {summary['splits']['train']['features']}

### Validation Set
- Records: {summary['splits']['validation']['records']:,}
- Date Range: {summary['splits']['validation']['date_range']['start']} to {summary['splits']['validation']['date_range']['end']}
- Tickers: {summary['splits']['validation']['tickers']}

### Test Set
- Records: {summary['splits']['test']['records']:,}
- Date Range: {summary['splits']['test']['date_range']['start']} to {summary['splits']['test']['date_range']['end']}
- Tickers: {summary['splits']['test']['tickers']}

## Files
- `train_final.parquet` - Training data
- `val_final.parquet` - Validation data
- `test_final.parquet` - Test data
- `rag_context.parquet` - News/text data for RAG
- `sentiment_model.pkl` - Trained sentiment analysis model
- `*_summary.json` - Pipeline stage summaries

## Features
See `05_final_summary.json` for complete feature list.

## Usage
```python
import pandas as pd

# Load data
train = pd.read_parquet('data/processed/train_final.parquet')
val = pd.read_parquet('data/processed/val_final.parquet')
test = pd.read_parquet('data/processed/test_final.parquet')

# For RAG context
rag_context = pd.read_parquet('data/processed/rag_context.parquet')
```
"""
    
    readme_file = PROCESSED_DIR / "README.md"
    with open(readme_file, 'w') as f:
        f.write(readme_content)
    
    print(f"\nSummary saved to: {summary_file}")
    print(f"README saved to: {readme_file}")
    
    return summary


def main():
    """Main merging and splitting function"""
    print("\n" + "="*80)
    print("STAGE 5: MERGING AND SPLITTING")
    print("="*80)
    
    # Load feature-engineered data
    print("Loading feature-engineered data...")
    df = pd.read_parquet(PROCESSED_DIR / "data_with_features.parquet")
    print(f"Loaded {len(df):,} records with {len(df.columns)} columns")
    
    # Select model features
    df_selected = select_model_features(df)
    
    # Create temporal splits
    train_df, val_df, test_df = create_temporal_split(df_selected)
    
    # Save final datasets
    print("\nSaving final datasets...")
    train_df.to_parquet(PROCESSED_DIR / "train_final.parquet", index=False)
    val_df.to_parquet(PROCESSED_DIR / "val_final.parquet", index=False)
    test_df.to_parquet(PROCESSED_DIR / "test_final.parquet", index=False)
    print("[SUCCESS] Saved train, validation, and test sets")
    
    # Create RAG context file
    create_rag_context_file(df)
    
    # Create final summary
    summary = create_final_summary(train_df, val_df, test_df)
    
    print("\n" + "="*80)
    print("STAGE 5 COMPLETE")
    print("="*80)
    print("\nAll processed data saved to: data/processed/")
    print("  - train_final.parquet")
    print("  - val_final.parquet")
    print("  - test_final.parquet")
    print("  - rag_context.parquet")
    print("  - sentiment_model.pkl")


if __name__ == "__main__":
    main()
