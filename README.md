# DSC288 Capstone: Multi-Agent LLM Framework for Explainable Financial Decision Support

**Team Members**: Harsh Arya, Gabrielle Despaigne, Camila Paik, Raghav Vasappanavara
**Course**: DSC288 - Capstone Project
**Institution**: UC San Diego

## Project Overview

This project develops a multi-agent LLM-based system for financial decision support that prioritizes **explainability** over pure trading performance. The system provides buy/hold/sell recommendations with natural language explanations grounded in cited sources using Retrieval-Augmented Generation (RAG).

**Target Users:** Intermediate/beginner retail investors who value understanding financial recommendations over opaque numerical predictions.

**Key Innovation:** Unlike traditional financial models, our system uses specialized agents (fundamental analyst, news/sentiment analyst, technical analyst, optimistic/cautious viewpoints) to generate interpretable recommendations with data provenance.

## Current Status

**Week 2 Milestone (February 2026)** - Completed
- Finnhub-aligned stock universe: 60 tickers across 3 sectors (finance, semiconductor, biotech)
- Data pipeline implemented (4 stages, leakage-free)
- Comprehensive EDA with 12 analysis sections and 10 output artifacts
- Feature engineering (technical indicators, Finnhub fundamentals, market-relative features)
- Normalization fitted on train split only (no leakage)
- ~440K observations across 58 tickers with FNSPID price history (2009-2023)
- Ready for model training phase

## Stock Universe

60 tickers sourced from **Finnhub** across three high-activity sectors:

| Sector | Tickers | Examples |
|--------|---------|----------|
| Finance | 20 | JPM, GS, V, MA, BAC |
| Semiconductor | 20 | NVDA, AMD, TSM, AVGO, QCOM |
| Biotech | 20 | AMGN, GILD, REGN, VRTX, MRNA |

Historical OHLCV prices loaded from **FNSPID** for the 58 tickers with available price history (2 tickers lack FNSPID coverage due to recent IPOs).

## Data Pipeline

We have implemented a 4-stage data pipeline that integrates structured market data with unstructured financial text, centered on the Finnhub universe:

**Stage 1: Load & Align on Finnhub Universe** - Loads 5 data sources, aligns on 60-ticker universe
**Stage 2: Clean** - Handles outliers (34 removed at >50% threshold), nulls, duplicates
**Stage 3: Temporal Alignment + Target Labels** - Merges news with prices, adds market context, creates buy/hold/sell targets (fixed ±2%)
**Stage 4: Feature Engineering + Normalization** - Creates technical indicators, Finnhub fundamentals; normalizes via scalers fitted on train split only

**Pipeline Output:**
- ~440K observations (stock-day records)
- 58 stock tickers (Finnhub universe matched to FNSPID)
- 3 sectors (finance, semiconductor, biotech)
- 2009-2023 time period
- Technical + fundamental + market-relative features
- Temporal split: train (2009-2021), validation (2022), test (2023)

## Data Sources

All datasets have been downloaded and are stored locally in `data/raw/` (gitignored due to size).

