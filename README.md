# DSC288 Capstone: Multi-Agent LLM Framework for Explainable Financial Decision Support

**Team Members**: Harsh Arya, Gabrielle Despaigne, Camila Paik, Raghav Vasappanavara
**Course**: DSC288 - Capstone Project
**Institution**: UC San Diego

## Project Overview

This project develops a multi-agent LLM-based system for financial decision support that prioritizes **explainability** over pure trading performance. The system provides buy/hold/sell recommendations with natural language explanations grounded in cited sources using Retrieval-Augmented Generation (RAG).

**Target Users:** Intermediate/beginner retail investors who value understanding financial recommendations over opaque numerical predictions.

**Key Innovation:** Unlike traditional financial models, our system uses specialized agents (fundamental analyst, news/sentiment analyst, technical analyst, optimistic/cautious viewpoints) to generate interpretable recommendations with data provenance.

> **Important — Runtime Requirements**
>
> This project was developed and executed inside **Docker containers on a local laptop**, with network hooks to the **OpenAI API** via a LiteLLM proxy. The LLM agents, evaluation pipeline, and MCP server all require a valid OpenAI API key (`OPENAI_API_KEY`). **The code will not run without OpenAI API keys.**
>
> The included results, evaluation figures, and HTML report (`index.html`) represent our completed outputs and can be reviewed without running anything. See `REPO_EXPLANATION.txt` for a detailed walkthrough of the entire system.

## Project Status (March 2026 — Final)

- 5-stage data pipeline (load, clean, align, feature engineering, split+normalize) — leakage-free
- Neo4j knowledge graph with 60 Finnhub tickers (sectors, earnings, news, recommendations, peers)
- Graph RAG agent system: Neo4j context retrieval, prompt construction (3 variants), analyst LLM
- LLM-as-judge evaluation scoring faithfulness, relevance, consistency, and correctness
- Hyperparameter tuning sweep (prompt strategy, max tokens, model, temperature)
- Classification evaluation with baselines (accuracy, balanced accuracy, macro F1)
- LiteLLM proxy server with model routing and MCP server for Cursor IDE integration
- GitHub Pages HTML report with evaluation results, comparison plots, and live demo
- Comprehensive EDA (12 sections, 10 output artifacts)
- ~440K observations across 58 tickers with FNSPID price history (2009–2023)

## Stock Universe

60 tickers sourced from **Finnhub** across three high-activity sectors:

| Sector | Tickers | Examples |
|--------|---------|----------|
| Finance | 20 | JPM, GS, V, MA, BAC |
| Semiconductor | 20 | NVDA, AMD, TSM, AVGO, QCOM |
| Biotech | 20 | AMGN, GILD, REGN, VRTX, MRNA |

Historical OHLCV prices loaded from **FNSPID** for the 58 tickers with available price history (2 tickers lack FNSPID coverage due to recent IPOs).

## Data Pipeline

A 5-stage pipeline integrates structured market data with unstructured financial text, centered on the Finnhub universe:

**Stage 1: Load** (`scripts/01_load_data.py`) — Loads 5 data sources, aligns on 60-ticker Finnhub universe
**Stage 2: Clean** (`scripts/02_clean_data.py`) — Handles outliers (34 removed at >50% threshold), nulls, duplicates
**Stage 3: Temporal Alignment** (`scripts/03_align_data.py`) — Merges news with prices, adds S&P 500 market context, creates buy/hold/sell targets (fixed ±2%)
**Stage 4: Feature Engineering** (`scripts/04_feature_engineering.py`) — Creates technical indicators and market-relative features; normalization deferred to Stage 5
**Stage 5: Split + Normalize** (`scripts/05_merge_and_split.py`) — Temporal train/val/test split, normalization fitted on train only (no leakage), forward-fill per split

**Pipeline Output:**
- ~440K observations (stock-day records)
- 58 stock tickers (Finnhub universe matched to FNSPID)
- 3 sectors (finance, semiconductor, biotech)
- 2009-2023 time period
- Technical + fundamental + market-relative features
- Temporal split: train (2009–2021, ~129K rows), validation (2022, ~14K rows), test (2023, ~6K rows)

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

## Fin Memory (Neo4j Knowledge Graph)

Finnhub master data is ingested into a **Neo4j** graph for explainability: sectors, stocks, profiles, earnings, news, recommendations, and peer links. The **fin_memory** agent builds and updates this graph via MERGE (idempotent).

**Entities:** Sector (3), Stock (60), Earnings (220), NewsArticle (6,960), Recommendation (232).  
**Relationships:** IN_SECTOR, HAS_EARNINGS, MENTIONED_IN, HAS_RECOMMENDATION, PEERS_WITH.

