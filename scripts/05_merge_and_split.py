"""
Stage 5: Data Merging and Train/Val/Test Split
Create final datasets with temporal splits.

LEAKAGE FIXES applied in this version:
  FIX 1 — Normalization post-split:
    MinMaxScaler (prices) and StandardScaler (volume, returns) are fitted
    on the TRAINING split only (per ticker), then applied via transform()
    to validation and test. This prevents future price ranges from
    influencing how training data is scaled.

  FIX 2 — ffill applied within each split:
    Forward-fill for NaN values is applied separately inside each split
    after the date cutoff, so no value from the validation or test period
    can propagate backward into training rows.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from sklearn.preprocessing import MinMaxScaler, StandardScaler
import warnings
warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def create_temporal_split(df, train_end='2018-12-31', val_end='2019-12-31'):
    """
    Split data temporally to prevent look-ahead bias.
    Train: up to train_end (inclusive)
    Validation: train_end+1 to val_end (inclusive)
    Test: after val_end
    """
    print("\n" + "="*60)
    print("CREATING TEMPORAL TRAIN/VAL/TEST SPLIT")
    print("="*60)

    df['date'] = pd.to_datetime(df['date'])
    print(f"Full date range: {df['date'].min().date()} to {df['date'].max().date()}")

    train_df = df[df['date'] <= train_end].copy()
    val_df   = df[(df['date'] > train_end) & (df['date'] <= val_end)].copy()
    test_df  = df[df['date'] > val_end].copy()

    print(f"\nSplit sizes:")
    print(f"  Train : {len(train_df):,} records  ({len(train_df)/len(df)*100:.1f}%)")
    print(f"  Val   : {len(val_df):,} records  ({len(val_df)/len(df)*100:.1f}%)")
    print(f"  Test  : {len(test_df):,} records  ({len(test_df)/len(df)*100:.1f}%)")

    print(f"\nTrain date range : {train_df['date'].min().date()} to {train_df['date'].max().date()}")
    print(f"Val   date range : {val_df['date'].min().date()} to {val_df['date'].max().date()}")
    print(f"Test  date range : {test_df['date'].min().date()} to {test_df['date'].max().date()}")

    if 'target' in df.columns:
        print("\nTarget distribution:")
        for name, split in [("Train", train_df), ("Validation", val_df), ("Test", test_df)]:
            dist = split['target'].value_counts(normalize=True) * 100
            print(f"  {name}: buy={dist.get('buy',0):.1f}%  hold={dist.get('hold',0):.1f}%  sell={dist.get('sell',0):.1f}%")

    return train_df, val_df, test_df


def normalize_splits(train_df, val_df, test_df):
    """
    FIX 1: Fit scalers on training data only, transform all three splits.
    Scalers are fitted per-ticker to handle different price scales.

    Columns normalized:
      - open, high, low, close  -> MinMaxScaler -> open_norm, high_norm, low_norm, close_norm
      - volume                  -> StandardScaler -> volume_norm
      - next_day_return         -> StandardScaler -> return_norm
    """
    print("\n" + "="*60)
    print("NORMALIZATION (train-fit only — FIX 1)")
    print("="*60)

    price_cols  = ['open', 'high', 'low', 'close']
    volume_col  = 'volume'
    return_col  = 'next_day_return'

    norm_train = train_df.copy()
    norm_val   = val_df.copy()
    norm_test  = test_df.copy()

    tickers = train_df['ticker'].unique()
    print(f"Fitting scalers on training data for {len(tickers)} tickers...")

    for ticker in tickers:
        tr_mask = norm_train['ticker'] == ticker
        va_mask = norm_val['ticker']   == ticker
        te_mask = norm_test['ticker']  == ticker

        # ── Price: MinMaxScaler ──────────────────────────────────────────
        if all(c in norm_train.columns for c in price_cols):
            price_scaler = MinMaxScaler()
            # Fit on train, transform all
            train_prices = norm_train.loc[tr_mask, price_cols]
            price_scaler.fit(train_prices)

            norm_cols = [c + '_norm' for c in price_cols]
            norm_train.loc[tr_mask, norm_cols] = price_scaler.transform(train_prices)
            if va_mask.any():
                norm_val.loc[va_mask, norm_cols]   = price_scaler.transform(norm_val.loc[va_mask, price_cols])
            if te_mask.any():
                norm_test.loc[te_mask, norm_cols]  = price_scaler.transform(norm_test.loc[te_mask, price_cols])

        # ── Volume: StandardScaler ───────────────────────────────────────
        if volume_col in norm_train.columns:
            vol_scaler = StandardScaler()
            vol_scaler.fit(norm_train.loc[tr_mask, [volume_col]])
            norm_train.loc[tr_mask, 'volume_norm'] = vol_scaler.transform(norm_train.loc[tr_mask, [volume_col]])
            if va_mask.any():
                norm_val.loc[va_mask,   'volume_norm'] = vol_scaler.transform(norm_val.loc[va_mask,   [volume_col]])
            if te_mask.any():
                norm_test.loc[te_mask,  'volume_norm'] = vol_scaler.transform(norm_test.loc[te_mask,  [volume_col]])

        # ── Returns: StandardScaler ──────────────────────────────────────
        if return_col in norm_train.columns:
            ret_scaler = StandardScaler()
            ret_scaler.fit(norm_train.loc[tr_mask, [return_col]])
            norm_train.loc[tr_mask, 'return_norm'] = ret_scaler.transform(norm_train.loc[tr_mask, [return_col]])
            if va_mask.any():
                norm_val.loc[va_mask,   'return_norm'] = ret_scaler.transform(norm_val.loc[va_mask,   [return_col]])
            if te_mask.any():
                norm_test.loc[te_mask,  'return_norm'] = ret_scaler.transform(norm_test.loc[te_mask,  [return_col]])

    print(f"[SUCCESS] Normalization complete (scalers fitted on train only)")
    print(f"  - Prices  : MinMaxScaler  -> open_norm, high_norm, low_norm, close_norm")
    print(f"  - Volume  : StandardScaler -> volume_norm")
    print(f"  - Returns : StandardScaler -> return_norm")

    return norm_train, norm_val, norm_test


def select_model_features(df):
    """
    Select relevant feature columns.
    NOTE: ffill/fillna is intentionally NOT applied here —
    it is applied per-split in apply_ffill_per_split() to prevent
    values from the validation/test period filling training rows (FIX 2).
    """
    print("\n" + "="*60)
    print("SELECTING MODEL FEATURES")
    print("="*60)

    essential_cols = [c for c in ['ticker', 'date', 'target', 'next_day_return'] if c in df.columns]

    feature_patterns = [
        'sma_', 'ema_', 'macd', 'rsi_', 'bb_', 'return_norm', 'volatility',
        'sentiment', 'volume_ratio', 'volume_norm', 'sp500_return',
        'momentum', 'price_to', 'excess_return', 'market_up', 'market_down',
        'open_norm', 'high_norm', 'low_norm', 'close_norm',
    ]
    feature_cols = [
        c for c in df.columns
        if any(p in c for p in feature_patterns) and c not in essential_cols
    ]
    if 'news_count' in df.columns:
        feature_cols.append('news_count')

    selected = list(dict.fromkeys(essential_cols + feature_cols))
    selected = [c for c in selected if c in df.columns]

    print(f"Selected {len(selected)} columns ({len(essential_cols)} essential + {len(feature_cols)} features)")
    return df[selected].copy()


def apply_ffill_per_split(train_df, val_df, test_df):
    """
    FIX 2: Forward-fill NaN values within each split independently.
    This prevents a NaN at the end of training being filled with a value
    from the validation period.
    """
    print("\n" + "="*60)
    print("FILLING NaN VALUES (per-split — FIX 2)")
    print("="*60)

    results = []
    for name, split in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
        before = split.isnull().sum().sum()
        split = split.sort_values(['ticker', 'date'])
        split = split.ffill().fillna(0)
        after = split.isnull().sum().sum()
        print(f"  {name}: filled {before - after:,} NaN values (ffill within split, then 0)")
        results.append(split)

    return results[0], results[1], results[2]


def create_rag_context_file(df):
    """Create a file mapping ticker-date to source information for RAG"""
    print("\n" + "="*60)
    print("CREATING RAG CONTEXT FILE")
    print("="*60)

    rag_cols = [c for c in ['ticker', 'date', 'text', 'news_count', 'source'] if c in df.columns]
    if len(rag_cols) > 2:
        rag_df = df[rag_cols].copy()
        if 'text' in rag_df.columns:
            rag_df = rag_df[rag_df['text'].notna()]
        output_file = PROCESSED_DIR / "rag_context.parquet"
        rag_df.to_parquet(output_file, index=False)
        print(f"[SUCCESS] Created RAG context file: {output_file} ({len(rag_df):,} records)")
    else:
        print("[WARNING] Insufficient columns for RAG context file")


def create_final_summary(train_df, val_df, test_df):
    """Create final pipeline summary"""
    print("\n" + "="*60)
    print("FINAL PIPELINE SUMMARY")
    print("="*60)

    summary = {
        "pipeline_completion_timestamp": pd.Timestamp.now().isoformat(),
        "leakage_fixes_applied": [
            "FIX 1: Scalers fitted on training split only; val/test transformed without refitting",
            "FIX 2: ffill applied within each split independently after date cutoff",
        ],
        "splits": {},
    }

    for name, split in [("train", train_df), ("validation", val_df), ("test", test_df)]:
        entry = {
            "records": len(split),
            "date_range": {
                "start": str(split['date'].min().date()),
                "end":   str(split['date'].max().date()),
            },
            "tickers": split['ticker'].nunique(),
            "features": len(split.columns) - 4,
        }
        if 'target' in split.columns:
            entry["target_distribution"] = split['target'].value_counts().to_dict()
        summary["splits"][name] = entry
        print(f"  {name.capitalize():12s}: {entry['records']:>8,} records  "
              f"{entry['date_range']['start']} to {entry['date_range']['end']}")

    summary_file = PROCESSED_DIR / "05_final_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved to: {summary_file}")
    return summary


def main():
    """Main merging and splitting function"""
    print("\n" + "="*80)
    print("STAGE 5: MERGING, SPLITTING AND NORMALIZATION")
    print("="*80)
    print("Leakage fixes: scalers fitted on train only (FIX 1); ffill per-split (FIX 2).")

    # Load feature-engineered data (output of Stage 4 — un-normalized)
    print("\nLoading feature-engineered data...")
    df = pd.read_parquet(PROCESSED_DIR / "data_engineered.parquet")
    print(f"Loaded {len(df):,} records with {len(df.columns)} columns")

    # Select model features (no ffill yet)
    df_selected = select_model_features(df)

    # Step 1: Temporal split
    train_df, val_df, test_df = create_temporal_split(df_selected)

    # Step 2: Normalize using train-fit scalers only (FIX 1)
    train_df, val_df, test_df = normalize_splits(train_df, val_df, test_df)

    # Step 3: ffill within each split independently (FIX 2)
    train_df, val_df, test_df = apply_ffill_per_split(train_df, val_df, test_df)

    # Save final datasets
    print("\nSaving final datasets...")
    train_df.to_parquet(PROCESSED_DIR / "train_final.parquet", index=False)
    val_df.to_parquet(PROCESSED_DIR   / "val_final.parquet",   index=False)
    test_df.to_parquet(PROCESSED_DIR  / "test_final.parquet",  index=False)
    print("[SUCCESS] Saved train_final, val_final, test_final")

    # Create RAG context file
    create_rag_context_file(df)

    # Final summary
    create_final_summary(train_df, val_df, test_df)

    print("\n" + "="*80)
    print("STAGE 5 COMPLETE")
    print("="*80)
    print("\nAll processed data saved to: data/processed/")
    print("  - train_final.parquet")
    print("  - val_final.parquet")
    print("  - test_final.parquet")
    print("  - rag_context.parquet")


if __name__ == "__main__":
    main()
