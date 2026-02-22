# Implementation Plan: Multi-Agent Financial Decision Support System

**DSC288 Capstone — Group 10**
**Last updated:** February 2026

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     CURSOR IDE (User)                        │
│                                                              │
│  "Analyze AAPL"  ──── MCP Protocol ────►                     │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│              MCP SERVER  (server/mcp_server.py)              │
│                                                              │
│  Tools: analyze_stock · get_sentiment · technical_snapshot   │
│         search_news · backtest · evaluate_model              │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│              MULTI-AGENT ORCHESTRATOR                        │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ Technical  │  │ Sentiment  │  │Fundamental │             │
│  │ Analyst    │  │ Analyst    │  │ Analyst    │             │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘             │
│        │               │               │                     │
│        └───────┬───────┴───────┬───────┘                     │
│        ┌───────▼──────┐ ┌──────▼───────┐                     │
│        │  Optimistic  │ │   Cautious   │                     │
│        │  Viewpoint   │ │   Viewpoint  │                     │
│        └───────┬──────┘ └──────┬───────┘                     │
│                └───────┬───────┘                              │
│                ┌───────▼──────┐                               │
│                │  Synthesizer │ ──► Buy/Hold/Sell             │
│                │  (Decision)  │     + Explanation             │
│                └──────────────┘     + Citations              │
└──────────────────────────┬───────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │    LiteLLM Proxy :4000  │
              │                        │
              │  agent-reasoning: 4o   │
              │  agent-fast: 4o-mini   │
              │  embedder: emb-3-small │
              └────────────┬───────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                   DATA & RETRIEVAL LAYER                     │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌───────────┐                │
│  │ ChromaDB │   │  Neo4j   │   │  Parquet  │                │
│  │ (vectors)│   │ (graph)  │   │  (pipeline│                │
│  │          │   │          │   │   output) │                │
│  └──────────┘   └──────────┘   └───────────┘                │
└──────────────────────────────────────────────────────────────┘
```

---

## What We Have (completed)

| Component | Status | Location |
|-----------|--------|----------|
| 5-stage data pipeline | Done | `scripts/01-05_*.py` |
| 262K aligned stock-day records | Done | `data/processed/data_aligned.parquet` |
| 35 engineered features | Done | `data/processed/data_engineered.parquet` |
| Temporal train/val/test split (no leakage) | Done | `data/processed/{train,val,test}_final.parquet` |
| RAG context file (news lookup) | Done | `data/processed/rag_context.parquet` |
| EDA with 7 plots and statistical validation | Done | `EDA_REPORT.md`, `notebooks/01_EDA.ipynb` |
| TA feedback fully addressed (9/11 closed, 2 team decisions) | Done | `Addressing_TA_Comments.md` |
| OpenAI API key stored | Done | `.key` (gitignored) |
| LiteLLM config | Done | `litellm_config.yaml` |
| MCP server skeleton | Done | `server/mcp_server.py` |

---

## Phase 1: Sentiment & Retrieval Foundation

**Goal:** Build the two capabilities every agent depends on — understanding news sentiment, and retrieving relevant context from the dataset.

### 1A. Sentiment Model (FinBERT)

Fine-tune FinBERT on Financial Phrasebank (2,264 sentences, all-agree split) to produce a sentiment classifier that maps financial text to `{positive, neutral, negative}` with a confidence score.

**Why FinBERT over GPT:** Deterministic, free, runs locally, produces consistent scores for the same input. GPT is reserved for agent reasoning where creativity matters; sentiment scoring needs reproducibility.

```
Financial Phrasebank (2,264 sentences)
    │
    ▼
FinBERT base model (ProsusAI/finbert)
    │  fine-tune (3 epochs, lr=2e-5)
    ▼
finbert_sentiment.pt
    │
    ▼  apply to all 9,721 news articles in dataset
    │
sentiment_scores.parquet
    columns: ticker, date, article_idx, sentiment_label, sentiment_score, confidence
