"""Download FNSPID data directly from HuggingFace repo."""
import os, sys, zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "raw" / "fnspid"
KEY_FILE = BASE / ".key"


def load_token():
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("HF_TOKEN="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("HF_TOKEN")


def main():
    from huggingface_hub import hf_hub_download

    token = load_token()
    sys.stdout.write(f"[FNSPID] HF token: {'yes' if token else 'NO'}\n")
    sys.stdout.flush()

    # --- 1) Stock News: download to HF cache, create reference ---
    news_dir = DATA / "Stock_news"
    news_file = news_dir / "All_external.csv"
    ref_file = news_dir / "_cache_path.txt"

    if news_file.exists():
        mb = news_file.stat().st_size / (1024 * 1024)
        sys.stdout.write(f"[FNSPID] News SKIP - already on disk ({mb:,.0f} MB)\n")
        sys.stdout.flush()
    else:
        news_dir.mkdir(parents=True, exist_ok=True)
        sys.stdout.write("[FNSPID] Downloading Stock_news/All_external.csv (5.5 GB) ...\n")
        sys.stdout.flush()

        cached = hf_hub_download(
            "Zihan1004/FNSPID",
            "Stock_news/All_external.csv",
            repo_type="dataset",
            token=token,
        )
        cached_path = Path(cached)
        mb = cached_path.stat().st_size / (1024 * 1024)
        sys.stdout.write(f"[FNSPID] News downloaded to HF cache ({mb:,.0f} MB)\n")
        sys.stdout.flush()

        # Save cache path reference (avoids 5.5 GB copy to OneDrive)
        ref_file.write_text(str(cached_path))
        sys.stdout.write(f"[FNSPID] Cache ref saved to {ref_file}\n")

        # Try to create a symlink instead of copying
        try:
            if not news_file.exists():
                os.symlink(cached_path, news_file)
                sys.stdout.write(f"[FNSPID] Symlink created: {news_file}\n")
        except OSError:
            sys.stdout.write(f"[FNSPID] Symlink not available; use cache path from {ref_file}\n")
        sys.stdout.flush()

    # --- 2) Stock Prices (full_history.zip) - 562 MB ---
    price_base = DATA / "Stock_price"
    price_dir = price_base / "full_history"
    price_marker = price_base / "_extracted"

    if price_marker.exists():
        n = len(list(price_dir.glob("**/*.csv"))) if price_dir.exists() else 0
        sys.stdout.write(f"[FNSPID] Prices SKIP - already extracted ({n} CSVs)\n")
        sys.stdout.flush()
    else:
        price_dir.mkdir(parents=True, exist_ok=True)
        sys.stdout.write("[FNSPID] Downloading Stock_price/full_history.zip (562 MB) ...\n")
        sys.stdout.flush()

        cached = hf_hub_download(
            "Zihan1004/FNSPID",
            "Stock_price/full_history.zip",
            repo_type="dataset",
            token=token,
        )
        sys.stdout.write("[FNSPID] Zip downloaded, extracting ...\n")
        sys.stdout.flush()

        with zipfile.ZipFile(cached, "r") as zf:
            zf.extractall(price_dir)

        n = len(list(price_dir.glob("**/*.csv")))
        price_marker.write_text("done")
        sys.stdout.write(f"[FNSPID] Prices extracted: {n} CSV files\n")
        sys.stdout.flush()

    sys.stdout.write("[FNSPID] DONE\n")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stdout.write(f"[FNSPID] ERROR: {e}\n")
        import traceback; traceback.print_exc()
        sys.exit(1)
