"""
Explainability evaluation pipeline — single module, run as:

    python -m src.evaluation.explainability build   [--min-per-split 200]
    python -m src.evaluation.explainability run      [--limit N] [--train-only]
    python -m src.evaluation.explainability export   [--max 100]
    python -m src.evaluation.explainability all      [--min-per-split 200 --limit N --max 100]

Steps:
  build  — Extract prompts from Neo4j + processed data (val/test splits), write prompts_train/test.jsonl
  run    — Send prompts through LiteLLM analyst, score with LLM judge, compute metrics, save plots
  export — Write demo_embed.js and eval_summary_embed.js into assets/ for index.html
  all    — build + run + export in sequence
"""

import argparse
import json
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_EVAL = REPO_ROOT / "data" / "eval"
REPORTS_FIGURES = REPO_ROOT / "reports" / "figures" / "eval"
ASSETS = REPO_ROOT / "assets"
CLASSES = ["buy", "hold", "sell"]

sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _load_sector_index() -> dict[str, str]:
    p = REPO_ROOT / "data" / "raw" / "finnhub_stocks" / "_sector_index.json"
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def _parse_recommendation(text: str) -> str:
    for line in (text or "").splitlines():
        up = line.strip().upper()
        if up.startswith("RECOMMENDATION:"):
            for c in CLASSES:
                if c.upper() in up:
                    return c
    return "hold"


def _read_jsonl(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def _write_jsonl(records: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# BUILD — extract prompts from Neo4j + processed data
# ---------------------------------------------------------------------------

def build_prompts(total: int = 50, train_ratio: float = 0.8, seed: int = 42):
    from src.agents.data_context import get_finnhub_tickers, get_processed_df
    from src.agents.graph_context import get_stock_context
    from src.agents.prompt_builder import (
        build_analyst_prompt_variant,
        context_summary_for_judge,
        PROMPT_VARIANTS,
    )

    n_train = int(total * train_ratio)
    n_test = total - n_train
    split_sizes = {"train": n_train, "test": n_test}
    sector_index = _load_sector_index()
    DATA_EVAL.mkdir(parents=True, exist_ok=True)

    for split_label, split_key in [("train", "validation"), ("test", "test")]:
        target_n = split_sizes[split_label]
        df = get_processed_df(split_key)
        if df is None or len(df) == 0:
            print(f"[{split_label}] No data in {split_key} split — skipping.")
            continue
        fh = get_finnhub_tickers()
        if fh:
            df = df[df["ticker"].astype(str).str.upper().isin(fh)]
        if len(df) == 0:
            print(f"[{split_label}] No Finnhub tickers in {split_key} split — skipping.")
            continue

        n_sample = min(len(df), target_n)
        df_s = df.sample(n=n_sample, random_state=seed if split_label == "train" else seed + 1)
        records: list[dict] = []

        for _, row in df_s.iterrows():
            if len(records) >= target_n:
                break
            ticker = str(row.get("ticker", "")).strip().upper()
            ctx = get_stock_context(ticker, news_limit=5, earnings_limit=4)
            if not ctx.get("found"):
                continue
            data_row = {
                "ticker": ticker,
                "date": str(row.get("date")),
                "target": str(row.get("target", "hold")).lower(),
                "next_day_return": float(row["next_day_return"]) if "next_day_return" in row.index and row.get("next_day_return") is not None else None,
                "close": float(row["close"]) if "close" in row.index and row.get("close") is not None else None,
                "news_count": int(row["news_count"]) if "news_count" in row.index and row.get("news_count") is not None else 0,
            }
            remaining = target_n - len(records)
            variants = PROMPT_VARIANTS[:remaining] if remaining < len(PROMPT_VARIANTS) else PROMPT_VARIANTS
            for v in variants:
                records.append({
                    "ticker": ticker,
                    "date": data_row["date"],
                    "sector": sector_index.get(ticker, "unknown"),
                    "ground_truth": data_row["target"],
                    "prompt_variant": v,
                    "prompt_text": build_analyst_prompt_variant(ctx, data_row, variant=v),
                    "context_summary": context_summary_for_judge(ctx, data_row),
                })
                if len(records) >= target_n:
                    break

        out = DATA_EVAL / f"prompts_{split_label}.jsonl"
        _write_jsonl(records[:target_n], out)
        print(f"[{split_label}] {len(records[:target_n])} prompts -> {out}")


# ---------------------------------------------------------------------------
# RUN — send through LiteLLM analyst + judge, compute metrics, save plots
# ---------------------------------------------------------------------------

def _call_analyst(prompt_text: str) -> str:
    from openai import OpenAI
    client = OpenAI(
        base_url=os.environ.get("LITELLM_BASE_URL", "http://localhost:4000"),
        api_key=os.environ.get("LITELLM_MASTER_KEY", "sk-ds288r"),
    )
    model = os.environ.get("LITELLM_MODEL", "gpt-5.2-chat")
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt_text}],
        max_tokens=500,
    )
    return (resp.choices[0].message.content or "").strip()