**Documentation:** See [reports/FIN_MEMORY_IMPLEMENTATION.md](reports/FIN_MEMORY_IMPLEMENTATION.md) for how entities and relationships are built, and how they were verified.

## Feature Engineering

Based on EDA findings, we engineer features across three categories:

**Technical Indicators:** SMA-5/20/50, momentum-5/20, volatility-20, volume ratio, price-to-SMA ratios
**Finnhub Fundamentals:** Earnings surprise, sentiment score, sector (Ball & Brown, 1968)
**Market-Relative:** S&P 500 return, excess return, market direction indicators

Normalization: MinMaxScaler for prices, StandardScaler for volume/returns (per ticker) — fitted on train split only to prevent leakage.

## Repository Structure

```
.
├── config/
│   ├── litellm_config.yaml               # LiteLLM proxy model definitions + aliases
│   └── neo4j.yaml                        # Neo4j connection settings
├── data/
│   ├── raw/                              # Original datasets (gitignored)
│   │   ├── finnhub_stocks/               # 60 tickers × 9 endpoints (JSON)
│   │   ├── fnspid/                       # OHLCV prices + news articles
│   │   ├── financial_phrasebank/         # Sentiment-labeled sentences
│   │   ├── finqa/                        # Financial QA benchmark
│   │   └── yahoo_sp500/                  # S&P 500 daily index
│   └── processed/                        # Pipeline outputs (gitignored)
├── scripts/
│   ├── run_pipeline.py                   # Orchestrates all 5 stages
│   ├── 01_load_data.py                   # Stage 1: Load raw data
│   ├── 02_clean_data.py                  # Stage 2: Clean data
│   ├── 03_align_data.py                  # Stage 3: Temporal alignment
│   ├── 04_feature_engineering.py         # Stage 4: Feature engineering
│   ├── 05_merge_and_split.py            # Stage 5: Split + normalize
│   ├── download_all_data.py             # Parallel downloader (all sources)
│   ├── ingest_fin_memory.py             # Start Neo4j + full graph ingest
│   ├── generate_hp_comparison_plots.py  # HP baseline vs tuned plots
│   ├── generate_hp_demo_data.py         # HP demo data for HTML report
│   ├── _dl_stocks.py                    # Finnhub API downloader
│   ├── _dl_fnspid.py                    # FNSPID HuggingFace downloader
│   ├── _dl_phrasebank.py               # Phrasebank downloader
│   ├── _dl_finqa.py                     # FinQA GitHub downloader
│   └── README.md                        # Pipeline documentation
├── src/
│   ├── agents/
│   │   ├── graph_context.py             # Neo4j context retrieval for prompts
│   │   ├── data_context.py              # Market data from processed parquets
│   │   ├── prompt_builder.py            # Analyst + judge prompt construction
│   │   ├── llm_judge.py                # LLM-as-judge scoring (4 dimensions)
│   │   └── fin_memory.py               # Finnhub → Neo4j ingestion CLI
│   ├── evaluation/
│   │   ├── explainability.py            # Main eval pipeline (build/run/export)
│   │   ├── hyperparam_sweep.py          # HP tuning (prompt × tokens × model)
│   │   └── classification_eval.py       # Classification metrics + baselines
│   └── server/
│       ├── manage.py                    # Server CLI (start/stop/status/test)
│       ├── _serve.py                    # LiteLLM proxy launcher
│       └── mcp_server.py               # MCP tool server for Cursor IDE
├── eda/
│   ├── 01_EDA.ipynb                     # Main EDA notebook (12 sections)
│   ├── run_eda.py                       # Programmatic notebook executor
│   └── outputs/                         # 8 PNGs + 1 JSON + 1 CSV
├── assets/
│   ├── figures/eval/                    # Evaluation + HP comparison plots (PNG)
│   ├── eval_summary_embed.js            # Metrics data for HTML report
│   ├── demo_hp_embed.js                # Demo entries for HTML report
│   └── hyperparam_embed.js             # HP sweep results for HTML report
├── reports/                             # Documentation and reports
│   ├── PLAN.md                          # End-to-end implementation plan
│   ├── FIN_MEMORY_IMPLEMENTATION.md    # Neo4j graph documentation
│   ├── PIPELINE_SUMMARY.md             # Pipeline documentation
│   ├── NEO4J_BROWSER_QUERIES.md        # Example Cypher queries
│   ├── Addressing_TA_Comments.md       # Response to TA feedback
│   ├── eval_summary.json               # Evaluation results (JSON)
│   └── hyperparam_results.json         # HP sweep results (JSON)
├── index.html                           # GitHub Pages report (main deliverable)
├── requirements.txt                     # Python dependencies
├── PROJECT_STRUCTURE.md                 # Navigable project layout
├── REPO_EXPLANATION.txt                 # Detailed system documentation
└── README.md                            # This file
```

