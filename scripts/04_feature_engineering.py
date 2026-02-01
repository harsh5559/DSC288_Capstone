"""
Stage 4: Feature Engineering & Normalization
Create derived features and normalize data for model training
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


def add_normalized_features(df):
    """Add normalized price and volume features"""
    print("\n" + "="*60)
    print("FEATURE NORMALIZATION")
    print("="*60)
    
    # Initialize scalers
    price_scaler = MinMaxScaler()
    volume_scaler = StandardScaler()
    return_scaler = StandardScaler()
    
    # Group by ticker for proper normalization (each stock has different price ranges)
    print("\nNormalizing features by ticker...")
    
    normalized_dfs = []
    for ticker in df['ticker'].unique():
        ticker_df = df[df['ticker'] == ticker].copy()
        
        # Min-Max scaling for prices (0-1 range per ticker)
        price_cols = ['open', 'high', 'low', 'close']
        if all(col in ticker_df.columns for col in price_cols):
            ticker_df[['open_norm', 'high_norm', 'low_norm', 'close_norm']] = \
                price_scaler.fit_transform(ticker_df[price_cols])
        
        # Standardize volume (z-score per ticker)
        if 'volume' in ticker_df.columns:
            ticker_df['volume_norm'] = volume_scaler.fit_transform(ticker_df[['volume']])
        
        # Standardize returns
        if 'next_day_return' in ticker_df.columns:
            ticker_df['return_norm'] = return_scaler.fit_transform(ticker_df[['next_day_return']])
        
        normalized_dfs.append(ticker_df)
    
    df_normalized = pd.concat(normalized_dfs, ignore_index=True)
    df_normalized = df_normalized.sort_values(['ticker', 'date']).reset_index(drop=True)
    
    print(f"[SUCCESS] Normalized {len(df_normalized):,} records")
    print(f"  - Price features: min-max scaled (0-1 range)")
    print(f"  - Volume: standardized (z-score)")
    print(f"  - Returns: standardized (z-score)")
    
    return df_normalized


def add_technical_indicators(df):
    """Add basic technical indicators (moving averages, momentum)"""
    print("\n" + "="*60)
    print("TECHNICAL INDICATORS")
    print("="*60)
    
    print("\nCalculating technical indicators by ticker...")
    
    feature_dfs = []
    for ticker in df['ticker'].unique():
        ticker_df = df[df['ticker'] == ticker].copy()
        ticker_df = ticker_df.sort_values('date')
        
        # Simple Moving Averages
        if 'close' in ticker_df.columns:
            ticker_df['sma_5'] = ticker_df['close'].rolling(window=5, min_periods=1).mean()
            ticker_df['sma_20'] = ticker_df['close'].rolling(window=20, min_periods=1).mean()
            ticker_df['sma_50'] = ticker_df['close'].rolling(window=50, min_periods=1).mean()
            
            # Price relative to moving averages
            ticker_df['price_to_sma5'] = ticker_df['close'] / ticker_df['sma_5']
            ticker_df['price_to_sma20'] = ticker_df['close'] / ticker_df['sma_20']
        
        # Momentum (rate of change)
        if 'close' in ticker_df.columns:
            ticker_df['momentum_5'] = ticker_df['close'].pct_change(periods=5)
            ticker_df['momentum_20'] = ticker_df['close'].pct_change(periods=20)
        
        # Volatility (rolling standard deviation of returns)
        if 'close' in ticker_df.columns:
            returns = ticker_df['close'].pct_change()
            ticker_df['volatility_20'] = returns.rolling(window=20, min_periods=1).std()
        
        # Volume trends
        if 'volume' in ticker_df.columns:
            ticker_df['volume_ma_20'] = ticker_df['volume'].rolling(window=20, min_periods=1).mean()
            ticker_df['volume_ratio'] = ticker_df['volume'] / ticker_df['volume_ma_20']
        
        feature_dfs.append(ticker_df)
    
    df_with_features = pd.concat(feature_dfs, ignore_index=True)
    df_with_features = df_with_features.sort_values(['ticker', 'date']).reset_index(drop=True)
    
    # Count new features
    new_features = [col for col in df_with_features.columns if col not in df.columns]
    
    print(f"[SUCCESS] Added {len(new_features)} technical indicators:")
    for feat in new_features[:10]:  # Show first 10
        print(f"  - {feat}")
    if len(new_features) > 10:
        print(f"  ... and {len(new_features) - 10} more")
    
    return df_with_features


def add_market_features(df):
    """Add market-relative features"""
    print("\n" + "="*60)
    print("MARKET-RELATIVE FEATURES")
    print("="*60)
    
    # Stock return vs market return
    if 'next_day_return' in df.columns and 'sp500_return' in df.columns:
        df['excess_return'] = df['next_day_return'] - df['sp500_return'].fillna(0)
        print("[SUCCESS] Added excess_return (stock return - market return)")
    
    # Market correlation indicator
    if 'sp500_return' in df.columns:
        df['market_up'] = (df['sp500_return'] > 0).astype(int)
        df['market_down'] = (df['sp500_return'] < 0).astype(int)
        print("[SUCCESS] Added market direction indicators")
    
    return df


def create_feature_summary(df_original, df_final):
    """Create summary of feature engineering"""
    print("\n" + "="*60)
    print("FEATURE ENGINEERING SUMMARY")
    print("="*60)
    
    # Count features by type
    original_cols = set(df_original.columns)
    new_cols = [col for col in df_final.columns if col not in original_cols]
    
    normalized_features = [col for col in new_cols if '_norm' in col]
    technical_features = [col for col in new_cols if any(x in col for x in ['sma', 'momentum', 'volatility', 'volume_ratio'])]
    market_features = [col for col in new_cols if any(x in col for x in ['excess_return', 'market_up', 'market_down'])]
    ratio_features = [col for col in new_cols if 'price_to' in col]
    
    summary = {
        "engineering_timestamp": pd.Timestamp.now().isoformat(),
        "total_records": len(df_final),
        "original_features": len(original_cols),
        "new_features": len(new_cols),
        "total_features": len(df_final.columns),
        "feature_categories": {
            "normalized": len(normalized_features),
            "technical_indicators": len(technical_features),
            "market_relative": len(market_features),
            "price_ratios": len(ratio_features)
        },
        "normalization_methods": {
            "prices": "MinMaxScaler (0-1 range, per ticker)",
            "volume": "StandardScaler (z-score, per ticker)",
            "returns": "StandardScaler (z-score, per ticker)"
        },
        "new_feature_list": new_cols
    }
    
    print(f"\nTotal records: {summary['total_records']:,}")
    print(f"Original features: {summary['original_features']}")
    print(f"New features: {summary['new_features']}")
    print(f"Total features: {summary['total_features']}")
    print(f"\nFeature categories:")
    for category, count in summary['feature_categories'].items():
        print(f"  - {category}: {count}")
    
    # Save summary
    summary_file = PROCESSED_DIR / "04_feature_engineering_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nSummary saved to: {summary_file}")
    return summary


def main():
    """Main feature engineering function"""
    print("\n" + "="*80)
    print("STAGE 4: FEATURE ENGINEERING & NORMALIZATION")
    print("="*80)
    
    # Load aligned data
    print("\nLoading aligned dataset...")
    df = pd.read_parquet(PROCESSED_DIR / "data_aligned.parquet")
    print(f"Loaded: {len(df):,} records with {len(df.columns)} columns")
    
    df_original = df.copy()
    
    # Add normalized features
    df = add_normalized_features(df)
    
    # Add technical indicators
    df = add_technical_indicators(df)
    
    # Add market-relative features
    df = add_market_features(df)
    
    # Save engineered dataset
    print("\nSaving engineered dataset...")
    output_file = PROCESSED_DIR / "data_engineered.parquet"
    df.to_parquet(output_file, index=False)
    print(f"Saved to: {output_file}")
    print(f"File size: {output_file.stat().st_size / 1024**2:.2f} MB")
    
    # Create summary
    summary = create_feature_summary(df_original, df)
    
    print("\n" + "="*80)
    print("STAGE 4 COMPLETE")
    print("="*80)
    print(f"\n[SUCCESS] Feature engineering complete!")
    print(f"  - Dataset: {len(df):,} records")
    print(f"  - Features: {len(df.columns)} total ({len(df.columns) - len(df_original.columns)} new)")
    print(f"  - Normalized: prices (min-max), volume (z-score), returns (z-score)")
    print(f"  - Technical indicators: SMA, momentum, volatility, volume ratios")
    print(f"  - Market features: excess returns, market direction")


if __name__ == "__main__":
    main()
