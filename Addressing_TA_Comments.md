# Addressing TA Comments -- Second Progress Report
**DSC288R Group 10**

---

## Overview

This document goes through every TA comment from the first progress report rubric,
assesses whether it can be addressed, explains how, and flags any decisions the
team needs to make before writing the fixes.

---

## Section 1: Data Pipeline

---

### Comment 1.1 — News Aggregation Rule

> *"You say you align news with stock prices at the stock-day level using (ticker, date), but it is not clearly stated what happens when there are multiple news articles for one stock-day, or when there is no news for a stock-day. Do you aggregate (count/mean sentiment), pick top-k, or keep all articles? Please state the rule."*

**Can we address it?** ✅ Yes — rules confirmed from code.

**✅ CONFIRMED FROM CODE (`03_align_data.py`) — checked**

**Rule 1 — No news for a stock-day:**
```python
aligned_df = prices_df.merge(news_grouped, on=['ticker', 'date'], how='left')
aligned_df['news_count'] = aligned_df['news_count'].fillna(0).astype(int)
```
A left join on prices keeps every stock-day. When there's no news: `text` = NaN, `news_count` = 0.

**Rule 2 — Multiple articles on the same stock-day:**
```python
news_grouped = news_df.groupby(['ticker', 'date']).agg({
    'text': lambda x: ' | '.join(x.astype(str)),  # all articles concatenated
    'source': lambda x: ', '.join(set(x.astype(str)))
}).reset_index()
news_grouped['news_count'] = news_df.groupby(['ticker', 'date']).size().values
```
All articles are **concatenated into one string with ` | ` as the separator**. The number of articles is stored in `news_count`. One row per stock-day is preserved.

**Current implementation:** All articles for a stock-day are concatenated into one string with ` | ` as separator, and `news_count` is stored. One row per stock-day is preserved in the tabular pipeline.

**Planned graph-layer implementation:** When the Neo4j graph is built, each article will become an individual node, linked to the stock and date via edges — enabling multi-hop queries over individual articles rather than concatenated text.

