# DSC288 Capstone: Multi-Agent LLM Framework for Explainable Financial Decision Support

**Team Members**: Harsh Arya, Gabrielle Despaigne, Camila Paik, Raghav Vasappanavara
**Course**: DSC288 - Capstone Project
**Institution**: UC San Diego

## Project Overview

This project develops a multi-agent LLM-based system for financial decision support that prioritizes **explainability** over pure trading performance. The system provides buy/hold/sell recommendations with natural language explanations grounded in cited sources using Retrieval-Augmented Generation (RAG).

**Target Users:** Intermediate/beginner retail investors who value understanding financial recommendations over opaque numerical predictions.

**Key Innovation:** Unlike traditional financial models, our system uses specialized agents (fundamental analyst, news/sentiment analyst, technical analyst, optimistic/cautious viewpoints) to generate interpretable recommendations with data provenance.

## Current Status

**Week 2 Milestone (January 2026)** - Completed
- Data pipeline implemented (5 stages, leakage-free)
- Exploratory data analysis completed
- Feature engineering (technical indicators & market-relative features)
- Normalization fitted on train split only (Stage 5, no leakage)
- 262,257 observations across 100 stocks (2009-2023)
- Ready for model training phase

## Data Pipeline

We have implemented a 5-stage data pipeline that integrates structured market data with unstructured financial text:

**Stage 1: Data Loading** - Loads 5 data sources into standardized parquet format
**Stage 2: Data Cleaning** - Handles NULLs, duplicates, outliers, date formats
**Stage 3: Temporal Alignment** - Merges news with prices, adds market context, creates targets
**Stage 4: Feature Engineering** - Creates 9 technical indicators and market-relative features (un-normalized)
**Stage 5: Train/Val/Test Split** - Temporal split; normalizes via scalers fitted on train only (no leakage)

**Pipeline Output:**
- 262,257 observations (stock-day records)
- 100 stock tickers
- 2009-2023 time period (14.2 years)
- 35 total features (16 original + 19 engineered)
- Runtime: ~3 minutes for validation

**Documentation:** See `PIPELINE_SUMMARY.md` for complete pipeline details and validation results.

## Data Sources

All datasets have been downloaded and are stored locally in `data/raw/` (gitignored due to size).