| Dataset | Source | Description |
|---------|--------|-------------|
| **Finnhub** (Primary) | [Finnhub API](https://finnhub.io/) | 60 tickers: profiles, earnings, financials, news, sentiment, recommendations |
| FNSPID Stock Prices | [HuggingFace](https://huggingface.co/datasets/Zihan1004/FNSPID) | OHLCV prices for 58 Finnhub-matched tickers (Oct 2009 - Dec 2023) |
| Financial Phrasebank | [HuggingFace](https://huggingface.co/datasets/takala/financial_phrasebank) | 2,264 sentences (AllAgree) for FinBERT sentiment validation |
| S&P 500 | [Yahoo Finance](https://finance.yahoo.com/quote/%5EGSPC/history/) | Market context index (1999-2023) |
| FinQA | [GitHub](https://github.com/czyssrs/FinQA) | Financial Q&A pairs for evaluating reasoning faithfulness |

## Exploratory Data Analysis

Comprehensive EDA in a single notebook (`eda/01_EDA.ipynb`) covering 12 analysis sections:

| Section | Topic | TA Comment Addressed |
|---------|-------|---------------------|
| 1 | Setup & stock universe | - |
| 2 | Load & align price history | 4.1 (reproducible stock selection) |
| 3 | Data quality | - |
| 4 | Outlier analysis | 1.2 (50% threshold justification) |
| 5 | Target variable | 1.3 (buy/hold/sell thresholds) |
| 6 | Finnhub fundamentals | - |
| 7 | Phrasebank sentiment baseline | 3.1 (sentiment pipeline definition) |
| 8 | FinQA | 4.4 (connection to explanations) |
| 9 | S&P 500 correlation | 2.2 (correlation meaningfulness) |
| 10 | Temporal analysis | - |
| 11 | Anomaly summary | 2.1 (concrete anomaly table) |
| 12 | Critical insights | - |

**Key Findings:**
- **Outliers:** 34 records removed at >50% daily change threshold (all data errors in curated Finnhub universe)
- **S&P 500 Correlation:** Pearson r = +0.023 is misleading for categorical targets; MI = 0.0875 nats (~10% of target info), chi-squared p ≈ 0 confirm real signal
- **Sector Differences:** Biotech has highest volatility; finance is most stable
- **Sentiment Pipeline:** FinBERT → score [-1, +1] → mean per stock-day, validated on Phrasebank
- **Target Distribution:** ~15% buy, ~70% hold, ~15% sell (fixed ±2% thresholds)

**Output artifacts:** 8 PNG visualizations + 1 JSON insights summary + 1 CSV anomaly table in `eda/outputs/`.

## Feature Engineering

Based on EDA findings, we engineer features across three categories:

**Technical Indicators:** SMA-5/20/50, momentum-5/20, volatility-20, volume ratio, price-to-SMA ratios
**Finnhub Fundamentals:** Earnings surprise, sentiment score, sector (Ball & Brown, 1968)
**Market-Relative:** S&P 500 return, excess return, market direction indicators

Normalization: MinMaxScaler for prices, StandardScaler for volume/returns (per ticker) — fitted on train split only to prevent leakage.

## Repository Structure

```
.
├── data/
│   ├── raw/                              # Original datasets (gitignored)
│   │   ├── finnhub_stocks/               # Finnhub API data (60 tickers)
│   │   ├── fnspid/                       # FNSPID price history
│   │   ├── financial_phrasebank/
│   │   ├── finqa/
│   │   └── yahoo_sp500/
│   └── processed/                        # Pipeline outputs (gitignored)
├── scripts/                              # Data pipeline scripts
│   ├── 01_load_data.py                   # Stage 1: Load raw data
│   ├── 02_clean_data.py                  # Stage 2: Clean data
│   ├── 03_align_data.py                  # Stage 3: Temporal alignment
│   ├── 04_feature_engineering.py         # Stage 4: Feature engineering
│   ├── run_pipeline.py                   # Pipeline orchestrator
│   └── README.md                         # Scripts documentation
├── src/                                  # System implementation
│   ├── server/                           # LiteLLM proxy & MCP server
│   ├── agents/                           # Multi-agent system (Phase 2)
│   └── evaluation/                       # Evaluation pipeline (Phase 4)
├── eda/                                  # Exploratory data analysis
│   ├── 01_EDA.ipynb                      # Canonical EDA notebook (12 sections)
│   ├── run_eda.py                        # Executes notebook, saves outputs
│   └── outputs/                          # Generated plots and summaries
├── config/
│   └── litellm_config.yaml               # LiteLLM proxy model configuration
├── docs/
│   └── index.html                        # GitHub Pages progress report
├── reports/                              # Documentation and reports
│   ├── PLAN.md                           # End-to-end implementation plan
│   ├── PIPELINE_SUMMARY.md              # Pipeline documentation
│   ├── Addressing_TA_Comments.md        # Response plan for TA feedback
│   ├── DSC288_Progress_Report_Group10.md # Progress report (Markdown)
│   └── DSC288_Progress_Report.html      # Progress report (styled HTML)
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

This executes all 4 stages sequentially:
1. Loads data from `data/raw/`, aligns on Finnhub universe
2. Cleans data (outliers, nulls, duplicates)
3. Aligns news with prices, creates buy/hold/sell targets
4. Engineers features and normalizes (scalers fitted on train only)

### Run EDA
```bash
python eda/run_eda.py                  # Run full EDA pipeline end-to-end
python eda/run_eda.py --check          # Verify data exists before running
```
Or open `eda/01_EDA.ipynb` interactively in Jupyter.

### Server Management
```bash
python src/server/manage.py start      # Start LiteLLM proxy
python src/server/manage.py status     # Check status
python src/server/manage.py test       # Run test suite
python src/server/manage.py stop       # Stop server
```

## Evaluation Plan

| Category | Metric | Purpose |
|----------|--------|---------|
| Classification | **Macro F1** (primary) | Treats all three classes equally despite ~70% hold imbalance |
| Classification | Per-class Precision / Recall | Reveals bias toward "hold" predictions |
| Classification | Confusion Matrix | Shows cost of wrong predictions (BUY vs SELL misclassification) |
| Trading | Simulated cumulative return | Does following signals make money on the 2023 test set? |
| Explanation | Citation correctness | Does the cited article support the stated claim? |
| Explanation | RAGAS faithfulness | No hallucination — only info from retrieved sources |
| Explanation | FinQA reasoning accuracy | Tests grounded numerical reasoning over financial tables |

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total Observations | ~440K |
| Stock Tickers | 58 (of 60 Finnhub universe) |
| Sectors | 3 (finance, semiconductor, biotech) |
| Time Period | Oct 2009 - Dec 2023 |
| Integrated Datasets | 5 (Finnhub, FNSPID, Phrasebank, S&P 500, FinQA) |
| Outliers Removed | 34 (>50% daily change, all data errors) |
| Target Distribution | ~15% buy, ~70% hold, ~15% sell |
| Strongest Predictor | S&P 500 return (MI = 0.0875 nats, ~10% of target info) |
| EDA Artifacts | 10 output files (8 PNG + 1 JSON + 1 CSV) |

## Next Steps (Post Week 2 Milestone)

1. **Sentiment Model Training** - Fine-tune FinBERT on Financial Phrasebank data
2. **Multi-Agent Implementation** - Build agent framework using OpenAI API
3. **RAG System** - Implement retrieval-augmented generation for grounding explanations
4. **Evaluation** - Temporal consistency, baseline comparison, explanation faithfulness

## References

### Datasets
- Finnhub: https://finnhub.io/
- FNSPID: https://github.com/Zdong104/FNSPID_Financial_News_Dataset
- Financial Phrasebank: https://huggingface.co/datasets/takala/financial_phrasebank
- FinQA: https://github.com/czyssrs/FinQA
- Yahoo Finance: https://finance.yahoo.com

### Related Work
- Ball & Brown (1968) — Earnings surprise as predictor of abnormal returns
- TradingAgents: https://github.com/TauricResearch/TradingAgents
- Multi-agent systems for financial analysis
- RAG for explainable AI

## License

Educational project for DSC288 Capstone course at UC San Diego.

## Contact

For questions about this project, please contact the team members through the course instructor.
