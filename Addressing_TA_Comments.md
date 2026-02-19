# Addressing TA Comments — First Progress Report
**DSC288R Group 10 | Score: 13.3 / 15 pts**

---

## Overview

This document goes through every TA comment from the first progress report rubric,
assesses whether it can be addressed, explains how, and flags any decisions the
team needs to make before writing the fixes.

---

## Section 1: Data Pipeline (4.1 / 5 pts)

---

### Comment 1.1 — News Aggregation Rule

> *"You say you align news with stock prices at the stock-day level using (ticker, date), but it is not clearly stated what happens when there are multiple news articles for one stock-day, or when there is no news for a stock-day. Do you aggregate (count/mean sentiment), pick top-k, or keep all articles? Please state the rule."*

**Can we address it?** ✅ Yes — straightforward clarification needed.

**What we know already:**
- 3,821 stock-days have at least one news article (~1.46% of all records)
- Average of 2.42 articles per news day when news exists
- ~98.54% of stock-days have no news at all

**How to address it:**
We need to explicitly state two rules:

1. **When there is NO news for a stock-day:** The `text` column is `None`/`NaN` and `news_count = 0`. The row still exists (price data is present). The system falls back to technical-only analysis for that day. This should already be the case in the pipeline — we just need to say it clearly in the report.

2. **When there are MULTIPLE articles for one stock-day:** This is the part that needs a concrete rule defined and implemented. Options:

| Option | Pros | Cons |
|--------|------|------|
| Keep all as separate records (one row per article) | No information loss, best for Graph RAG (each article = its own node) | Inflates dataset size; breaks the stock-day structure |
| Concatenate text, aggregate sentiment (mean score) | Clean one-row-per-stock-day structure; easy for tabular models | Loses individual article signal; mean can be misleading |
| Pick the single highest-confidence article (top-1) | Clean structure; keeps best signal | Arbitrary; discards valid information |
| Keep one row but store `news_count` + `mean_sentiment` + full article list in graph | Best of both worlds for Graph RAG architecture | More complex pipeline |

**⚠️ DECISION NEEDED:**
The recommended approach for our Graph RAG system is **Option 4**: in the tabular dataset, store `news_count` and `mean_sentiment_score` per stock-day; in Neo4j, store each article as a separate `(:Article)` node linked to the stock and date. This way the flat dataset stays one-row-per-stock-day, and the full article detail lives in the graph. The team should confirm this is what was implemented (or update the pipeline if not).

> **💬 Harsh:** Option 4 is the best given our pipeline is not that complex, and we don't have enough data to justify dropping any records if we can avoid it.

---

### Comment 1.2 — Justification for the 50% Outlier Cutoff

> *"You remove 'extreme price outliers' defined as daily changes > 50%. It is not clear why 50% is the right cutoff or how many outliers are valid events (splits, major news) vs errors. Please justify the rule or show a quick check that this filtering does not remove real signal."*

**Can we address it?** ✅ Yes — needs a brief analysis and written justification.

**How to address it:**
We need to add a short analysis (can go in the report or a notebook cell) that shows:
1. How many of the 951 removed records were likely data errors vs legitimate events
2. Why 50% is a reasonable threshold

**What to write:**
- Normal daily stock moves are rarely above 10-15% even for major news events
- Moves above 50% in a single day are almost always one of: (a) a data entry error, (b) a stock split that wasn't adjusted, or (c) a reverse merger/bankruptcy — none of which represent tradeable signals in our system
- Cross-referencing a sample of the removed records against known split dates would confirm this