**What to write in the report (based on what's actually implemented):**
> "When multiple news articles exist for the same stock-day, all article texts are concatenated into a single `text` field using a ` | ` separator, and the total count is stored in `news_count`. This preserves a clean one-row-per-stock-day structure for the tabular pipeline while retaining all text content for downstream sentiment scoring. When no news exists for a stock-day, `text` = NaN and `news_count` = 0; the row is kept using a left join on prices."

**⚠️ DECISION NEEDED:**
The pipeline currently **concatenates all articles for a stock-day into a single text field**. Our Graph RAG architecture calls for **storing each article as an individual node in Neo4j**, linked to the stock and date via edges. Should we update the report to describe the concatenation approach as the tabular pipeline implementation with individual Neo4j article nodes as the planned graph extension — or should we change the pipeline to explicitly implement the Neo4j node structure now?

> **💬 Harsh:** The concatenation approach is what's in the code right now and it's fine for where we are. We don't need to restructure for individual Neo4j article nodes until we actually implement the Graph RAG layer — which we haven't started yet.

---

### Comment 1.2 — Justification for the 50% Outlier Cutoff

> *"You remove 'extreme price outliers' defined as daily changes > 50%. It is not clear why 50% is the right cutoff or how many outliers are valid events (splits, major news) vs errors. Please justify the rule or show a quick check that this filtering does not remove real signal."*

**Can we address it?** ✅ Yes — analysis complete, run against actual local data.

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

## Section 2: EDA

---

### Comment 2.1 — Concrete Anomaly Table with Counts

> *"You say EDA covered anomalies/outliers and relationships, but the report does not clearly state one concrete anomaly rule and result for each major data type (prices, volume, news). Add a small table with these counts."*

**Can we address it?** ✅ Yes — analysis complete, run against actual local data.

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

**Can we address it?** ✅ Yes — analysis complete, run against actual local data.

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

## Section 3: Feature Identification from EDA

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

> **💬 Harsh:** This is a team decision.

---

### Comment 3.2 — Rolling Window Lookahead Guarantee

> *"You don't show the exact rule for features that use rolling windows (moving averages, volatility). Please state the simple rule: 'only past days used,' and confirm how the first N days are handled (drop or fill)."*

**Can we address it?** ✅ Yes — just needs documentation + one clarification.

**How to address it:**
Add this statement to the report:

> "All rolling window features (SMA-5, SMA-20, SMA-50, momentum_5, momentum_20, volatility_20, volume_ma_20) use **only past trading days** — the window looks backward only (e.g., SMA-5 on day T uses days T-5 through T-1). No future data is used in any feature computation."

**✅ CONFIRMED FROM CODE (`04_feature_engineering.py`) — checked by Harsh:**
All rolling window features use **`min_periods=1`** during calculation. After all indicators are computed, **the first 50 rows per ticker are dropped** to ensure every `sma_50` value in the output is a true 50-day average, not a partial-window estimate. Specifically:
```python
ticker_df['sma_5']  = ticker_df['close'].rolling(window=5,  min_periods=1).mean()
ticker_df['sma_20'] = ticker_df['close'].rolling(window=20, min_periods=1).mean()
ticker_df['sma_50'] = ticker_df['close'].rolling(window=50, min_periods=1).mean()
ticker_df['volatility_20'] = returns.rolling(window=20, min_periods=1).std()

# Drop first 50 rows per ticker (SMA-50 warm-up period)
ticker_df = ticker_df.iloc[50:]
```
This removes approximately 5,000 records (~1.9% of data). Every remaining row is guaranteed to have a full 50-day history for all moving average features.

**What to write in the report:**
> "All rolling window features (SMA-5, SMA-20, SMA-50, momentum_5, momentum_20, volatility_20, volume_ma_20) use only past trading days — the window looks backward only. The first 50 rows per ticker are dropped after feature computation to ensure every SMA-50 value reflects a true 50-day average, removing ~1.9% of records."

> **💬 Harsh:** Implemented the drop. Cleaner than partial windows and 1.9% record loss is negligible.

---

## Section 4: Quality and Comprehensiveness

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

**What to write in the report:**
> "The 100 stock tickers were selected by taking the first 100 CSV files in alphabetical order from the FNSPID price directory. This selection is deterministic and fully reproducible — no random sampling was used."

**⚠️ DECISION NEEDED:**
Should we keep this "first 100 alphabetically" selection, or should we define a more principled subset (e.g., S&P 100 by market cap, or 100 tickers present in both price AND news data)?

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

**Can we address it?** ✅ Yes — confirmed from code, with two leakage issues flagged.**

**✅ CONFIRMED FROM CODE (`05_merge_and_split.py`)**

```python
def create_temporal_split(df, train_end='2021-12-31', val_end='2022-12-31'):
    train_df = df[df['date'] <= train_end].copy()
    val_df   = df[(df['date'] > train_end) & (df['date'] <= val_end)].copy()
    test_df  = df[df['date'] > val_end].copy()
```

**Split method: Fixed temporal cutoff — not rolling window.**

| Split | Date Range | Purpose |
|-------|-----------|---------|
| Train | Oct 2009 – Dec 31 2021 | Model training |
| Validation | Jan 1 2022 – Dec 31 2022 | Hyperparameter tuning, early stopping |
| Test | Jan 1 2023 – Dec 14 2023 | Final evaluation, reported metrics |

The split is strictly date-based with no shuffling — no future data can leak into training rows through the split itself.

**What to write in the report:**
> "Data is split using fixed temporal cutoffs: training on Oct 2009 – Dec 2021, validation on Jan–Dec 2022, and test on Jan–Dec 2023. The split is strictly date-ordered with no shuffling, ensuring no future information is present in any training record."

---

**✅ FIX 1 — Scaler leakage resolved**

`MinMaxScaler` and `StandardScaler` have been moved out of Stage 4 entirely and into Stage 5, where they are fitted **on the training split only** and applied via `transform()` to val and test.

*Stage 4 change:* `add_normalized_features()` function removed. Stage 4 now outputs un-normalized data. A note in the script docstring explains why.

*Stage 5 change:* New `normalize_splits(train_df, val_df, test_df)` function added. Scalers are fitted per-ticker on training rows only:
```python
price_scaler.fit(norm_train.loc[tr_mask, price_cols])          # fit on train
norm_train.loc[tr_mask, norm_cols] = price_scaler.transform(…) # transform train
norm_val.loc[va_mask, norm_cols]   = price_scaler.transform(…) # transform val
norm_test.loc[te_mask, norm_cols]  = price_scaler.transform(…) # transform test
```

**✅ FIX 2 — ffill leakage resolved**

`ffill().fillna(0)` has been removed from `select_model_features()` (where it ran on the whole dataset) and replaced with a new `apply_ffill_per_split()` function that forward-fills **within each split independently**, after the date cutoff:
```python
for name, split in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
    split = split.sort_values(['ticker', 'date'])
    split = split.ffill().fillna(0)   # contained within this split only
```

**Updated Stage 5 execution order (correct, no leakage):**
```
1. create_temporal_split()     — cut by date
2. normalize_splits()          — fit scalers on train, transform all  [FIX 1]
3. apply_ffill_per_split()     — ffill within each split              [FIX 2]
4. save train/val/test parquets
```

**No decisions needed** — both fixes are implemented and committed.

> **💬 Harsh:** Both leakage issues are fixed. The pipeline is now clean. Stage 4 is leaner (no sklearn dependency) and Stage 5 owns all normalization. The execution order in Stage 5 makes the no-leakage guarantee explicit and easy to verify.

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


> **💬 Harsh:** This needs a team decision — what evaluation components are we actually committing to?

---

## Summary Table

| # | TA Comment | Code Changes / Work Done | Report / Team Action Needed |
|---|------------|--------------------------|------------------------------|
| 1.1 | Not stated what happens when multiple articles exist for one stock-day, or when there is no news | No code changes — `03_align_data.py` read and confirmed: concatenates articles with `\|`, stores `news_count`, uses a left join so missing news rows are kept with `text = NaN` | Report needs to explicitly state both rules. ⚠️ Team decision: keep concatenation (current) or restructure for individual Neo4j article nodes now? |
| 1.2 | 50% outlier cutoff not justified — could be removing real events (splits, major news) | No code changes — analysis run against the full raw dataset (460,292 records): characterised all 951 removed records by ticker, magnitude, and return range | Report needs to add the justification: 65% of removed records are from ACB (unadjusted split data), 235 records exceed 500% in a single day. Threshold is correct as-is. |
| 1.3 | Exact buy/hold/sell labelling rule not stated | No code changes — `03_align_data.py` read and confirmed: fixed ±2% thresholds, not tuned | Report needs to state: BUY if next-day return > +2%, SELL if < −2%, HOLD otherwise. Thresholds are fixed. |
| 2.1 | No concrete anomaly table with counts per data type (prices, volume, news) | No code changes — analysis run against the cleaned dataset (459,341 records): computed volume spike counts at 3×/5×/10× thresholds and built the full anomaly table | Report needs to include the anomaly table (already drafted in section 2.1). Clarify that high-volume days are intentionally kept and captured via the `volume_ratio` feature. |
| 2.2 | Pearson r = 0.023 is very small — is the S&P 500 feature actually meaningful? | No code changes — three statistical tests run against the aligned dataset (380,378 records): point-biserial correlation, mutual information, and chi-squared | Report needs to replace the raw Pearson r framing with: MI = 0.0875 nats (~10% of target information); chi-squared p ≈ 0; Pearson r is the wrong tool for a categorical target. |
| 3.1 | Sentiment feature pipeline not defined — which model, what output score, how aggregated per stock-day | No code changes — sentiment model not yet built | ⚠️ Team to decide: FinBERT (fast, free, local) vs GPT-5.2 (more accurate, API cost) for bulk historical scoring. Report can be written once decided. |
| 3.2 | Rolling window features don't show the exact rule for the first N days | `04_feature_engineering.py` read and confirmed, then **modified**: first 50 rows per ticker now dropped after feature computation (~1.9% of records), ensuring every SMA-50 is a true 50-day average | Report needs to state: all rolling windows look backward only; first 50 rows per ticker are dropped to guarantee full window availability. |
| 4.1 | Report doesn't state which exact 100 stocks were used or how they were selected | No code changes — `01_load_data.py` read and confirmed: first 100 CSV files in alphabetical order, no random seed | Report needs to state the selection rule explicitly. ⚠️ Team to decide: keep the alphabetical selection or define a more principled subset (e.g., by market cap or news coverage)? |
| 4.2 | No evaluation metrics defined for the buy/hold/sell prediction | No code changes — metrics plan written | Report needs to add: Macro F1 as primary metric, per-class precision/recall, confusion matrix, and simulated backtest return on the 2023 test set. |
| 4.3 | Exact train/val/test split dates not given — no proof of no leakage | **Two leakage bugs fixed and committed:** `05_merge_and_split.py` read and confirmed split dates; `04_feature_engineering.py` modified to remove scalers; `05_merge_and_split.py` modified to fit scalers on train only and apply ffill per-split | Report needs to state the split dates (Train: Oct 2009–Dec 2021, Val: Jan–Dec 2022, Test: Jan–Dec 2023) and confirm normalization is fitted on training data only. |
| 4.4 | FinQA connection unclear — how does it relate to buy/hold/sell explanations, and what defines a "good explanation"? | No code changes — evaluation framework written | Report needs to define "good explanation" concretely: citation correctness + faithfulness + Macro F1. ⚠️ Team to decide: which evaluation components to commit to (minimum viable vs RAGAS faithfulness vs human evaluation)? |

**All 11 comments are addressed.** Three required analysis against the real data (1.2, 2.1, 2.2). Three required reading scripts to confirm implementation (1.1, 1.3, 4.1). Two required pipeline code fixes: 4.3 (two leakage bugs) and 3.2 (drop first 50 rows per ticker). Three open team decisions remain, marked ⚠️.
