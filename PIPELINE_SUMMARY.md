# Pipeline Summary for Progress Report

## Quick Reference

### What We Built
A 4-stage data pipeline that:
1. **Loads** financial data from 5 sources
2. **Cleans** data (removes NULLs, duplicates, outliers)
3. **Aligns** news with prices temporally, filtered to 2009-2023 (news-available period)
4. **Engineers features** with normalization and technical indicators

### Validation Results
✅ **Tested with:** 100 stocks, 20K news articles  
✅ **Runtime:** ~3 minutes total  
✅ **Output:** 262,257 aligned stock-day observations (2009-2023)  
✅ **Quality:** 93% data retention after cleaning  
✅ **Features:** 35 total (16 original + 19 engineered)  
✅ **Normalized:** Prices (min-max), volume & returns (z-score)

### Key Numbers for Report

| Metric | Value |
|--------|-------|
| Stock tickers | 100 |
| Total observations | 262,257 |
| Date range | 2009-2023 (14.2 years) |
| News articles | 9,721 (after cleaning) |
| News coverage | 1.46% (3,821 stock-days) |
| Prediction targets | Buy: 14.9%, Hold: 69.7%, Sell: 15.4% |
| Total features | 35 (16 original + 19 engineered) |
| Normalized features | 6 (prices, volume, returns) |
| Technical indicators | 9 (SMA, momentum, volatility) |

---

## Data Pipeline Section (For Report)

### Purpose
The goal of the pipeline is to align structured market data with relevant financial text during the period where both are available (2009-2023), so that the multi-agent LLM system can make explainable buy/hold/sell recommendations grounded in actual news sources via RAG.

### Pipeline Design
We designed and implemented a 4-stage pipeline that integrates multiple financial data sources:

**Stage 1 (Loading):** Loads raw data from FNSPID (stock prices + news), Financial Phrasebank (sentiment data), Yahoo Finance (S&P 500 market context), and FinQA (Q&A benchmarks). For validation, we sample 100 stocks and 20,000 news articles to ensure reasonable processing time.

**Stage 2 (Cleaning):** Handles NULL values through forward-filling for prices and dropping for missing critical fields; removes 951 outlier records with >50% daily price changes; removes 278 duplicate news articles; standardizes date formats across all sources; removes 7,711 records with non-positive prices and 23,388 with zero/negative volume.

**Stage 3 (Alignment):** **Filters to 2009-2023 period** where both stock prices AND news are available (critical for explainable recommendations); merges news articles with stock prices by (ticker, date); adds S&P 500 market context (86.4% coverage); creates prediction targets (buy/hold/sell) based on next-day returns using ±2% thresholds; ensures no look-ahead bias by using only historical data.

**Stage 4 (Feature Engineering & Normalization):** Normalizes price features using MinMaxScaler (0-1 range per ticker); standardizes volume and returns using StandardScaler (z-score per ticker); creates 9 technical indicators (SMA-5/20/50, momentum-5/20, volatility-20, volume ratio, price-to-SMA ratios); adds market-relative features (excess return, market direction indicators). Total: 35 features (16 original + 19 engineered).

### Data Merging
We combine historical stock price data with corresponding financial news articles from the same date/time period, sentiment scores derived from Financial Phrasebank analysis, and market-level context (S&P 500 performance). The merging is done on a (ticker, date) key, ensuring that all information available up to day T is used to make predictions for day T+1. **Critically, we filter to 2009-2023, the period where FNSPID news is available**, reducing the dataset from 428K to 262K observations but ensuring every record can potentially be explained using both technical analysis AND news content.

### Data Cleansing
We handle NULL values through forward-filling for prices and dropping for news if critical fields are missing; remove 951 outliers with >50% daily price changes (likely stock splits or errors); remove 278 duplicate news articles based on content; standardize all timestamps; remove 7,711 records with non-positive prices and 23,388 with zero/negative volume; clean HTML tags and normalize whitespace in news text.

### Data Augmentation/Enrichment
We create derived features including: next-day returns and targets (buy/hold/sell); news counts per stock-day; S&P 500 daily returns; 9 technical indicators (moving averages, momentum, volatility, volume ratios); price-to-SMA ratios; excess returns (stock return minus market return); market direction indicators.

### Data Normalization
All features are normalized for model training: **Price features** (open, high, low, close) are min-max scaled to [0,1] range per ticker to account for different price scales; **Volume** is standardized to z-scores per ticker to handle varying trading volumes; **Returns** are standardized to z-scores per ticker for consistent volatility measures. Normalization is done per ticker to preserve relative patterns while enabling cross-stock comparison.

### Description of Outputs
**Final Dataset:** Deduplicated records with one row per (ticker, date) combination containing aligned multi-modal data (prices + news + market context + technical indicators + normalized features). Time-series ordered to prevent data leakage. 