## How to Run

> **Note:** This system was developed and run on a laptop using Docker Desktop and the OpenAI API. **You will need valid API keys to run any LLM-dependent code.** The evaluation results and HTML report are included in the repo and can be reviewed without running anything.

### Prerequisites

| Requirement | Purpose |
|-------------|---------|
| Python 3.10+ | Runtime |
| Docker Desktop | Neo4j runs as a Docker container |
| OpenAI API key | All LLM calls (analyst, judge, embeddings) go through OpenAI |

API keys are stored in a `.key` file at the repo root (gitignored), one `KEY=VALUE` per line:

```
OPENAI_API_KEY=sk-...
FINNHUB_API_KEY=...
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

### 1. Data Pipeline

```bash
python scripts/run_pipeline.py
```

Runs all 5 stages sequentially: load → clean → align → feature engineering → split + normalize. Requires raw data in `data/raw/`.

### 2. Neo4j Knowledge Graph

```bash
python scripts/ingest_fin_memory.py             # Start Neo4j (Docker) + full ingest
python src/agents/fin_memory.py memorize         # Ingest all 60 tickers
python src/agents/fin_memory.py stats            # Graph node/edge counts
```

### 3. Evaluation Pipeline (requires OpenAI API key)

```bash
python -m src.evaluation.explainability build    # Build prompts from Neo4j + data
python -m src.evaluation.explainability run      # Run analyst LLM + judge scoring
python -m src.evaluation.explainability export   # Export demo data for HTML report
python -m src.evaluation.hyperparam_sweep        # HP tuning sweep
```

### 4. Server Management

```bash
python src/server/manage.py start                # Start LiteLLM proxy + Neo4j
python src/server/manage.py status               # Check service status
python src/server/manage.py test                 # LiteLLM test suite
python src/server/manage.py stop                 # Shut down services
```

### 5. EDA

```bash
python eda/run_eda.py                            # Run full EDA pipeline
python eda/run_eda.py --check                    # Verify data exists
```

Or open `eda/01_EDA.ipynb` interactively in Jupyter.

For a detailed walkthrough of every script and module, see `REPO_EXPLANATION.txt`.

## Evaluation Results

The evaluation pipeline uses an **LLM-as-judge** approach: an analyst LLM generates recommendations from Neo4j context, then a separate GPT-5.2-chat judge scores each output on four dimensions (1–5 scale).

**Classification (50 test prompts):**

| Metric | Train | Test |
|--------|-------|------|
| Accuracy | ~52.5% | ~60% |
| Balanced Accuracy | Low (BUY bias) | Low (BUY bias) |

The model exhibits a strong **BUY bias** — nearly all predictions are BUY regardless of ground truth, making it effectively a majority-class classifier. Test accuracy is inflated by COVID-era signals aligning with the BUY tendency.

**Explanation Quality (LLM judge, 1–5 scale):**

| Dimension | Score | Interpretation |
|-----------|-------|----------------|
| Relevance | 4–5 | Explanations are on-topic |
| Consistency | 4–5 | Reasoning is internally coherent |
| Faithfulness | ~1.0–1.3 | **Critically low** — model fabricates specific numbers not in context |

**Faithfulness is the most important finding:** the model hallucates statistics and analyst counts not present in the provided data. This cannot be fixed by prompt engineering alone and requires RAG constraints or citation enforcement.

**Hyperparameter Tuning:**
Best configuration (Chain-of-Thought prompt + 300 max tokens) achieved a **+10 percentage point accuracy improvement** over baseline while preserving explanation quality. Full results in `reports/hyperparam_results.json`.

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

## Future Work

1. **Multi-agent debate** — Multiple specialist agents (fundamental, sentiment, technical, optimistic, cautious) discussing before a synthesizer produces the final recommendation
2. **Real-time API integration** — Live Finnhub data instead of static JSON snapshots
3. **Full backtesting simulation** — Simulated portfolio returns from following model signals on the 2023 test set
4. **RAGAS faithfulness enforcement** — Citation constraints and retrieval-augmented decoding to eliminate hallucination
5. **FinBERT fine-tuning** — Fine-tune on Financial Phrasebank for domain-specific sentiment scoring

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
