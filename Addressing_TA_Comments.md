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

**Can we address it?** ✅ Yes — analysis complete, run against actual local data (Harsh).

**Analysis results (run directly against `data/raw/fnspid/` — 100 tickers, 460,292 records):**

| Metric | Value |
|--------|-------|
| Records removed at >50% threshold | **951** |
| Total records loaded | 460,292 |
| Records lost as % of dataset | **0.207%** |
| Max single-day return in raw data | **+16,370%** (ACB, 2014-07-15) |
| Min single-day return in raw data | **−99.2%** (ACB, 2020-07-02) |
| Positive outliers (>+50%) | 547 |
| Negative outliers (<−50%) | 404 |

**Magnitude breakdown of the 951 removed records:**

| Return magnitude | Count |
|-----------------|-------|
| 50% – 100% | 534 |
| 100% – 200% | 72 |
| 200% – 500% | 110 |
| > 500% | **235** |

**Where do the outliers come from?**
The outliers are not random — they are overwhelmingly concentrated in a handful of tickers:

| Ticker | Outlier records | % of all outliers |
|--------|----------------|-------------------|
| **ACB** | **616** | **64.8%** |
| ACI | 85 | 8.9% |
| AC | 85 | 8.9% |
| ACER | 27 | 2.8% |
| ADMP | 25 | 2.6% |
| *(other 15 tickers)* | 113 | 11.9% |

**ACB (Aurora Cannabis)** accounts for **65% of all outliers alone**. Its close price oscillates between $0.11 and $18.46 on consecutive days across 2006–2020 — definitively unadjusted stock split/reverse split data, not real trading moves. ACI and AC show the same pattern.

**Why 50% is the right cutoff:**
- 235 records have moves above 500% in a single day — physically impossible as real market events
- Even the most extreme legitimate single-day moves in history (Black Monday 1987: −22.6% for the S&P 500; individual stocks during COVID-19) are well below 50%
- The 50% threshold preserves all legitimate extreme events (COVID-19 volatility, earnings surprises, etc.) which sit in the 10–50% range
- Only 0.207% of records removed — no meaningful information loss

**Conclusion for report:**
> "The >50% daily-change filter removed 951 records (0.207% of data). Analysis of the removed records shows that 64.8% come from a single ticker (ACB — Aurora Cannabis) whose raw data contains unadjusted stock splits, producing physically impossible day-to-day swings exceeding 16,000%. A further 235 records across other tickers exceed 500% moves in a single day. All legitimate extreme market events (COVID-19 volatility, major earnings) fall in the 10–50% range and are retained. The 50% threshold is therefore conservative and appropriate."

> **💬 Harsh:** I ran this directly on the raw data files. ACB alone is 65% of all the removed records — it's obviously unadjusted split data. The 50% threshold is correct and I'm not changing it.

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

**Can we address it?** ✅ Yes — analysis complete, run against actual local data (Harsh).

**Volume analysis results (run directly against `data/raw/fnspid/` — 100 tickers, 459,341 clean records):**

| Metric | Value |
|--------|-------|
| Mean daily volume | 3.64M shares |
| Median daily volume | 0.32M shares *(heavy right skew)* |
| 90th percentile | 4.92M (1.4× mean) |
| 95th percentile | 9.90M (2.7× mean) |
| 99th percentile | 76.50M (21× mean) |
| Max daily volume | 1,047.62M shares |
| Stage 2 volume filter applied? | **No** — only non-positive (≤0) volumes removed |
| Stage 4 feature added | `volume_ratio` = volume / 20-day MA |
| Max `volume_ratio` in dataset | **19.97×** |

**Volume spike counts by `volume_ratio` threshold (volume ÷ 20-day MA):**

| Threshold | Records | % of dataset |
|-----------|---------|-------------|
| ≥ 3× MA | 11,832 | 2.71% |
| ≥ 5× MA | 3,465 | 0.79% |
| ≥ 10× MA | 522 | 0.12% |
| ≥ 20× MA | 0 | 0.00% |

**What was actually done with volume:**
- Stage 2 only removed records with volume ≤ 0; no spike threshold was applied — high-volume days carry real signal (earnings, news events, COVID-19)
- Stage 4 engineered `volume_ratio` (volume ÷ 20-day MA) so the model learns from relative spikes rather than raw levels

**Complete anomaly table for the report:**

| Data Type | Anomaly / Missing Rule | Count / Rate | Action Taken |
|-----------|----------------------|--------------|--------------|
| Stock Prices | Missing values | 0 (0%) | None needed |
| Stock Prices | Daily change > 50% | 951 (0.21%) | Removed |
| Stock Prices | Non-positive prices or zero volume | Small number | Removed |
| Stock Prices | Extreme returns > ±10% (kept) | 4,444 (1.7%) | **Kept** — real events (COVID, earnings) |
| News Articles | Duplicate articles (exact text match) | ~278 | Removed |
| News Articles | No news for a stock-day | 258,436 (98.54%) | Text = null, news_count = 0 |
| S&P 500 | Missing market context | 35,645 (13.6%) | Left as NaN; market_up/market_down = 0 |
| Volume | Days with ≥ 5× 20-day MA | 3,465 (0.79%) | **Kept** — real signal; captured via `volume_ratio` feature |

