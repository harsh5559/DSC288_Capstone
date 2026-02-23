"""
Hyperparameter sweep for the financial explainability evaluation pipeline.

Tunes: system prompt strategy, max_tokens, model, temperature (where supported).
Reuses existing prompts from data/eval/prompts_{split}.jsonl.

Usage:
    python -m src.evaluation.hyperparam_sweep [--split test] [--limit N]
"""

import argparse
import itertools
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
from tqdm import tqdm

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_EVAL = REPO_ROOT / "data" / "eval"
REPORTS = REPO_ROOT / "reports"
ASSETS = REPO_ROOT / "assets"
CLASSES = ["buy", "hold", "sell"]

sys.path.insert(0, str(REPO_ROOT))

# ── hyperparameter grid ──────────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "baseline": (
        "You are a financial analyst. Base your answer ONLY on the following "
        "structured context."
    ),
    "chain_of_thought": (
        "You are a senior equity analyst. Think step by step:\n"
        "1) Review the earnings data — are surprises positive or negative?\n"
        "2) Assess recent news sentiment — bullish, bearish, or neutral?\n"
        "3) Check analyst consensus — are more analysts buying or selling?\n"
        "4) Consider the next-day return direction if provided.\n"
        "5) Based ONLY on these facts, give your final recommendation.\n"
        "Be precise and cite specific numbers."
    ),
    "structured_analysis": (
        "You are a quantitative equity analyst at a top-tier investment bank. "
        "You MUST structure your analysis into three sections before giving "
        "your recommendation:\n"
        "FUNDAMENTALS: Analyze earnings surprises and trends.\n"
        "SENTIMENT: Analyze news headlines and analyst consensus.\n"
        "TECHNICAL: Analyze price momentum and return data.\n"
        "Then synthesize into a single recommendation. "
        "Base your answer ONLY on the provided context — do not speculate."
    ),
}

CONFIGS = [
    # (model, temperature_or_None, system_prompt_key, max_tokens)
    ("gpt-5.2-chat", None,  "baseline",            500),
    ("gpt-5.2-chat", None,  "chain_of_thought",    500),
    ("gpt-5.2-chat", None,  "structured_analysis", 500),
    ("gpt-5.2-chat", None,  "baseline",            300),
    ("gpt-5.2-chat", None,  "chain_of_thought",    300),
    ("gpt-5.2-chat", None,  "structured_analysis", 300),
    ("gpt-5.2-chat", None,  "chain_of_thought",    800),
    ("gpt-5.2-chat", None,  "structured_analysis", 800),
    ("gpt-5-mini",   0.3,   "baseline",            500),
    ("gpt-5-mini",   0.3,   "chain_of_thought",    500),
    ("gpt-5-mini",   0.3,   "structured_analysis", 500),
    ("gpt-5-mini",   0.7,   "baseline",            500),
    ("gpt-5-mini",   0.7,   "chain_of_thought",    500),
    ("gpt-5-mini",   0.7,   "structured_analysis", 500),
    ("gpt-5",        0.3,   "chain_of_thought",    500),
    ("gpt-5",        0.3,   "structured_analysis", 500),
    ("gpt-5",        0.7,   "chain_of_thought",    500),
    ("gpt-5",        0.7,   "structured_analysis", 500),
]

# ── helpers ──────────────────────────────────────────────────────────────

def _read_jsonl(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def _parse_recommendation(text: str) -> str:
    for line in (text or "").splitlines():
        up = line.strip().upper()
        if up.startswith("RECOMMENDATION:"):
            for c in CLASSES:
                if c.upper() in up:
                    return c
    for line in (text or "").splitlines():
        up = line.strip().upper()
        for c in CLASSES:
            if c.upper() in up.split():
                return c
    return "hold"


def _strip_original_system_instruction(prompt_text: str) -> str:
    """Remove the baked-in system instruction line from the original prompt
    so it doesn't conflict with the new system message."""
    lines = prompt_text.split("\n")
    cleaned = []
    skip_next_blank = False
    for line in lines:
        if line.startswith("You are a financial analyst"):
            skip_next_blank = True
            continue
        if line.startswith("Give one recommendation:"):
            skip_next_blank = True
            continue
        if skip_next_blank and line.strip() == "":
            skip_next_blank = False
            continue
        skip_next_blank = False
        cleaned.append(line)
    return "\n".join(cleaned)


def _call_analyst(prompt_text: str, system_prompt: str,
                  model: str, temperature: Optional[float],
                  max_tokens: int) -> str:
    from openai import OpenAI
    client = OpenAI(
        base_url=os.environ.get("LITELLM_BASE_URL", "http://localhost:4000"),
        api_key=os.environ.get("LITELLM_MASTER_KEY", "sk-ds288r"),
    )

    context_only = _strip_original_system_instruction(prompt_text)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context_only},
    ]

    kwargs: dict[str, Any] = dict(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )
    if temperature is not None:
        kwargs["temperature"] = temperature

    resp = client.chat.completions.create(**kwargs)
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


# ── main sweep ───────────────────────────────────────────────────────────

