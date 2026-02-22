"""
DSC288 - Parallel Data Download

Launches individual download scripts concurrently:
  1. FNSPID News          HuggingFace  (scripts/_dl_fnspid.py)
  2. Financial Phrasebank HuggingFace  (scripts/_dl_phrasebank.py)
  3. FinQA                GitHub       (scripts/_dl_finqa.py)
  4. Stock Prices         Finnhub API  (scripts/_dl_stocks.py)

Usage:
    python scripts/download_all_data.py
"""
import subprocess, sys, time, threading
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
SCRIPTS = [
    ("FNSPID News",  BASE / "scripts" / "_dl_fnspid.py"),
    ("Phrasebank",   BASE / "scripts" / "_dl_phrasebank.py"),
    ("FinQA",        BASE / "scripts" / "_dl_finqa.py"),
    ("Stocks",       BASE / "scripts" / "_dl_stocks.py"),
]


def run_script(name, script_path):
    """Run a download script and capture result."""
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, timeout=1800,
        )
        return {
            "name": name,
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"name": name, "ok": False, "stdout": "", "stderr": "TIMEOUT (30 min)"}
    except Exception as e:
        return {"name": name, "ok": False, "stdout": "", "stderr": str(e)}


def main():
    print("=" * 70)
    print("  DSC288 - Parallel Data Download")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Launching {len(SCRIPTS)} downloads in parallel ...")
    print("=" * 70)
    print()

    threads = {}
    results = {}

    def worker(name, path):
        results[name] = run_script(name, path)

    for name, path in SCRIPTS:
        t = threading.Thread(target=worker, args=(name, path), daemon=True)
        t.start()
        threads[name] = t

    for name, t in threads.items():
        t.join()
        r = results[name]
        print(r.get("stdout", ""))
        if r.get("stderr"):
            for line in r["stderr"].splitlines():
                if "WARNING" in line or "Error" in line or "error" in line:
                    print(f"  STDERR: {line}")

    print()
    print("=" * 70)
    print("  DOWNLOAD SUMMARY")
    print("=" * 70)
    all_ok = True
    for name, _ in SCRIPTS:
        r = results.get(name, {})
        status = "  OK  " if r.get("ok") else "FAILED"
        print(f"    [{status}]  {name}")
        if not r.get("ok"):
            all_ok = False

    if all_ok:
        print("\n  All datasets ready!")
    else:
        failed = [n for n, _ in SCRIPTS if not results.get(n, {}).get("ok")]
        print(f"\n  Failed: {', '.join(failed)}")
        print("  Re-run to retry. Already-downloaded data is preserved.")
    print("=" * 70)

    return all_ok


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