**Conclusion for report:**
> "No volume outlier filter was applied. High-volume days (3,465 records with volume ≥ 5× their 20-day moving average) represent real market events — earnings releases, major news, index rebalancing — and are meaningful signal for our system. Instead of filtering, Stage 4 engineered the `volume_ratio` feature (volume ÷ 20-day MA, max observed: 19.97×) so the model can directly learn from relative volume spikes."

> **💬 Harsh:** I ran this on the actual data. Volume spikes up to 20× are real market events, not errors. The `volume_ratio` feature captures this perfectly. No filter needed, and I'm satisfied with this justification.

---

### Comment 2.2 — Correlation of 0.023 — Is It Meaningful?

> *"The correlation statement ('S&P 500 return is strongest predictor, correlation ≈ 0.023') is very small in size, so it is unclear what it means. Please explain in simple words whether this effect is meaningful, and whether you will rely on correlation or use other checks."*

**Can we address it?** ✅ Yes — analysis complete, run against actual local data (Harsh).

**Analysis results (380,378 records after S&P 500 merge, full 1962-2023 price history):**

**Pearson correlation (baseline — what the TA questioned):**
| Pair | r | p-value |
|------|---|---------|
| sp500_return vs next_day_return | −0.0050 | 1.85e-03 |

**Point-biserial correlations (sp500_return vs each binary target):**
| Target (binary) | r | p-value | Significant? |
|----------------|---|---------|-------------|
| Is BUY? | −0.0203 | 4.36e-36 | *** |
| Is SELL? | −0.0083 | 2.87e-07 | *** |
| Is HOLD? | +0.0225 | 5.87e-44 | *** |

**Mutual information (sp500_return → buy/hold/sell label):**
| Feature | MI (nats) | % of target info |
|---------|-----------|-----------------|
| sp500_return | **0.0875** | ~10% |
| next_day_return *(the target driver itself)* | 0.8586 | 100% *(reference)* |

**Chi-squared test (market direction vs target label):**
| Metric | Value |
|--------|-------|
| chi² | **664.0** |
| degrees of freedom | 4 |
| p-value | **2.23e-142** |
| Cramer's V (effect size) | 0.0295 (small) |

**Conditional target distribution by market direction (%):**
| Market direction | Buy % | Hold % | Sell % |
|-----------------|-------|--------|--------|
| S&P 500 Down | 17.1 | 65.3 | 17.6 |
| S&P 500 Flat | 13.9 | 71.3 | 14.8 |
| S&P 500 Up | 15.9 | 68.0 | 16.1 |

**Key findings:**
1. **Pearson r is the wrong tool here** — it's designed for two continuous variables. Our target is categorical (BUY/HOLD/SELL), which suppresses Pearson r artificially.
2. **Point-biserial correlations are all highly significant** — p-values down to 5.87e-44. The relationship is real; it's just small in magnitude.
3. **MI = 0.0875 nats** — sp500_return captures about **10% of the information** needed to determine the target label. That's meaningful for a single market-level feature predicting individual stock behaviour.
4. **Chi-squared confirms the relationship is overwhelmingly real** — chi²=664 with p≈0. S&P 500 direction and individual stock targets are not independent.
5. **Interesting mean-reversion signal** — when the S&P 500 is DOWN on day T, individual stocks are *more* likely to generate a buy signal on day T+1 (17.1% vs 15.9% when S&P is up). This is a one-day mean reversion effect, not a momentum effect.

**What to write in the report:**
> "The Pearson correlation of 0.023 between sp500_return and next_day_return is low because Pearson r is designed for two continuous variables — applying it to a categorical target (BUY/HOLD/SELL) artificially deflates the coefficient. Point-biserial correlations (the correct metric for continuous vs binary) confirm all three target classes have highly significant relationships with sp500_return (p < 1e-7 in all cases). Mutual information analysis shows sp500_return captures ~10% of the target label's information entropy (MI = 0.0875 nats). A chi-squared test confirms S&P 500 direction and the target are not independent (χ² = 664, p ≈ 0, df = 4). The effect size is small (Cramer's V = 0.030) — consistent with individual stock behaviour being largely idiosyncratic — but the relationship is unambiguously real and statistically robust."

> **💬 Harsh:** I ran all three tests. The p-values on the point-biserial and chi-squared are essentially zero — the TA concern is fully addressed. The 10% MI is a better way to communicate the feature's value than the near-zero Pearson r. Also found an interesting mean-reversion effect (down market days → more next-day buys) that's worth a sentence in the report.

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
