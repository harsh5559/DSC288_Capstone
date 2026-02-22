# DSC288 Project Structure

Navigable layout of the Financial Explainability & Evaluation system.

## 1. Overview

- **Goal:** Multi-agent Graph RAG for explainable buy/hold/sell recommendations, with real data from Neo4j and Finnhub, and evaluation against ground truth using an LLM-as-judge.
- **Entry points:** Pipeline → Eval → Demo → Conclusion (see below).

## 2. Data & Config

| Path | Purpose |
|------|---------|
| `data/raw/finnhub_stocks/` | Finnhub API data (60 tickers, 3 sectors). `_sector_index.json` = ticker → sector. |
| `data/raw/fnspid/` | Price/news (FNSPID). |
| `data/processed/` | Pipeline outputs: `val_final.parquet`, `test_final.parquet`, `selected_tickers.json`. |
| `data/eval/` | Explainability prompts and results: `prompts_train.jsonl`, `prompts_test.jsonl`, `results_*.jsonl`. |
| `config/neo4j.yaml` | Neo4j connection. |
| `config/litellm_config.yaml` | LiteLLM proxy models. |

## 3. Pipeline (Train/Test Data)

1. **Load data**  
   `scripts/01_load_data.py` — Uses Finnhub/Neo4j tickers when available; writes `selected_tickers.json` and `*_raw.parquet`.

2. **Clean, align, features, split**  
   `scripts/02_clean_data.py` → `03_align_data.py` → `04_feature_engineering.py` → `05_merge_and_split.py`.

3. **Run full pipeline**  
   `scripts/run_pipeline.py` — Runs all stages; produces train/val/test parquet.

## 4. Explainability Evaluation

1. **Build prompt datasets (200+ train, 200+ test)**  
   `scripts/build_explainability_dataset.py`  
   - Reads Neo4j + processed data; builds prompts per sector with variants (`standard`, `earnings_focus`, `news_focus`).  
   - Output: `data/eval/prompts_train.jsonl`, `data/eval/prompts_test.jsonl`.

2. **Run evaluation (analyst LLM + judge)**  
   `scripts/run_explainability_eval.py`  
   - For each prompt: run analyst LLM → parse recommendation → run LLM judge.  
   - Compares to ground truth; writes `data/eval/results_*.jsonl`, `reports/eval_summary.json`, `reports/figures/eval/*.png`, and copies figures to `docs/figures/eval/` for the report.  
   - Also writes `docs/eval_summary_embed.js` for the HTML report.

3. **Export demo data for HTML**  
   `scripts/export_demo_data.py`  
   - Reads `results_test.jsonl`; writes `docs/demo_data.json` and `docs/demo_embed.js` for the live-demo section.

## 5. Agents & Server

| Path | Purpose |
|------|---------|
| `src/agents/graph_context.py` | Neo4j: stock context (profile, earnings, news, peers, recommendation). |
| `src/agents/data_context.py` | Processed data: get row by ticker/date, sample for judge, Finnhub ticker list. |
| `src/agents/prompt_builder.py` | Analyst prompts (incl. variants) and judge prompts. |
| `src/agents/llm_judge.py` | LLM-as-judge (sync/async); default model gpt-5.2-chat. |
| `src/agents/fin_memory.py` | Ingest Finnhub data into Neo4j. |
| `src/server/mcp_server.py` | MCP tools: analyze_stock, evaluate_model, evaluate_with_judge, search_news. |
| `src/evaluation/classification_eval.py` | Classification metrics (accuracy, macro F1, confusion matrix). |

## 6. Report & Demo (HTML) — GitHub Pages

- **Report (deploy):** **`index.html`** at repo root, for GitHub Pages. All assets live under **`assets/`**:
  - **assets/demo_embed.js** — Demo data (from `export_demo_data.py`).
  - **assets/eval_summary_embed.js** — Eval metrics (from `run_explainability_eval.py`).
  - **assets/figures/eval/*.png** — Eval plots (copied by `run_explainability_eval.py`).
  Sections: Background, Datasets, Pipeline, EDA, Sentiment, System, Graph RAG, Progress, Risks, Evaluation Analysis, Live Demo, Conclusion, Future Work, References.

- **Legacy:** `docs/index.html` still exists; scripts now write to `assets/` so the root site stays in sync.

## 7. Quick Commands

```bash
# Pipeline (real data)
python scripts/run_pipeline.py

# Neo4j ingest (for graph context)
python scripts/ingest_fin_memory.py

# Explainability: build prompts → run eval → export demo
python scripts/build_explainability_dataset.py
python scripts/run_explainability_eval.py
python scripts/export_demo_data.py
```

## 8. Conclusion & Future Work

- **Conclusion:** In `docs/index.html` section 13.  
- **Future work:** In `docs/index.html` section 14 (multi-agent debate, backtest, RAGAS, real-time API).