def _call_judge(context_summary: str, model_output: str, gt: str) -> dict:
    from src.agents.llm_judge import judge_sync
    return judge_sync(context_summary, model_output, ground_truth_target=gt)


def _compute_metrics(results: list[dict]) -> dict:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
    y_true = [r["ground_truth"] for r in results]
    y_pred = [r["predicted"] for r in results]
    f_vals = [r["judge_faithfulness"] for r in results if r.get("judge_faithfulness") is not None]
    r_vals = [r["judge_relevance"] for r in results if r.get("judge_relevance") is not None]
    c_vals = [r["judge_consistency"] for r in results if r.get("judge_consistency") is not None]
    cr_vals = [r["judge_correctness"] for r in results if r.get("judge_correctness") is not None]
    return {
        "n": len(results),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "judge_faithfulness_mean": round(float(np.mean(f_vals)), 4) if f_vals else None,
        "judge_relevance_mean": round(float(np.mean(r_vals)), 4) if r_vals else None,
        "judge_consistency_mean": round(float(np.mean(c_vals)), 4) if c_vals else None,
        "judge_correctness_mean": round(float(np.mean(cr_vals)), 4) if cr_vals else None,
    }


def _plot_confusion(y_true, y_pred, labels, path: Path):
    from sklearn.metrics import confusion_matrix
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels))); ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels); ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted"); ax.set_ylabel("True")
    ax.set_title("Confusion Matrix")
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black")
    plt.colorbar(im, ax=ax)
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _plot_judge(results, path: Path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data = [[r.get(k) for r in results if r.get(k) is not None]
            for k in ("judge_faithfulness", "judge_relevance", "judge_consistency", "judge_correctness")]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.boxplot(data, tick_labels=["Faithfulness", "Relevance", "Consistency", "Correctness"])
    ax.set_ylabel("Score (1-5)"); ax.set_ylim(0, 6)
    ax.set_title("LLM Judge Score Distribution")
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def _plot_sector_accuracy(results, path: Path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    by_sec: dict[str, dict] = defaultdict(lambda: {"c": 0, "t": 0})
    for r in results:
        s = r.get("sector", "unknown")
        by_sec[s]["t"] += 1; by_sec[s]["c"] += r.get("correct", 0)
    sectors = sorted(by_sec); accs = [by_sec[s]["c"] / by_sec[s]["t"] for s in sectors]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(sectors, accs, color=["#3182ce", "#38a169", "#d69e2e"][:len(sectors)])
    ax.set_ylabel("Accuracy"); ax.set_xlabel("Sector"); ax.set_ylim(0, 1)
    ax.set_title("Accuracy by Sector")
    plt.tight_layout(); plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()


def run_eval(limit: int | None = None, train_only: bool = False):
    from tqdm import tqdm
    import time as _time

    REPORTS_FIGURES.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {}
    labels = CLASSES

    for split_label in (["train"] if train_only else ["train", "test"]):
        prompts = _read_jsonl(DATA_EVAL / f"prompts_{split_label}.jsonl")
        if not prompts:
            print(f"[{split_label}] No prompts found — run 'build' first.")
            continue
        if limit:
            prompts = prompts[:limit]
        print(f"\n{'='*60}")
        print(f"[{split_label.upper()}] Evaluating {len(prompts)} prompts")
        print(f"{'='*60}")
        results: list[dict] = []
        correct_count = 0
        pbar = tqdm(prompts, desc=f"{split_label}", unit="prompt",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
        for i, rec in enumerate(pbar):
            t0 = _time.time()
            ticker = rec.get("ticker", "?")
            variant = rec.get("prompt_variant", "?")

            try:
                model_output = _call_analyst(rec["prompt_text"])
            except Exception as e:
                model_output = f"[Error: {e}]"
            pred = _parse_recommendation(model_output)
            gt = (rec.get("ground_truth") or "hold").lower()

            try:
                judge = _call_judge(rec["context_summary"], model_output, gt)
            except Exception as e:
                judge = {k: None for k in ("faithfulness", "relevance", "consistency", "correctness")}

            is_correct = 1 if pred == gt else 0
            correct_count += is_correct
            results.append({
                **rec,
                "model_output": model_output,
                "predicted": pred,
                "ground_truth": gt,
                "correct": is_correct,
                "judge_faithfulness": judge.get("faithfulness"),
                "judge_relevance": judge.get("relevance"),
                "judge_consistency": judge.get("consistency"),
                "judge_correctness": judge.get("correctness"),
            })
            elapsed = _time.time() - t0
            acc_so_far = correct_count / (i + 1)
            mark = "+" if is_correct else "x"
            pbar.set_postfix_str(
                f"{mark} {ticker}/{variant} pred={pred} gt={gt} "
                f"j={judge.get('correctness','?')} acc={acc_so_far:.0%} {elapsed:.1f}s"
            )
        pbar.close()
        _write_jsonl(results, DATA_EVAL / f"results_{split_label}.jsonl")
        metrics = _compute_metrics(results)
        summary[split_label] = metrics
        print(f"[{split_label}] Metrics: {metrics}")

        y_t = [r["ground_truth"] for r in results]
        y_p = [r["predicted"] for r in results]
        try:
            _plot_confusion(y_t, y_p, labels, REPORTS_FIGURES / f"confusion_{split_label}.png")
            _plot_judge(results, REPORTS_FIGURES / f"judge_scores_{split_label}.png")
            _plot_sector_accuracy(results, REPORTS_FIGURES / f"accuracy_by_sector_{split_label}.png")
        except Exception as e:
            print(f"  Plot error: {e}")

    # save summary
    summary_path = REPO_ROOT / "reports" / "eval_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary: {summary_path}")

    # copy plots + embed to assets
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "figures" / "eval").mkdir(parents=True, exist_ok=True)
    for p in REPORTS_FIGURES.glob("*.png"):
        shutil.copy(p, ASSETS / "figures" / "eval" / p.name)
    with open(ASSETS / "eval_summary_embed.js", "w") as f:
        f.write("var EVAL_SUMMARY = "); f.write(json.dumps(summary)); f.write(";\n")


# ---------------------------------------------------------------------------
# EXPORT — write demo_embed.js for index.html
# ---------------------------------------------------------------------------

def export_demo(max_entries: int = 100):
    results = _read_jsonl(DATA_EVAL / "results_test.jsonl")
    if not results:
        print("No test results. Run 'run' first.")
        return
    entries = []
    for r in results[:max_entries]:
        preview = (r.get("prompt_text") or "")[:500]
        if len(r.get("prompt_text") or "") > 500:
            preview += "..."
        entries.append({
            "ticker": r.get("ticker"),
            "date": r.get("date"),
            "sector": r.get("sector"),
            "prompt_preview": preview,
            "output": r.get("model_output"),
            "ground_truth": r.get("ground_truth"),
            "predicted": r.get("predicted"),
            "correct": bool(r.get("correct")),
            "judge": {k: r.get(f"judge_{k}") for k in ("faithfulness", "relevance", "consistency", "correctness")},
        })
    ASSETS.mkdir(parents=True, exist_ok=True)
    with open(ASSETS / "demo_data.json", "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    with open(ASSETS / "demo_embed.js", "w", encoding="utf-8") as f:
        f.write("var DEMO_DATA = "); f.write(json.dumps(entries, ensure_ascii=False)); f.write(";\n")
    print(f"Exported {len(entries)} entries -> assets/demo_embed.js")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(prog="python -m src.evaluation.explainability")
    sub = ap.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="Build prompt datasets from Neo4j + processed data")
    b.add_argument("--total", type=int, default=50, help="Total prompts (default 50)")
    b.add_argument("--train-ratio", type=float, default=0.8, help="Train fraction (default 0.8 = 80/20)")
    b.add_argument("--seed", type=int, default=42)

    r = sub.add_parser("run", help="Run analyst + judge eval, save results/plots")
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--train-only", action="store_true")

    e = sub.add_parser("export", help="Export demo data for index.html")
    e.add_argument("--max", type=int, default=100)

    a = sub.add_parser("all", help="build + run + export in sequence")
    a.add_argument("--total", type=int, default=50)
    a.add_argument("--train-ratio", type=float, default=0.8)
    a.add_argument("--limit", type=int, default=None)
    a.add_argument("--max", type=int, default=100)
    a.add_argument("--seed", type=int, default=42)

    args = ap.parse_args()

    if args.cmd == "build":
        build_prompts(args.total, args.train_ratio, args.seed)
    elif args.cmd == "run":
        run_eval(args.limit, args.train_only)
    elif args.cmd == "export":
        export_demo(args.max)
    elif args.cmd == "all":
        build_prompts(args.total, args.train_ratio, args.seed)
        run_eval(args.limit)
        export_demo(args.max)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