```

**Implementation:**

| Step | File | What It Does |
|------|------|-------------|
| 1 | `scripts/06_train_sentiment.py` | Fine-tune FinBERT on Phrasebank. Save model + classification report. |
| 2 | `scripts/07_score_sentiment.py` | Apply fine-tuned model to all news articles. For stock-days with multiple articles (concatenated with ` \| `), split on the separator and score each article individually. Save per-article scores AND per-stock-day aggregated scores (mean, min, max, count). |
| 3 | `scripts/08_enrich_features.py` | Merge sentiment scores into the engineered dataset. Add columns: `sentiment_mean`, `sentiment_min`, `sentiment_max`, `sentiment_std`, `pct_positive`, `pct_negative`. Re-run Stage 5 split + normalization with the new features. |

**Evaluation of sentiment model itself:**
- Held-out accuracy on Phrasebank test split (expect >85% on all-agree)
- Manual spot-check: sample 50 scored articles, read them, verify label makes sense

### 1B. RAG Vector Store (ChromaDB)

Build a vector store of all news articles so agents can retrieve relevant context by semantic similarity at inference time.

```
9,721 news articles (from rag_context.parquet)
    │
    ▼  split concatenated articles on ' | '
    │
~15,000 individual article chunks
    │
    ▼  embed with text-embedding-3-small (via LiteLLM)
    │
ChromaDB collection: "financial_news"
    metadata: {ticker, date, source, sentiment_label, sentiment_score}
```

**Implementation:**

| Step | File | What It Does |
|------|------|-------------|
| 1 | `scripts/09_build_vectorstore.py` | Split concatenated articles, embed via LiteLLM proxy, store in ChromaDB with metadata. Persist to `data/vectorstore/`. |
| 2 | `server/retriever.py` | Retrieval interface: `retrieve(query, ticker, date_range, top_k)` → returns articles with metadata. Supports both semantic search and metadata filtering. |

### 1C. Neo4j Knowledge Graph (optional, stretch)

Model relationships that flat retrieval can't capture:

```
(:Stock {ticker}) -[:HAS_PRICE_ON]-> (:TradingDay {date, close, volume, target})
(:Stock) -[:MENTIONED_IN]-> (:Article {text, sentiment, source})
(:Article) -[:PUBLISHED_ON]-> (:TradingDay)
(:Stock) -[:IN_SECTOR]-> (:Sector)
(:TradingDay) -[:MARKET_CONTEXT]-> (:MarketDay {sp500_return, direction})
```

Enables multi-hop queries like: "Find all negative articles about AAPL in weeks where the S&P 500 was also down." This feeds the Fundamental Analyst agent.

**Implementation:** `scripts/10_build_graph.py` — load parquet data into Neo4j, create nodes and relationships.

---

## Phase 2: Multi-Agent System

**Goal:** Build 6 specialized agents that collaborate to produce an explainable recommendation.

### Mental Model: How Sentiment Meets Price

The core insight the system must capture is **divergence** — when sentiment and price action disagree, that's where the signal is.

```
                    SENTIMENT
                 Positive  Negative
          ┌──────────┬──────────┐
  Price   │  ALIGNED │ DIVERGE  │
  Rising  │  (hold/  │ (caution │
          │   buy)   │  — sell?)│
          ├──────────┼──────────┤
  Price   │ DIVERGE  │ ALIGNED  │
  Falling │ (buy     │  (hold/  │
          │  signal?)│   sell)  │
          └──────────┴──────────┘