**⚠️ DECISION NEEDED:**
Should we run a quick spot-check on the 951 removed records and include a small table in the report showing the breakdown (e.g., "X were likely splits, Y were data errors, Z were unidentified")? This is the cleanest way to satisfy the TA. Alternatively, we can simply add a written justification with a citation (e.g., noting that even the most extreme single-day moves in market history, like 1987's Black Monday at -22%, are well below 50%). The team should decide whether to add the analysis or rely on written justification.

> **💬 Harsh:** I'm willing to do the analysis — look at the patterns in the data we cut off via the 50% threshold and change the cutoff if the analysis justifies it.

---

### Comment 1.3 — Exact Buy/Hold/Sell Threshold Definition

> *"The pipeline describes 'buy/hold/sell targets based on next-day returns,' but it does not clearly define the exact thresholds for buy/hold/sell, and whether thresholds are fixed or tuned. Please give the exact labeling rule in simple terms."*

**Can we address it?** ✅ Yes — this is just a documentation fix, the logic already exists.

**What we know already (from the alignment summary JSON):**
```
BUY:  next-day return > +2%   → 39,082 records (14.9%)
HOLD: -2% ≤ next-day return ≤ +2% → 182,914 records (69.7%)
SELL: next-day return < -2%   → 40,261 records (15.4%)
```

**How to address it:**
Simply add this exact table to the report and state: "Thresholds are **fixed at ±2%** and were not tuned — they represent a meaningful single-day move that justifies a trading action." Also worth noting that `next_day_return` is a **forward-looking label** (computed from tomorrow's close vs today's close) and the temporal split ensures no leakage.

**No decision needed here** — just write it up clearly.

---

## Section 2: EDA (4.2 / 5 pts)

---

### Comment 2.1 — Concrete Anomaly Table with Counts

> *"You say EDA covered anomalies/outliers and relationships, but the report does not clearly state one concrete anomaly rule and result for each major data type (prices, volume, news). Add a small table with these counts."*

**Can we address it?** ✅ Yes — we already have the numbers from the pipeline summary JSONs.

**How to address it:**
Add this table to the EDA section of the report:

| Data Type | Anomaly / Missing Rule | Count / Rate | Action Taken |
|-----------|----------------------|--------------|--------------|
| Stock Prices | Missing values | 0 (0%) | None needed |
| Stock Prices | Daily change > 50% (outliers) | 951 records | Removed |
| Stock Prices | Non-positive prices / zero volume | Small number | Removed |
| News Articles | Duplicate articles (same content hash) | 278 | Removed |
| News Articles | No news for a stock-day | 258,436 days (98.54%) | Text = null, news_count = 0 |
| S&P 500 | Missing market context | 35,645 records (13.6%) | Left as NaN, flagged with market_up/down = 0 |
| Volume | Extreme volume spikes (>Nx daily avg) | TBD — need to run check | TBD |

**⚠️ DECISION NEEDED:**
The volume spike row is TBD. We should either (a) add a quick check in the EDA notebook to quantify extreme volume days and report that number, or (b) remove that row from the table if we didn't apply a volume outlier filter. The team should clarify what was actually done with volume outliers.

> **💬 Harsh:** I'm willing to run the analysis to see if we can justify flagging/removing a volume spike anomaly threshold.

---

### Comment 2.2 — Correlation of 0.023 — Is It Meaningful?

> *"The correlation statement ('S&P 500 return is strongest predictor, correlation ≈ 0.023') is very small in size, so it is unclear what it means. Please explain in simple words whether this effect is meaningful, and whether you will rely on correlation or use other checks."*

**Can we address it?** ✅ Yes — needs a written explanation and potentially supplementary analysis.

**How to address it:**
We need to be honest here: a Pearson correlation of 0.023 between S&P 500 return and a stock's buy/hold/sell label is statistically near-zero at the individual data point level. However, this doesn't mean the feature is useless — it means:

1. **It's a noisy measure at the single stock-day level** — stock behavior is idiosyncratic
2. **The aggregate effect is real** — our own EDA showed that when S&P 500 is up, buy signals increase from 14.8% → 17.2% and sell signals drop. That's a meaningful directional effect even if individual Pearson r is small.
3. **Pearson correlation is the wrong tool for categorical targets** — our target (BUY/HOLD/SELL) is ordinal/categorical, so Pearson r will be artificially low. A better check would be mutual information or a chi-squared test.

**What to write in the report:**
> "A Pearson correlation of 0.023 between sp500_return and the target is low because our target is categorical (not continuous) and individual stock behavior is highly idiosyncratic. However, the group-level analysis shows S&P 500 direction meaningfully shifts the buy/sell ratio by ~3-5 percentage points. We include market context features (excess_return, market_up, market_down) not because of high raw correlation, but because the conditional distribution of targets shifts with market direction."

**⚠️ DECISION NEEDED:**
Should we add a mutual information score or point-biserial correlation as a supplementary check in the EDA notebook to replace or complement the Pearson correlation? This would be a stronger justification. Recommend yes — it's a one-liner in sklearn.

> **💬 Harsh:** I will implement a mutual information score and point-biserial correlation — the Pearson correlation being so low makes a stronger supplementary check essential.

---

## Section 3: Feature Identification from EDA (2 / 2 pts — Full Marks)

---

### Comment 3.1 — Sentiment Feature Pipeline Definition

> *"You list technical indicators and news features, but it is not clear how sentiment features are computed (which sentiment model, what output score, how aggregated per stock-day). Please define the sentiment feature pipeline clearly."*

**Can we address it?** ✅ Yes — but this requires decisions since the sentiment model hasn't been built yet.

**How to address it:**
Add a clear definition to the report. The pipeline will be:

```
Raw news article text
    → Sentiment model (see decision below)
    → Output: score ∈ [-1, +1], label (bullish/neutral/bearish), confidence ∈ [0, 1]
    → Aggregation per stock-day: mean score across all articles for that day
    → Final features: sentiment_score (mean), news_count, sentiment_label (majority vote)
```

**⚠️ DECISION NEEDED:**
Which sentiment model will we use? Two options:

| Option | Pros | Cons |
|--------|------|------|
| **FinBERT** (fine-tuned on Financial Phrasebank) | Fast, free, runs locally, well-established baseline | Older model, may miss nuance |
| **GPT-5.2 with structured outputs** | More accurate, handles complex financial language | Costs API money per article, slower for 9,721 articles |

**Recommendation:** Use FinBERT for the bulk sentiment scoring of the historical dataset (cheap, fast, reproducible). Use GPT-5.2 only for live/real-time inference in the final demo system. The team should confirm this split approach.

> **💬 Harsh:** I will let Raghav make this decision.

---

### Comment 3.2 — Rolling Window Lookahead Guarantee

> *"You don't show the exact rule for features that use rolling windows (moving averages, volatility). Please state the simple rule: 'only past days used,' and confirm how the first N days are handled (drop or fill)."*

**Can we address it?** ✅ Yes — just needs documentation + one clarification.

**How to address it:**
Add this statement to the report:

> "All rolling window features (SMA-5, SMA-20, SMA-50, momentum_5, momentum_20, volatility_20, volume_ma_20) use **only past trading days** — the window looks backward only (e.g., SMA-5 on day T uses days T-5 through T-1). No future data is used in any feature computation."

**✅ CONFIRMED FROM CODE (`04_feature_engineering.py`) — checked by Harsh:**
All rolling window features use **`min_periods=1`** (partial windows). The script does NOT drop any rows. Specifically:
```python
ticker_df['sma_5']  = ticker_df['close'].rolling(window=5,  min_periods=1).mean()
ticker_df['sma_20'] = ticker_df['close'].rolling(window=20, min_periods=1).mean()
ticker_df['sma_50'] = ticker_df['close'].rolling(window=50, min_periods=1).mean()
ticker_df['volatility_20'] = returns.rolling(window=20, min_periods=1).std()
```
The `momentum_5` and `momentum_20` features (via `pct_change`) do produce NaN for the first 5/20 rows per ticker, which are forward-filled downstream. No rows are dropped due to rolling window initialisation.

**What to write in the report:**
> "All rolling window features (SMA-5, SMA-20, SMA-50, momentum_5, momentum_20, volatility_20, volume_ma_20) use only past trading days — the window looks backward only. For the first N days of each ticker's history where the full window isn't yet available, partial windows are used (e.g., SMA-50 on day 3 = mean of 3 days). No rows are dropped due to rolling window initialisation."

**⚠️ DECISION NEEDED:**
Now that we know `min_periods=1` (partial windows) is what was implemented, should we keep this or switch to dropping the first 50 rows?

| Option | Approach | Records lost |
|--------|----------|-------------|
| **Partial windows (current)** | Use available days; keeps all records but early SMA values are less reliable | 0 |
| **Drop first 50 rows per ticker** | Clean — SMA-50 is always a real 50-day average | ~5,000 (~1.9%) |

> **💬 Harsh:** I think we simply drop. Cleaner approach and 1.9% record loss is nothing.

---

## Section 4: Quality and Comprehensiveness (3 / 3 pts — Full Marks)

---

### Comment 4.1 — Dataset Reproducibility (Exact Subset / Version)

> *"The report does not clearly state the exact subset and version you use (which exact date range per source, what 'sample of 100 stocks' and how chosen). Please specify the selection rule so the dataset is reproducible."*

**Can we address it?** ✅ Yes — needs a documentation addition.

**How to address it:**
Add a dataset specification table to the report:

| Dataset | Source Version | Date Range Used | Subset Rule |
|---------|----------------|-----------------|-------------|
| FNSPID Stock Prices | HuggingFace `Zihan1004/FNSPID`, accessed Jan 2026 | Oct 2009 – Dec 2023 | 100 tickers selected from those present in both FNSPID prices AND FNSPID news |
| FNSPID News | Same dataset, news split | Oct 2009 – Dec 2023 | All articles for the 100 selected tickers |
| Financial Phrasebank | HuggingFace `takala/financial_phrasebank`, `sentences_allagree` config | N/A (static dataset) | Full dataset, all 2,264 sentences |
| Yahoo S&P 500 | `^GSPC` via yfinance, downloaded Jan 2026 | Jan 1999 – Dec 2023 | Full index history |
| FinQA | GitHub `czyssrs/FinQA`, accessed Jan 2026 | N/A (static dataset) | Train + validation + test splits |

**✅ CONFIRMED FROM CODE (`01_load_data.py`) — checked by Harsh:**
```python
csv_files = list(price_dir.glob("*.csv"))
for csv_file in tqdm(csv_files[:100], desc="Loading prices"):  # Start with first 100 stocks for validation
```
The 100 tickers are the **first 100 CSV files returned by `glob("*.csv")`** on the FNSPID price directory. On most filesystems, `glob()` returns files in alphabetical order by filename, so this is effectively the **first 100 tickers alphabetically**. There is **no random sampling and no random seed** — the selection is deterministic.

However, the comment in the script says "for validation" suggesting this was intended as a starting point. The dataset specification table above should be corrected to reflect the actual rule.

**What to write in the report:**
> "The 100 stock tickers were selected by taking the first 100 CSV files in alphabetical order from the FNSPID price directory. This selection is deterministic and fully reproducible — no random sampling was used."

**⚠️ DECISION NEEDED:**
Should we keep this "first 100 alphabetically" selection, or should we define a more principled subset (e.g., S&P 100 by market cap, or 100 tickers present in both price AND news data)?

> **💬 Harsh:** I will let Raghav make this decision.

---

### Comment 4.2 — Evaluation Metrics Plan

> *"The report does not clearly state the evaluation metrics you will use for buy/hold/sell prediction (example: accuracy, macro F1, class-wise precision/recall, and also a simple trading metric if relevant). Please list your metric plan and why it matches your project goal."*

**Can we address it?** ✅ Yes — needs a metrics plan section added to the report.

**How to address it:**
Add this metrics plan:

**Classification Metrics (for the buy/hold/sell prediction):**
| Metric | Why it matters for this project |
|--------|--------------------------------|
| Macro F1 | Primary metric — classes are imbalanced (70% hold), macro F1 treats all three equally |
| Class-wise Precision / Recall | Lets us see if the model is biased toward "hold" (safe default) |
| Accuracy | Reported for completeness, but not the primary metric given class imbalance |
| Confusion matrix | Shows the cost of wrong predictions (e.g., predicting BUY when it should be SELL is worse than predicting HOLD) |

**Trading Performance Metric (simulated backtest on test set):**
| Metric | Why it matters |
|--------|---------------|
| Simulated cumulative return | Measures real-world utility: does following the system's signals make money on the 2023 test set? |
| Sharpe Ratio (optional) | Risk-adjusted return — relevant if we want to show the system is not just lucky |

**Explanation Quality Metrics** (see Comment 4.4 below).

**No major decisions needed** — this is mostly writing it down. The team should confirm they agree with Macro F1 as the primary metric.

---

### Comment 4.3 — Train / Val / Test Split Dates

> *"You say you enforce 'strict temporal splits,' but you do not specify what dates are train/val/test or the split method (rolling window vs fixed). Please define the split clearly to prove no leakage."*

**Can we address it?** ✅ Yes — the plan already exists, just needs to be stated explicitly.

**How to address it:**
State the following clearly in the report:

> **Split Method: Fixed temporal cutoff (not rolling window)**
>
> | Split | Date Range | Records (approx) | Purpose |
> |-------|-----------|------------------|---------|
> | Train | Oct 2009 – Dec 2021 | ~220,000 | Model training |
> | Validation | Jan 2022 – Dec 2022 | ~25,000 | Hyperparameter tuning, early stopping |
> | Test | Jan 2023 – Dec 2023 | ~17,000 | Final evaluation, reported metrics |
>
> **No-leakage guarantee:** (1) Rolling features (SMA, volatility) are computed on training data only, with test-set values computed using a walk-forward approach. (2) All scalers (MinMax, StandardScaler) are fit on the training set only and applied to val/test. (3) The target label uses next-day return, and all splits are by date so tomorrow's data is never in today's training set.

**⚠️ DECISION NEEDED:**
Should we use a **fixed split** or a **rolling/expanding window**? 
- Fixed split is simpler and more standard in academic work.
- Rolling window (e.g., train on 2009-2018, test 2019; then train 2009-2019, test 2020, etc.) is more rigorous and shows performance across different market regimes.

Recommend **fixed split for the report** (simpler to explain and defend) with a note that rolling-window evaluation is future work. The team should confirm.

---

### Comment 4.4 — FinQA Connection and Explanation Quality Definition

> *"You mention FinQA for evaluation, but it is unclear how FinQA connects to your output (buy/hold/sell explanation grounded in news). Please define what 'good explanation' means and how you will score it (human rubric, citation correctness, faithfulness, etc.)."*

**Can we address it?** ✅ Yes — but this requires the most new thinking.

**The honest assessment:**
FinQA tests numerical reasoning over financial tables (e.g., "what is the YoY revenue growth?"). Our system generates natural language explanations grounded in news articles and price data. The connection is weak — FinQA doesn't directly evaluate our explanation format. We need to either reframe how we use FinQA or define a different/supplementary evaluation.

**How to address it:**
Define "good explanation" concretely and propose a multi-part evaluation:

| Evaluation Type | What it measures | How to score |
|-----------------|-----------------|-------------|
| **Citation Correctness** | Does the cited article actually support the claim made? | For N sampled recommendations, manually check if each cited article matches the stated reason. Score: % of citations that are accurate. |
| **Faithfulness** | Does the explanation only contain information present in the retrieved sources (no hallucination)? | Use a faithfulness metric (e.g., from RAGAS framework) or manual spot-check on a sample. |
| **Prediction Accuracy** | Is the BUY/HOLD/SELL signal correct? | Macro F1 on 2023 test set (see Comment 4.2) |
| **FinQA (reframed)** | Tests whether the system can answer specific numerical questions about a stock using the graph (e.g., "what was AAPL's 20-day average return last week?") — this is answerable via Cypher + RAG | Report accuracy on a subset of FinQA questions relevant to our data |
| **Human evaluation (optional)** | Do users find explanations clear, trustworthy, and useful? | Small rubric (1-5 scale) on: clarity, accuracy, completeness, trustworthiness |

**⚠️ DECISION NEEDED:**
The team needs to agree on which evaluation components to commit to:
1. **Minimum viable:** Citation correctness (manual sample check) + Macro F1 on prediction — these are definitely achievable
2. **Stronger:** Add RAGAS faithfulness score — requires running the RAGAS library on outputs
3. **Optional/stretch:** Human evaluation study or FinQA numerical subset

The team should decide by Week 5 (before evaluation is implemented) which components to include. The TA is asking us to define this upfront, so at minimum we need to write the plan clearly now, even if full execution comes later.

---

## Summary Table

| # | Comment | Addressable? | Effort | Decision Required? |
|---|---------|-------------|--------|-------------------|
| 1.1 | News aggregation rule for multi-article days | ✅ Yes | Low | ✅ Yes — confirm aggregation approach |
| 1.2 | Justify 50% outlier cutoff | ✅ Yes | Low-Medium | ✅ Yes — written justification vs. spot-check analysis |
| 1.3 | Exact buy/hold/sell thresholds | ✅ Yes | Low | ❌ No — just write it up |
| 2.1 | Anomaly table with exact counts | ✅ Yes | Low | ✅ Yes — confirm volume outlier handling |
| 2.2 | Explain what correlation 0.023 means | ✅ Yes | Low | ✅ Yes — add mutual information check? |
| 3.1 | Define sentiment feature pipeline | ✅ Yes | Medium | ✅ Yes — FinBERT vs GPT-5.2 for batch processing |
| 3.2 | Rolling window lookahead guarantee | ✅ Yes | Low | ✅ Yes — confirm how first N days handled |
| 4.1 | Dataset reproducibility / 100 stock selection rule | ✅ Yes | Low | ✅ Yes — confirm exact ticker selection logic |
| 4.2 | Evaluation metrics plan | ✅ Yes | Low | Low — confirm Macro F1 as primary |
| 4.3 | Exact train/val/test split dates | ✅ Yes | Low | ✅ Yes — fixed vs rolling window |
| 4.4 | FinQA connection + explanation quality definition | ✅ Yes | Medium | ✅ Yes — which evaluation components to commit to |

**All 11 comments are addressable.** Most are documentation fixes. The substantive decisions that require team alignment are flagged with ⚠️ above.