**Statistics:**
- **262,257 observations** across 100 stocks from October 2009 to December 2023 (14.2 years)
- **35 features:** 16 original (prices, volume, dates, news, market context) + 19 engineered (6 normalized + 9 technical + 4 market-relative)
- **Prediction targets:** buy (14.9%), hold (69.7%), sell (15.4%) based on next-day returns
- **News coverage:** 3,821 stock-days (1.46%) with news articles - reflects reality that not every stock has daily news
- **Market context:** 86.4% of records have S&P 500 data for market-relative analysis
- **Data retention:** 93% for stock prices, 49% for news (due to quality filtering)

**Files Generated:**
- `data_aligned.parquet` - Cleaned and aligned data (Stage 3 output)
- `data_engineered.parquet` - Feature-engineered and normalized data (Stage 4 output, ready for modeling)
- `*_summary.json` - Stage-by-stage statistics for pipeline validation

All intermediate outputs saved as Parquet files for efficient downstream processing.

---

## Pipeline Stages Detail

### Stage 1: Data Loading ✅
- **Script:** `scripts/01_load_data.py`
- **Input:** Raw CSV/JSON/TXT files from 5 sources
- **Output:** 5 parquet files with standardized schemas
- **Runtime:** ~2 minutes
- **Key Decision:** Sample 100 stocks and 20K news for validation

### Stage 2: Data Cleaning ✅
- **Script:** `scripts/02_clean_data.py`
- **Operations:** NULL handling, deduplication, outlier removal, format standardization
- **Output:** Cleaned parquet files (93% price retention, 49% news retention)
- **Runtime:** ~10 seconds
- **Key Metric:** 428,243 clean price records from 460,293 raw

### Stage 3: Temporal Alignment ✅
- **Script:** `scripts/03_align_data.py`
- **Operations:** 
  - **Filter to 2009-2023** (news-available period)
  - Merge news with prices
  - Add market context
  - Create prediction targets
- **Output:** `data_aligned.parquet` (262,257 records)
- **Runtime:** ~15 seconds
- **Key Decision:** Focus on period where we have BOTH prices AND news

### Stage 4: Feature Engineering & Normalization ✅
- **Script:** `scripts/04_feature_engineering.py`
- **Operations:**
  - Normalize prices (MinMaxScaler per ticker)
  - Standardize volume/returns (StandardScaler per ticker)
  - Add 9 technical indicators
  - Add 4 market-relative features
- **Output:** `data_engineered.parquet` (262,257 records, 35 features)
- **Runtime:** ~30 seconds
- **Key Achievement:** All features on comparable scales for modeling

### Stage 5: Train/Val/Test Split ⏳
- **Status:** Planned (not required for Week 2 progress report)
- **Design:** Temporal split (e.g., train: 2009-2019, val: 2020-2021, test: 2022-2023)
- **Purpose:** Prevent look-ahead bias in model evaluation

---

## Files Generated

### Validation Evidence:
- `PIPELINE_VALIDATION.md` - Full technical validation report
- `data/processed/*_summary.json` - Stage-by-stage statistics
- `data/processed/data_aligned.parquet` - Aligned dataset (Stage 3)
- `data/processed/data_engineered.parquet` - Feature-engineered dataset (Stage 4)

### For Inspection:
```python
import pandas as pd

# Load final engineered data
df = pd.read_parquet('data/processed/data_engineered.parquet')

print(f"Shape: {df.shape}")
print(f"Columns: {df.columns.tolist()}")
print(f"\nTarget distribution:")
print(df['target'].value_counts())
print(f"\nNormalized features:")
print([col for col in df.columns if '_norm' in col])
```

---

## Key Achievements

✅ **Data Integration:** Successfully merged 5 diverse financial data sources  
✅ **Quality Filtering:** 93% retention for core price data  
✅ **Temporal Alignment:** Aligned news with prices, filtered to news-available period (2009-2023)  
✅ **Feature Engineering:** 19 new features including normalized, technical, and market-relative  
✅ **Normalization:** All features on comparable scales (min-max for prices, z-score for volume/returns)  
✅ **No Data Leakage:** Temporal ordering preserved, only historical data used for predictions  
✅ **Scalability:** Pipeline tested with 100 stocks, can scale to full dataset  

---

## For Progress Report

### Summary Statement:
> "We implemented a 4-stage data pipeline that loads data from 5 financial sources, cleans and standardizes formats, aligns news with stock prices during the 2009-2023 period where both are available (critical for explainable recommendations), and engineers 19 new features with proper normalization. The final dataset contains 262,257 observations across 100 stocks with 35 features (6 normalized, 9 technical indicators, 4 market-relative), ready for multi-agent LLM model development."

### Key Evidence Files:
1. `PIPELINE_VALIDATION.md` - Comprehensive technical validation
2. `data/processed/*_summary.json` - Quantitative pipeline metrics
3. `data/processed/data_engineered.parquet` - Final model-ready dataset
4. `scripts/01-04_*.py` - Reproducible pipeline code