```

Each agent builds a piece of this mental model:

| Agent | What It Sees | Internal State It Builds |
|-------|-------------|-------------------------|
| **Technical Analyst** | Price, volume, SMAs, momentum, volatility | Technical regime: `{trending_up, trending_down, ranging, volatile}` + SMA crossover signals + volume confirmation |
| **Sentiment Analyst** | News articles, sentiment scores, sentiment trend | Sentiment state: `{bullish, neutral, bearish}` + conviction (how many articles agree) + momentum (is sentiment improving or declining?) |
| **Fundamental Analyst** | Market context, sector performance, excess returns | Macro state: `{risk_on, risk_off, mixed}` + whether stock is outperforming or underperforming its market context |
| **Optimistic Viewpoint** | All three analyst outputs | Best-case interpretation — what would justify a BUY? |
| **Cautious Viewpoint** | All three analyst outputs | Worst-case interpretation — what risks justify a SELL? |
| **Synthesizer** | All five outputs | Final decision + explanation with citations |

### Agent Implementation

Each agent is a function that takes context and returns a structured response via LiteLLM.

```python
# Pseudocode for agent structure
async def technical_analyst(ticker: str, date: str, data: dict) -> AgentOutput:
    """
    Input: price history, technical indicators for the ticker around the date
    Output: {
        "regime": "trending_up",
        "signals": ["SMA-5 > SMA-20 (bullish crossover)", "volume_ratio: 2.3x (confirming)"],
        "conviction": 0.72,
        "recommendation": "buy",
        "reasoning": "Price has crossed above the 20-day SMA with 2.3x average volume..."
    }
    """
    prompt = build_technical_prompt(ticker, date, data)
    response = await litellm.acompletion(
        model="agent-fast",
        messages=[{"role": "system", "content": TECHNICAL_SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}],
        response_format=TechnicalOutput,  # structured output
    )
    return parse_response(response)
```

**Implementation:**

| File | Agent | LLM Model |
|------|-------|-----------|
| `agents/__init__.py` | Package init, shared types | — |
| `agents/schemas.py` | Pydantic models for all agent inputs/outputs | — |
| `agents/technical.py` | Technical Analyst | agent-fast (4o-mini) |
| `agents/sentiment.py` | Sentiment Analyst (uses FinBERT scores + LLM interpretation) | agent-fast |
| `agents/fundamental.py` | Fundamental Analyst | agent-fast |
| `agents/optimistic.py` | Optimistic Viewpoint | agent-fast |
| `agents/cautious.py` | Cautious Viewpoint | agent-fast |
| `agents/synthesizer.py` | Decision Synthesizer (final recommendation + explanation) | agent-reasoning (4o) |
| `agents/orchestrator.py` | Runs all agents in order, passes context between them | — |

### Orchestration Flow

```
User asks: "Analyze AAPL on 2023-06-15"
    │
    ▼
Orchestrator loads data for AAPL around 2023-06-15:
    - Price/volume/indicators from parquet (last 60 days)
    - News articles from ChromaDB (semantic search + date filter)
    - Sentiment scores from sentiment_scores.parquet
    - Market context from S&P 500 data
    │
    ├── Technical Analyst  ──► regime + signals + conviction
    ├── Sentiment Analyst  ──► sentiment state + article citations
    ├── Fundamental Agent  ──► macro context + relative performance
    │         (these 3 run in parallel)
    │
    ▼  combine outputs
    │
    ├── Optimistic Viewpoint ──► best-case argument
    ├── Cautious Viewpoint   ──► worst-case argument
    │         (these 2 run in parallel)
    │
    ▼  all 5 outputs combined
    │
    └── Synthesizer ──► FINAL DECISION
                        {
                          "action": "buy",
                          "confidence": 0.68,
                          "explanation": "AAPL shows a bullish SMA crossover...",
                          "citations": [
                            {"source": "Reuters", "date": "2023-06-14", "text": "Apple unveils..."},
                            {"indicator": "SMA-5 > SMA-20", "value": "$182.30 > $178.45"}
                          ],
                          "dissenting_view": "Cautious agent notes elevated volatility..."
                        }
