"""
EDA Pipeline Runner

Executes 01_EDA.ipynb end-to-end, generating plots, summaries, and
insights into eda/outputs/.

Usage (from repo root):
    python eda/run_eda.py              Run full EDA pipeline
    python eda/run_eda.py --check      Verify raw data exists before running

Prerequisites:
    - Raw data in data/raw/ (FNSPID, Phrasebank, Finnhub, FinQA, S&P 500)
      Run 'python scripts/download_all_data.py' first.
    - Required packages: jupyter, nbformat, nbclient, scipy, scikit-learn
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
NOTEBOOK_PATH = BASE_DIR / "01_EDA.ipynb"
OUTPUT_DIR = BASE_DIR / "outputs"
RAW_DIR = REPO_ROOT / "data" / "raw"

REQUIRED_DATA = {
    "FNSPID Prices":   RAW_DIR / "fnspid" / "Stock_price" / "full_history",
    "Phrasebank":      RAW_DIR / "financial_phrasebank",
    "Finnhub Stocks":  RAW_DIR / "finnhub_stocks",
    "FinQA":           RAW_DIR / "finqa",
    "S&P 500":         RAW_DIR / "yahoo_sp500" / "sp500_1999_2023.csv",
}


def header(text):
    print("\n" + "=" * 70)
    print(text.center(70))
    print("=" * 70 + "\n")


def check_data():
    """Verify all raw datasets exist."""
    found, missing = 0, 0
    for name, path in REQUIRED_DATA.items():
        if path.exists():
            found += 1
            if path.is_file():
                mb = path.stat().st_size / (1024 * 1024)
                print(f"  [  OK  ] {name:<20} ({mb:.1f} MB)")
            else:
                n = len(list(path.rglob("*")))
                print(f"  [  OK  ] {name:<20} ({n} files)")
        else:
            missing += 1
            print(f"  [MISSING] {name:<20} {path}")

    print(f"\n  {found}/{found + missing} datasets found")
    return missing == 0


def run_notebook():
    """Execute the EDA notebook programmatically."""
    try:
        import nbformat
        from nbclient import NotebookClient
    except ImportError:
        print("  ERROR: pip install nbformat nbclient")
        return False

    print(f"  Loading: {NOTEBOOK_PATH.name}")
    nb = nbformat.read(str(NOTEBOOK_PATH), as_version=4)

    client = NotebookClient(
        nb,
        timeout=900,
        kernel_name="python3",
        resources={"metadata": {"path": str(BASE_DIR)}},
    )

    print("  Executing cells...")
    start = time.time()
    try:
        client.execute()
        elapsed = time.time() - start
        print(f"  Completed in {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  FAILED after {elapsed:.1f}s: {e}")
        return False

    executed = NOTEBOOK_PATH.with_name("01_EDA_executed.ipynb")
    nbformat.write(nb, str(executed))
    print(f"  Saved executed notebook: {executed.name}")
    return True


def list_outputs():
    """Print generated output files."""
    if not OUTPUT_DIR.exists():
        return
    files = sorted(OUTPUT_DIR.glob("*"))
    if not files:
        return
    print(f"  Output directory: {OUTPUT_DIR.relative_to(REPO_ROOT)}/")
    print("  " + "-" * 55)
    for f in files:
        if f.name.startswith("."):
            continue
        sz = f.stat().st_size
        if sz > 1024 * 1024:
            print(f"    {f.name:<45} {sz / 1024 / 1024:>6.1f} MB")
        else:
            print(f"    {f.name:<45} {sz / 1024:>6.1f} KB")


def main():
    parser = argparse.ArgumentParser(description="Run the EDA pipeline")
    parser.add_argument("--check", action="store_true",
                        help="Only verify data, don't run")
    args = parser.parse_args()

    header("EDA PIPELINE")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Root:    {REPO_ROOT}\n")

    header("STEP 1: VERIFY RAW DATA")
    all_present = check_data()

    if args.check:
        sys.exit(0 if all_present else 1)

    if not all_present:
        print("\n  WARNING: Some datasets missing. Notebook may skip those sections.")

    OUTPUT_DIR.mkdir(exist_ok=True)

    header("STEP 2: EXECUTE EDA NOTEBOOK")
    ok = run_notebook()
    if not ok:
        sys.exit(1)

    header("STEP 3: OUTPUT SUMMARY")
    list_outputs()

    header("EDA PIPELINE COMPLETE")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Outputs:  {OUTPUT_DIR.relative_to(REPO_ROOT)}/")
    print(f"  Notebook: {NOTEBOOK_PATH.relative_to(REPO_ROOT)}\n")


if __name__ == "__main__":
    main()