| Dataset | Source | Date Range | Subset Rule |
|---------|--------|-----------|-------------|
| FNSPID Stock Prices | [HuggingFace](https://huggingface.co/datasets/Zihan1004/FNSPID) | Oct 2009 – Dec 2023 | First 100 tickers alphabetically (deterministic, no random sampling) |
| FNSPID News | Same dataset | Oct 2009 – Dec 2023 | All articles for the 100 selected tickers |
| Financial Phrasebank | [HuggingFace](https://huggingface.co/datasets/takala/financial_phrasebank) | Static | All 2,264 sentences (`sentences_allagree`) |
| Yahoo S&P 500 | [Yahoo Finance](https://finance.yahoo.com/quote/%5EGSPC/history/) | Jan 1999 – Dec 2023 | Full index history (86.4% coverage) |
| FinQA | [GitHub](https://github.com/czyssrs/FinQA) | Static | Train + validation + test splits |

The selected ticker list is saved to `data/processed/selected_tickers.json` for full reproducibility.

## Exploratory Data Analysis

Comprehensive EDA covering all rubric requirements:
- **Data Quality:** 262K observations, minimal missing values in critical fields
- **Distributions:** Right-skewed prices, high volatility (34.7% daily std)
- **Outliers:** 9.67% price outliers, 1.7% extreme returns (>10% moves)
- **Correlations:** S&P 500 return strongest predictor (Pearson r = +0.023 deflated by categorical target; MI = 0.0875 nats, ~10% of target info; chi-squared p ≈ 0)
- **Key Insight:** 10% more extreme moves on days with news

**Documentation:** See `EDA_REPORT.md` for complete analysis with 7 visualizations and 15 data tables.

## Feature Engineering

Based on EDA findings, we engineered 19 features:

**Technical Indicators (9):** SMA-5/20/50, momentum-5/20, volatility-20, volume ratio, price-to-SMA ratios
**Market-Relative (4):** S&P 500 return, excess return, market direction indicators
**Normalization (6):** MinMaxScaler for prices, StandardScaler for volume/returns (per ticker) — applied in Stage 5, fitted on train split only to prevent leakage

Each feature is justified by specific EDA findings (see `EDA_REPORT.md`).

## Repository Structure

```
.
├── data/
│   ├── raw/                              # Original datasets (gitignored)
│   │   ├── yahoo_sp500/
│   │   ├── fnspid/
│   │   ├── financial_phrasebank/
│   │   └── finqa/
│   └── processed/                        # Pipeline outputs (gitignored)
│       ├── data_aligned.parquet          # Stage 3 output (262K records)
│       ├── data_engineered.parquet       # Stage 4 output (35 features, un-normalized)
│       ├── train_final.parquet           # Stage 5 output: training split (normalized)
│       ├── val_final.parquet             # Stage 5 output: validation split (normalized)
│       ├── test_final.parquet            # Stage 5 output: test split (normalized)
│       └── *_summary.json                # Pipeline statistics
├── scripts/                              # Data pipeline scripts
│   ├── 01_load_data.py                   # Stage 1: Load raw data
│   ├── 02_clean_data.py                  # Stage 2: Clean data
│   ├── 03_align_data.py                  # Stage 3: Temporal alignment
│   ├── 04_feature_engineering.py         # Stage 4: Feature engineering
│   ├── 05_merge_and_split.py             # Stage 5: Train/val/test split
│   ├── run_pipeline.py                   # Pipeline orchestrator
│   └── README.md                         # Scripts documentation
├── src/                                 # System implementation
│   ├── server/                          # LiteLLM proxy & MCP server
│   │   ├── manage.py                    # Server management (start/stop/test/logs)
│   │   ├── _serve.py                    # Internal server process
│   │   └── mcp_server.py               # MCP server for Cursor integration
│   ├── agents/                          # Multi-agent system (Phase 2)
│   └── evaluation/                      # Evaluation pipeline (Phase 4)
├── eda/                                  # Exploratory data analysis
│   ├── 01_EDA.ipynb                      # EDA notebook (interactive)
│   ├── run_eda.py                        # Consolidated EDA runner script
│   └── outputs/                          # Generated plots and summaries
├── logs/                                 # Agent and server logs (gitignored)
├── reports/                              # All documentation and reports
│   ├── PLAN.md                           # End-to-end implementation plan
│   ├── PIPELINE_SUMMARY.md              # Pipeline documentation
│   ├── EDA_REPORT.md                    # EDA with plots and tables
│   ├── Addressing_TA_Comments.md        # Response plan for TA feedback
│   ├── DSC288_Progress_Report_Group10.md # Progress report
│   └── Progress_Report_1/              # Milestone 1 archived docs
├── litellm_config.yaml                   # LiteLLM proxy model configuration
├── requirements.txt                      # Python dependencies
└── README.md                             # This file
```

## How to Run

### Prerequisites
```bash
pip install -r requirements.txt
```

### Run the Complete Pipeline
```bash
python scripts/run_pipeline.py
```

This executes all 5 stages sequentially:
1. Loads data from `data/raw/`
2. Cleans and processes data
3. Aligns news with prices, creates targets
4. Engineers features (technical indicators, un-normalized)
5. Splits into train/val/test and normalizes (scalers fitted on train only)

**Output:** `data/processed/train_final.parquet`, `val_final.parquet`, `test_final.parquet`

### Run Individual Stages
```bash
python scripts/01_load_data.py
python scripts/02_clean_data.py
python scripts/03_align_data.py
python scripts/04_feature_engineering.py
python scripts/05_merge_and_split.py
```

### Run EDA Pipeline
```bash
python eda/run_eda.py                  # Run full EDA pipeline end-to-end
python eda/run_eda.py --check          # Verify data exists before running
```
Or open `eda/01_EDA.ipynb` interactively in Jupyter. See `reports/EDA_REPORT.md` for the full analysis writeup.

### Server Management
```bash
python src/server/manage.py start      # Start LiteLLM proxy
python src/server/manage.py status     # Check status
python src/server/manage.py test       # Run test suite
python src/server/manage.py stop       # Stop server
```

## Key Documentation Files

| File | Description |
|------|-------------|
| `reports/PLAN.md` | End-to-end implementation plan and architecture |
| `reports/PIPELINE_SUMMARY.md` | Complete pipeline description with validation results |
| `reports/EDA_REPORT.md` | Comprehensive EDA with 7 plots and 15 tables |
| `reports/Addressing_TA_Comments.md` | Response plan for TA milestone 2 feedback |
| `scripts/README.md` | Detailed documentation for each pipeline script |

## Dependencies

- Python 3.8+
- pandas, numpy
- scikit-learn (normalization in Stage 5, feature engineering)
- yfinance (Yahoo Finance data)
- datasets (HuggingFace)
- matplotlib, seaborn (visualization)
- tqdm (progress bars)

See `requirements.txt` for complete list with versions.

## Evaluation Plan

| Category | Metric | Purpose |
|----------|--------|---------|
| Classification | **Macro F1** (primary) | Treats all three classes equally despite 70% hold imbalance |
| Classification | Per-class Precision / Recall | Reveals bias toward "hold" predictions |
| Classification | Confusion Matrix | Shows cost of wrong predictions (BUY vs SELL misclassification) |
| Trading | Simulated cumulative return | Does following signals make money on the 2023 test set? |
| Explanation | Citation correctness | Does the cited article support the stated claim? |
| Explanation | Faithfulness | No hallucination — only info from retrieved sources |

## Next Steps (Post Week 2 Milestone)

1. **Sentiment Model Training** - Fine-tune on Financial Phrasebank data
3. **Multi-Agent Implementation** - Build agent framework using OpenAI API
4. **RAG System** - Implement retrieval-augmented generation for grounding explanations
5. **Evaluation** - Temporal consistency, baseline comparison, explanation faithfulness

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total Observations | 262,257 |
| Stock Tickers | 100 |
| Time Period | Oct 2009 - Dec 2023 (14.2 years) |
| Total Features | 35 (16 original + 19 engineered) |
| News Coverage | 1.46% (3,821 stock-days) |
| S&P 500 Coverage | 86.4% |
| Target Distribution | 70% hold, 15% sell, 15% buy |
| Strongest Predictor | S&P 500 return (MI = 0.0875 nats, ~10% of target info) |

## References

### Datasets
- FNSPID: https://github.com/Zdong104/FNSPID_Financial_News_Dataset
- Financial Phrasebank: https://huggingface.co/datasets/takala/financial_phrasebank
- FinQA: https://github.com/czyssrs/FinQA
- Yahoo Finance: https://finance.yahoo.com

### Related Work
- TradingAgents: https://github.com/TauricResearch/TradingAgents
- Multi-agent systems for financial analysis
- RAG for explainable AI

## License

Educational project for DSC288 Capstone course at UC San Diego.

## Contact

For questions about this project, please contact the team members through the course instructor.