```

---

## Phase 3: Integration & MCP Server

**Goal:** Wire the multi-agent system into the MCP server so it's usable from Cursor, and connect it to the evaluation pipeline.

### MCP Server Tools (already scaffolded in `server/mcp_server.py`)

| Tool | What It Does | Agents Involved |
|------|-------------|-----------------|
| `analyze_stock(ticker, date?)` | Full multi-agent recommendation with explanation | All 6 |
| `get_sentiment(ticker, start?, end?)` | Sentiment breakdown over a date range | Sentiment Analyst |
| `technical_snapshot(ticker, date?)` | Technical indicators and regime classification | Technical Analyst |
| `search_news(ticker, query?, limit?)` | Semantic search over news articles | ChromaDB retriever |
| `backtest(ticker, start, end)` | Simulate trading with model's signals | Orchestrator + data layer |
| `evaluate_model(split)` | Return evaluation metrics for a split | Evaluation pipeline |

### Cursor Integration

Add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "financial-analyst": {
      "command": "python",
      "args": ["server/mcp_server.py"],
      "cwd": "."
    }
  }
}
```

Then from Cursor, you can ask: "Use the financial-analyst tool to analyze AAPL" and the agent system runs end-to-end, returning a recommendation with citations inline.

---

## Phase 4: Evaluation & Grading System

**Goal:** Build a rigorous, multi-dimensional evaluation pipeline that grades the system across prediction accuracy, explanation quality, and trading utility.

### 4A. Classification Evaluation

Run the full agent pipeline on every record in the 2023 test set (18,433 records) and compare the agent's decision to the ground-truth target label.

