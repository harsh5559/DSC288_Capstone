"""Download Financial Phrasebank — direct zip download (bypasses load_dataset)."""
import os, sys, zipfile, io
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "raw" / "financial_phrasebank" / "data" / "FinancialPhraseBank-v1.0"

def main():
    DATA.mkdir(parents=True, exist_ok=True)

    expected_files = [
        "Sentences_AllAgree.txt",
        "Sentences_75Agree.txt",
        "Sentences_66Agree.txt",
        "Sentences_50Agree.txt",
    ]
    if all((DATA / f).exists() for f in expected_files):
        for f in expected_files:
            n = sum(1 for _ in open(DATA / f, encoding="latin-1"))
            print(f"[Phrasebank] SKIP {f} - {n:,} sentences on disk")
        return

    from huggingface_hub import hf_hub_download
    print("[Phrasebank] Downloading zip from takala/financial_phrasebank ...")
    zip_path = hf_hub_download(
        "takala/financial_phrasebank",
        "data/FinancialPhraseBank-v1.0.zip",
        repo_type="dataset",
    )
    print(f"[Phrasebank] Downloaded -> {zip_path}")

    print("[Phrasebank] Extracting ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        print(f"[Phrasebank] Archive contains {len(names)} files")
        for name in names:
            basename = Path(name).name
            if basename.startswith("Sentences_") and basename.endswith(".txt"):
                target = DATA / basename
                with zf.open(name) as src:
                    target.write_bytes(src.read())
                n = sum(1 for _ in open(target, encoding="latin-1"))
                print(f"[Phrasebank] Extracted {basename}: {n:,} sentences")

    total = 0
    for f in expected_files:
        fp = DATA / f
        if fp.exists():
            n = sum(1 for _ in open(fp, encoding="latin-1"))
            total += n
    print(f"[Phrasebank] DONE - {total:,} sentences across {len(expected_files)} files")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[Phrasebank] ERROR: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
