# Data Pipeline Scripts

This directory contains the data pipeline for the Financial Decision Support System.

## Pipeline Overview

The pipeline processes raw financial data through 5 stages:

```
Stage 1: Load Data → Stage 2: Clean Data → Stage 3: Align Data → 
Stage 4: Feature Engineering → Stage 5: Merge & Split
```

## Running the Pipeline

### Option 1: Run Complete Pipeline (Recommended)

```bash
python scripts/run_pipeline.py
```

This runs all 5 stages in sequence and creates the final processed datasets.

### Option 2: Run Individual Stages

You can run stages individually for debugging or development:

```bash
python scripts/01_load_data.py
python scripts/02_clean_data.py
python scripts/03_align_data.py
python scripts/04_feature_engineering.py
python scripts/05_merge_and_split.py
```

## Pipeline Stages

### Stage 1: Data Loading (`01_load_data.py`)
- Loads all raw datasets from `data/raw/`
- Loads 100 stocks from FNSPID (can be adjusted)
- Loads Financial Phrasebank, FinQA, and S&P 500 data
- **Output:** `*_raw.parquet` files in `data/processed/`

### Stage 2: Data Cleaning (`02_clean_data.py`)
- Handles NULL values with forward fill
- Removes duplicates
- Standardizes date formats
- Removes outliers (>50% daily price changes)
- Cleans text data (HTML tags, whitespace)
- **Output:** `*_clean.parquet` files

### Stage 3: Temporal Alignment (`03_align_data.py`)
- Aligns news articles with stock prices by (ticker, date)
- Adds S&P 500 market context
- Creates prediction targets (buy/hold/sell)
- Uses news from day T to predict day T+1
- **Output:** `data_aligned.parquet`

### Stage 4: Feature Engineering (`04_feature_engineering.py`)
- Calculates technical indicators:
  - Moving averages (SMA, EMA)
  - MACD, RSI, Bollinger Bands
  - Momentum and volatility
- Trains sentiment model on Financial Phrasebank
- Adds sentiment scores to news text
- Creates lag features
- **Output:** `data_with_features.parquet`, `sentiment_model.pkl`

### Stage 5: Merging and Splitting (`05_merge_and_split.py`)
- Selects model-ready features
- Creates temporal train/val/test splits:
  - Train: data up to 2021-12-31
  - Validation: 2022-01-01 to 2022-12-31
  - Test: 2023-01-01 onwards
- Creates RAG context file for explainability
- **Output:** `train_final.parquet`, `val_final.parquet`, `test_final.parquet`

## Pipeline Output

All processed data is saved to `data/processed/`:

```
data/processed/
├── train_final.parquet          # Training data
├── val_final.parquet            # Validation data
├── test_final.parquet           # Test data
├── rag_context.parquet          # News/text for RAG citations
├── sentiment_model.pkl          # Trained sentiment analyzer
├── *_summary.json               # Stage summaries
└── README.md                    # Data documentation
```

## Features Created

### Technical Indicators
- **Moving Averages:** SMA (5, 10, 20, 50), EMA (12, 26)
- **MACD:** MACD line, signal line, histogram
- **RSI:** 14-period Relative Strength Index
- **Bollinger Bands:** Upper, lower, width
- **Momentum:** 1, 5, 10, 20-day returns
- **Volatility:** 20-day rolling standard deviation

### Sentiment Features
- **Sentiment Score:** -1 (negative), 0 (neutral), 1 (positive)
- **Lag Features:** 1, 3, 7-day sentiment lags

### Volume Features
- **Volume Ratio:** Current volume / 20-day average
- **Volume SMA:** 20-day moving average

### Market Context
- **S&P 500 Return:** Daily market return

### Target Variable
- **Target:** buy (>2% return), hold (-2% to 2%), sell (<-2%)
- **Next Day Return:** Actual return for evaluation

## Configuration

### Adjust Number of Stocks

In `01_load_data.py`, line ~41:
```python
for csv_file in tqdm(csv_files[:100], desc="Loading prices"):  # Change 100 to desired number
```

### Adjust Train/Val/Test Split

In `05_merge_and_split.py`, line ~16:
```python
def create_temporal_split(df, train_end='2021-12-31', val_end='2022-12-31'):
```

### Adjust Target Thresholds

In `03_align_data.py`, line ~95:
```python
aligned_df.loc[aligned_df['next_day_return'] > 0.02, 'target'] = 'buy'  # Change 0.02 to desired threshold
aligned_df.loc[aligned_df['next_day_return'] < -0.02, 'target'] = 'sell'
```

## Troubleshooting

### Memory Issues
If you encounter memory errors:
1. Reduce number of stocks in Stage 1
2. Process data in batches
3. Use a machine with more RAM

### Missing Data
- Check `*_summary.json` files for data quality metrics
- Review alignment rates in `03_alignment_summary.json`
- Verify date ranges cover your target period

### Slow Performance
- Pipeline takes ~5-15 minutes for 100 stocks
- Stage 4 (feature engineering) is slowest
- Consider reducing technical indicator windows

## Next Steps

After running the pipeline:
1. **EDA:** Explore `data/processed/` files in notebooks
2. **Model Training:** Use `train_final.parquet` for agent training
3. **RAG Setup:** Use `rag_context.parquet` for citation/grounding
4. **Sentiment Model:** Load `sentiment_model.pkl` for inference
