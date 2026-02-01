"""
Main Pipeline Runner
Executes all pipeline stages in sequence
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add scripts to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

# Import pipeline stages
import scripts.load_data as stage1
import scripts.clean_data as stage2
import scripts.align_data as stage3
import scripts.feature_engineering as stage4
import scripts.merge_and_split as stage5


def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(text.center(80))
    print("="*80 + "\n")


def run_pipeline():
    """Run the complete data pipeline"""
    start_time = time.time()
    
    print_header("FINANCIAL DATA PIPELINE")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    stages = [
        ("STAGE 1: DATA LOADING", stage1.main),
        ("STAGE 2: DATA CLEANING", stage2.main),
        ("STAGE 3: TEMPORAL ALIGNMENT", stage3.main),
        ("STAGE 4: FEATURE ENGINEERING", stage4.main),
        ("STAGE 5: MERGING AND SPLITTING", stage5.main)
    ]
    
    completed_stages = []
    
    for stage_name, stage_func in stages:
        print_header(f"Running: {stage_name}")
        stage_start = time.time()
        
        try:
            stage_func()
            stage_duration = time.time() - stage_start
            completed_stages.append((stage_name, True, stage_duration))
            print(f"\n✓ {stage_name} completed in {stage_duration:.1f} seconds")
        except Exception as e:
            stage_duration = time.time() - stage_start
            completed_stages.append((stage_name, False, stage_duration))
            print(f"\n✗ {stage_name} FAILED after {stage_duration:.1f} seconds")
            print(f"Error: {e}")
            
            import traceback
            traceback.print_exc()
            
            print("\n" + "="*80)
            print("PIPELINE STOPPED DUE TO ERROR")
            print("="*80)
            return False
    
    # Summary
    total_duration = time.time() - start_time
    print_header("PIPELINE COMPLETE")
    
    print("Stage Summary:")
    for stage_name, success, duration in completed_stages:
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"  {status:12s} {stage_name:45s} ({duration:6.1f}s)")
    
    print(f"\nTotal pipeline duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n" + "="*80)
    print("Processed datasets ready at: data/processed/")
    print("  - train_final.parquet")
    print("  - val_final.parquet")
    print("  - test_final.parquet")
    print("  - rag_context.parquet")
    print("  - sentiment_model.pkl")
    print("="*80 + "\n")
    
    return True


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