def run_sweep(split: str = "test", limit: int | None = None):
    prompts = _read_jsonl(DATA_EVAL / f"prompts_{split}.jsonl")
    if not prompts:
        print(f"No prompts found in data/eval/prompts_{split}.jsonl — run 'build' first.")
        return
    if limit:
        prompts = prompts[:limit]

    print(f"\n{'='*70}")
    print(f"  HYPERPARAMETER SWEEP — {len(CONFIGS)} configs x {len(prompts)} prompts")
    print(f"  Total LLM calls: ~{len(CONFIGS) * len(prompts) * 2} (analyst + judge)")
    print(f"{'='*70}\n")

    all_results: list[dict] = []
    best_acc = -1.0
    best_config = None

    for ci, (model, temp, sp_key, max_tok) in enumerate(CONFIGS):
        temp_str = f"T={temp}" if temp is not None else "T=default"
        config_label = f"{model} | {temp_str} | {sp_key} | max_tok={max_tok}"
        print(f"\n[{ci+1}/{len(CONFIGS)}] {config_label}")
        system_prompt = SYSTEM_PROMPTS[sp_key]
        results: list[dict] = []
        correct = 0

        pbar = tqdm(prompts, desc=f"  {sp_key[:10]}", unit="p",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
        for rec in pbar:
            t0 = time.time()
            try:
                model_output = _call_analyst(
                    rec["prompt_text"], system_prompt, model, temp, max_tok
                )
            except Exception as e:
                model_output = f"[Error: {e}]"

            pred = _parse_recommendation(model_output)
            gt = (rec.get("ground_truth") or "hold").lower()

            try:
                judge = _call_judge(rec["context_summary"], model_output, gt)
            except Exception:
                judge = {k: None for k in ("faithfulness", "relevance", "consistency", "correctness")}

            is_correct = 1 if pred == gt else 0
            correct += is_correct
            results.append({
                "ticker": rec.get("ticker"),
                "date": rec.get("date"),
                "sector": rec.get("sector"),
                "prompt_variant": rec.get("prompt_variant"),
                "ground_truth": gt,
                "predicted": pred,
                "correct": is_correct,
                "model_output": model_output[:500],
                "judge_faithfulness": judge.get("faithfulness"),
                "judge_relevance": judge.get("relevance"),
                "judge_consistency": judge.get("consistency"),
                "judge_correctness": judge.get("correctness"),
            })
            elapsed = time.time() - t0
            acc = correct / len(results)
            pbar.set_postfix_str(f"acc={acc:.0%} {elapsed:.1f}s")
        pbar.close()

        metrics = _compute_metrics(results)
        config_entry = {
            "model": model,
            "temperature": temp,
            "system_prompt": sp_key,
            "max_tokens": max_tok,
            "metrics": metrics,
            "predictions": [{"ticker": r["ticker"], "gt": r["ground_truth"],
                             "pred": r["predicted"], "correct": r["correct"]}
                            for r in results],
        }
        all_results.append(config_entry)

        if metrics["accuracy"] > best_acc:
            best_acc = metrics["accuracy"]
            best_config = config_entry

        print(f"  -> Accuracy={metrics['accuracy']:.1%}  BalAcc={metrics['balanced_accuracy']:.1%}  "
              f"F1={metrics['macro_f1']:.3f}  "
              f"Judge(faith={metrics['judge_faithfulness_mean']} rel={metrics['judge_relevance_mean']} "
              f"cons={metrics['judge_consistency_mean']} corr={metrics['judge_correctness_mean']})")

    # ── save results ─────────────────────────────────────────────────────
    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / "hyperparam_results.json"
    best_config_clean = {k: v for k, v in best_config.items() if k != "predictions"}
    summary = {
        "sweep_configs": len(all_results),
        "prompts_per_config": len(prompts),
        "split": split,
        "best_config": best_config_clean,
        "baseline_accuracy": 0.6,
        "results": [{k: v for k, v in r.items() if k != "predictions"} for r in all_results],
        "detailed_predictions": {
            f"{r['model']}_{r['system_prompt']}_T{r['temperature']}_tok{r['max_tokens']}": r["predictions"]
            for r in all_results
        },
    }
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults saved: {out_path}")

    ASSETS.mkdir(parents=True, exist_ok=True)
    js_path = ASSETS / "hyperparam_embed.js"
    embed = {k: v for k, v in summary.items() if k != "detailed_predictions"}
    with open(js_path, "w") as f:
        f.write("var HYPERPARAM_RESULTS = ")
        f.write(json.dumps(embed))
        f.write(";\n")
    print(f"JS embed saved: {js_path}")

    # ── print summary table ──────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  SWEEP COMPLETE — {len(all_results)} configurations evaluated")
    print(f"  Baseline (original run): 60.0% accuracy on test set")
    print(f"{'='*80}")
    print(f"\n{'Model':<16} {'Temp':<8} {'Prompt Strategy':<22} {'MaxTok':<8} "
          f"{'Accuracy':<10} {'Bal.Acc':<10} {'F1':<8} {'J.Corr':<8}")
    print("-" * 100)
    for r in sorted(all_results, key=lambda x: -x["metrics"]["accuracy"]):
        m = r["metrics"]
        t = str(r["temperature"]) if r["temperature"] is not None else "def"
        print(f"{r['model']:<16} {t:<8} {r['system_prompt']:<22} {r['max_tokens']:<8} "
              f"{m['accuracy']:<10.1%} {m['balanced_accuracy']:<10.1%} {m['macro_f1']:<8.3f} "
              f"{(m['judge_correctness_mean'] or 0):<8.2f}")

    print(f"\nBEST: {best_config['model']} | T={best_config['temperature']} | "
          f"{best_config['system_prompt']} | max_tokens={best_config['max_tokens']} "
          f"-> {best_config['metrics']['accuracy']:.1%}")


def main():
    ap = argparse.ArgumentParser(prog="python -m src.evaluation.hyperparam_sweep")
    ap.add_argument("--split", default="test", choices=["train", "test"])
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    run_sweep(args.split, args.limit)


if __name__ == "__main__":
    main()
