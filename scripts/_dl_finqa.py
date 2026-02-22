"""Download FinQA — direct download from GitHub (bypasses load_dataset)."""
import os, sys, json, zipfile, io, time
from pathlib import Path
from urllib.request import urlretrieve

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "raw" / "finqa"

GITHUB_ZIP = "https://github.com/czyssrs/FinQA/archive/refs/heads/main.zip"

def main():
    DATA.mkdir(parents=True, exist_ok=True)

    expected = ["finqa_train.json", "finqa_validation.json", "finqa_test.json"]
    if all((DATA / f).exists() for f in expected):
        total = 0
        for f in expected:
            n = len(json.load(open(DATA / f)))
            total += n
            print(f"[FinQA] SKIP {f} - {n:,} records on disk")
        print(f"[FinQA] Total: {total:,}")
        return

    print("[FinQA] Downloading from GitHub czyssrs/FinQA ...")
    zip_path = DATA / "_finqa_repo.zip"

    def progress(block, block_size, total_size):
        mb = block * block_size / (1024 * 1024)
        if total_size > 0:
            pct = min(100, block * block_size * 100 / total_size)
            print(f"\r[FinQA]   {mb:.1f} MB ({pct:.0f}%)", end="", flush=True)
        else:
            print(f"\r[FinQA]   {mb:.1f} MB", end="", flush=True)

    urlretrieve(GITHUB_ZIP, zip_path, reporthook=progress)
    print(f"\n[FinQA] Downloaded -> {zip_path.name}")

    print("[FinQA] Extracting JSON splits ...")
    split_map = {
        "train.json": "finqa_train.json",
        "dev.json":   "finqa_validation.json",
        "test.json":  "finqa_test.json",
    }

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        found = 0
        for name in names:
            basename = Path(name).name
            if basename in split_map:
                parent_dir = Path(name).parent.name
                if parent_dir == "dataset":
                    target = DATA / split_map[basename]
                    data = json.loads(zf.read(name))
                    with open(target, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, default=str)
                    print(f"[FinQA] {split_map[basename]}: {len(data):,} records")
                    found += 1

        if found == 0:
            json_files = [n for n in names if n.endswith(".json")]
            print(f"[FinQA] WARNING: No dataset/*.json found. JSON files in archive:")
            for jf in json_files[:20]:
                print(f"[FinQA]   {jf}")

    zip_path.unlink(missing_ok=True)

    total = 0
    for f in expected:
        fp = DATA / f
        if fp.exists():
            n = len(json.load(open(fp)))
            total += n
    print(f"[FinQA] DONE - {total:,} records total")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FinQA] ERROR: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