| Metric | How Computed | Target |
|--------|-------------|--------|
| **Macro F1** (primary) | `sklearn.metrics.f1_score(y_true, y_pred, average='macro')` | > 0.40 (beating always-hold baseline of 0.23) |
| Per-class Precision/Recall | `classification_report` | Buy recall > 0.30 (don't miss upswings) |
| Confusion Matrix | `confusion_matrix` | Minimize BUY↔SELL misclassifications |

**Baselines for comparison:**
| Baseline | How It Works | Expected Macro F1 |
|----------|-------------|-------------------|
| Always-Hold | Predict "hold" for everything | 0.23 (1/3 for hold class, 0 for buy/sell) |
| Random | Uniform random over {buy, hold, sell} | ~0.33 |
| SMA Crossover | Buy when SMA-5 > SMA-20, sell when SMA-5 < SMA-20 | ~0.35 |
| Sentiment-Only | Buy if positive sentiment, sell if negative | ~0.30 |

### 4B. Explanation Quality (RAGAS)

For each recommendation, the system produces: (1) a query (the analysis request), (2) retrieved context (news articles), and (3) a generated answer (the explanation). RAGAS scores all three dimensions automatically.

| RAGAS Metric | What It Measures | Acceptable Range |
|-------------|-----------------|-----------------|
| `faithfulness` | Does the explanation only contain claims supported by the retrieved articles? | > 0.70 |
| `context_relevancy` | Are the retrieved articles actually relevant to the stock and time period? | > 0.75 |
| `answer_relevancy` | Does the explanation address the buy/hold/sell question specifically? | > 0.80 |

**Implementation:** `evaluation/ragas_eval.py` — run RAGAS on a sample of 200 test-set recommendations.

### 4C. Citation Correctness (Semi-automated)

For 50 sampled recommendations:

| Check | Method | Pass Criteria |
|-------|--------|--------------|
| **Source exists** | Verify cited article is in `rag_context.parquet` for the stated ticker and date | 100% (automated check) |
| **Content alignment** | Read the cited article; does it actually support the stated claim? | > 80% (manual review) |
| **No fabrication** | Are there any citations to articles that don't exist in our dataset? | 0 fabricated citations |

### 4D. Trading Backtest

Simulate following the system's signals on the 2023 test set:

```
For each stock-day in test set:
    if model says BUY  → go long (buy at close, sell next day at close)
    if model says SELL → go short (or skip if long-only)
    if model says HOLD → do nothing

Track:
    - Cumulative return
    - Sharpe ratio (annualized)
    - Max drawdown
    - Win rate (% of trades that are profitable)

Compare to:
    - Buy-and-hold benchmark (buy on Jan 1 2023, hold until Dec 14 2023)
    - S&P 500 return over the same period
```

**Implementation:** `evaluation/backtest.py`

### 4E. Grounded Reasoning (FinQA-Style)

Create 30 factual questions answerable from our dataset and run them through the RAG pipeline to test the retrieval + reasoning backbone.

Example questions:
- "What was AAPL's 20-day moving average on 2023-03-15?"
- "How many news articles mentioned MSFT in June 2023?"
- "What was the S&P 500 return on 2023-10-27?"
- "Which stock had the highest volume ratio in the test set?"

Score: % of factual questions answered correctly (target: > 80%).

**Implementation:** `evaluation/grounded_qa.py` + `evaluation/finqa_questions.json`

### Evaluation Summary Dashboard

```
evaluation/
├── run_evaluation.py        # Orchestrates all evaluation components
├── ragas_eval.py            # RAGAS faithfulness/relevancy scoring
├── classification_eval.py   # Macro F1, confusion matrix, baselines
├── backtest.py              # Trading simulation
├── citation_check.py        # Automated source verification
├── grounded_qa.py           # FinQA-style factual QA
├── finqa_questions.json     # 30 test questions with ground truth
└── results/                 # Evaluation outputs
    ├── classification_report.json
    ├── ragas_scores.json
    ├── backtest_results.json
    ├── citation_report.json
    └── grounded_qa_results.json
```

---

## Data Flow: How Existing Data Folds Into the System

```
EXISTING PIPELINE OUTPUT                     NEW COMPONENTS
========================                     ==============

data_engineered.parquet ─────────────────►  Classification model training
  (262K records, 35 features)                 (XGBoost / LightGBM on technical features)
         │
         ├── train_final.parquet ──────►  Train model + fit scalers
         ├── val_final.parquet ────────►  Tune hyperparameters
         └── test_final.parquet ───────►  Final evaluation + backtest

rag_context.parquet ──────────────────────►  ChromaDB vector store
  (3,821 stock-days with news text)          (split articles, embed, index)
         │
         └── per-article embeddings ───►  Retriever for agents

financial_phrasebank_clean.parquet ───────►  FinBERT fine-tuning
  (2,264 labeled sentences)                  (sentiment classifier)
         │
         └── finbert_sentiment.pt ─────►  Score all 9,721 articles
                                              │
                                              ▼
                                         sentiment_scores.parquet
                                              │
                                              ▼
                                         Enriched features ──► re-split ──► retrain
```

---

## Implementation Timeline

| Phase | Week | Deliverables |
|-------|------|-------------|
| **Phase 1A** | Week 1 | FinBERT fine-tuned, sentiment scores generated, features enriched |
| **Phase 1B** | Week 1 | ChromaDB vector store built, retriever tested |
| **Phase 2** | Weeks 2-3 | All 6 agents implemented, orchestrator working end-to-end |
| **Phase 3** | Week 3 | MCP server wired to agents, Cursor integration tested |
| **Phase 4** | Weeks 3-4 | Full evaluation pipeline: classification + RAGAS + backtest + citations |
| **Report** | Week 4 | Final progress report with all results |

---

## File Structure (final state)

```
.
├── agents/                          # Multi-agent system
│   ├── __init__.py
│   ├── schemas.py                   # Shared Pydantic models
│   ├── technical.py                 # Technical Analyst agent
│   ├── sentiment.py                 # Sentiment Analyst agent
│   ├── fundamental.py               # Fundamental Analyst agent
│   ├── optimistic.py                # Optimistic Viewpoint agent
│   ├── cautious.py                  # Cautious Viewpoint agent
│   ├── synthesizer.py               # Decision Synthesizer agent
│   └── orchestrator.py              # Agent coordination
│
├── server/                          # Server infrastructure
│   ├── mcp_server.py                # MCP server for Cursor
│   ├── retriever.py                 # ChromaDB retrieval interface
│   └── start_litellm.py             # LiteLLM proxy launcher
│
├── evaluation/                      # Evaluation pipeline
│   ├── run_evaluation.py            # Run all evaluations
│   ├── classification_eval.py       # Macro F1, confusion matrix
│   ├── ragas_eval.py                # RAGAS explanation quality
│   ├── backtest.py                  # Trading simulation
│   ├── citation_check.py            # Citation correctness
│   ├── grounded_qa.py               # FinQA-style factual QA
│   ├── finqa_questions.json         # Test questions
│   └── results/                     # Evaluation outputs
│
├── scripts/                         # Data pipeline (existing)
│   ├── 01_load_data.py              # Stage 1
│   ├── 02_clean_data.py             # Stage 2
│   ├── 03_align_data.py             # Stage 3
│   ├── 04_feature_engineering.py    # Stage 4
│   ├── 05_merge_and_split.py        # Stage 5
│   ├── 06_train_sentiment.py        # FinBERT fine-tuning (new)
│   ├── 07_score_sentiment.py        # Apply sentiment model (new)
│   ├── 08_enrich_features.py        # Add sentiment features (new)
│   ├── 09_build_vectorstore.py      # ChromaDB construction (new)
│   ├── 10_build_graph.py            # Neo4j graph (stretch, new)
│   └── run_pipeline.py              # Pipeline orchestrator
│
├── data/
│   ├── raw/                         # Original datasets (gitignored)
│   ├── processed/                   # Pipeline outputs (gitignored)
│   └── vectorstore/                 # ChromaDB persistence (gitignored)
│
├── notebooks/
│   ├── 01_EDA.ipynb                 # Exploratory analysis
│   └── eda_outputs/                 # Plots and summaries
│
├── .key                             # OpenAI API key (gitignored)
├── litellm_config.yaml              # LiteLLM proxy configuration
├── PLAN.md                          # This file
├── PIPELINE_SUMMARY.md              # Pipeline documentation
├── EDA_REPORT.md                    # EDA documentation
├── Addressing_TA_Comments.md        # TA feedback response
├── README.md                        # Project overview
└── requirements.txt                 # Python dependencies
```

---

## Dependencies (additions to requirements.txt)

```
# Sentiment model
transformers>=4.36.0
torch>=2.1.0

# LiteLLM proxy
litellm>=1.30.0

# RAG vector store
chromadb>=0.4.0

# MCP server
mcp>=1.0.0

# Evaluation
ragas>=0.1.0
xgboost>=2.0.0

# Knowledge graph (optional)
neo4j>=5.15.0
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Sentiment model | FinBERT (local) for scoring, GPT for agent reasoning | Reproducibility for scores, creativity for explanations |
| Vector store | ChromaDB (local, embedded) | No infrastructure needed, persists to disk, good enough for ~15K articles |
| Agent LLM | GPT-4o for synthesis, GPT-4o-mini for individual agents | Cost control: only the final synthesizer needs the full model |
| Primary metric | Macro F1 | Handles 70/15/15 class imbalance fairly |
| Explanation eval | RAGAS automated + 50-sample manual citation check | Scalable automated scoring + human validation |
| MCP over REST API | MCP server | Direct Cursor integration — type a question, get a recommendation inline |
| Classification model | XGBoost on engineered features | Strong baseline for tabular data; agents add interpretability on top |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Sentiment model underperforms on FNSPID articles (different domain than Phrasebank) | Sentiment features add noise, not signal | Evaluate sentiment model on 50 FNSPID articles manually before bulk scoring. Fall back to zero-shot GPT-4o-mini if FinBERT < 70% agreement with human labels. |
| Agent explanations hallucinate facts not in retrieved context | Low faithfulness scores, unreliable system | Use structured outputs to constrain citations to retrieved articles only. RAGAS faithfulness check catches this. |
| Low Macro F1 (< 0.35) on test set | System not better than random | This is expected for daily stock prediction. Frame the contribution as explainability, not prediction accuracy. The backtest and explanation quality are the real deliverables. |
| LiteLLM proxy cost overrun from test-set evaluation | API bill exceeds budget | Use GPT-4o-mini for most agents. Cache responses. Run full evaluation once, spot-check on subsets during development. |
| News coverage too sparse (1.46%) for meaningful sentiment features | Sentiment features are mostly null | Implement graceful degradation: when no news exists, sentiment agent reports "no news available" and technical + fundamental agents carry the decision. |
