"""Generate side-by-side comparison plots: Baseline vs HP-Tuned (CoT+300)."""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "reports"
FIGURES = REPO / "assets" / "figures" / "eval"
FIGURES.mkdir(parents=True, exist_ok=True)

hp = json.loads((REPORTS / "hyperparam_results.json").read_text())

baseline_metrics = None
tuned_metrics = None
for r in hp["results"]:
    if r["system_prompt"] == "baseline" and r["max_tokens"] == 500 and r["model"] == "gpt-5.2-chat":
        baseline_metrics = r["metrics"]
    if r["system_prompt"] == "chain_of_thought" and r["max_tokens"] == 300 and r["model"] == "gpt-5.2-chat":
        tuned_metrics = r["metrics"]

detailed = hp.get("detailed_predictions", {})
baseline_preds = detailed.get("gpt-5.2-chat_baseline_TNone_tok500", [])
tuned_preds = detailed.get("gpt-5.2-chat_chain_of_thought_TNone_tok300", [])

CLASSES = ["buy", "hold", "sell"]
colors_baseline = "#6366f1"
colors_tuned = "#22c55e"

# ── 1. Classification Metrics Bar Chart ──────────────────────────────────

fig, ax = plt.subplots(figsize=(10, 5))
metrics_names = ["Accuracy", "Balanced\nAccuracy", "Macro F1"]
baseline_vals = [baseline_metrics["accuracy"], baseline_metrics["balanced_accuracy"], baseline_metrics["macro_f1"]]
tuned_vals = [tuned_metrics["accuracy"], tuned_metrics["balanced_accuracy"], tuned_metrics["macro_f1"]]

x = np.arange(len(metrics_names))
w = 0.32
bars1 = ax.bar(x - w/2, baseline_vals, w, label="Baseline (500 tok)", color=colors_baseline, edgecolor="white", linewidth=0.5)
bars2 = ax.bar(x + w/2, tuned_vals, w, label="CoT + 300 tok (Tuned)", color=colors_tuned, edgecolor="white", linewidth=0.5)

for bar, val in zip(bars1, baseline_vals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f"{val:.1%}", ha="center", va="bottom", fontweight="bold", fontsize=11, color=colors_baseline)
for bar, val in zip(bars2, tuned_vals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f"{val:.1%}", ha="center", va="bottom", fontweight="bold", fontsize=11, color=colors_tuned)

ax.set_ylabel("Score", fontsize=12)
ax.set_title("Classification Metrics: Baseline vs. HP-Tuned", fontsize=14, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(metrics_names, fontsize=12)
ax.set_ylim(0, 1.0)
ax.legend(fontsize=11, loc="upper left")
ax.grid(axis="y", alpha=0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig(FIGURES / "hp_classification_comparison.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved hp_classification_comparison.png")

# ── 2. Judge Scores Comparison ───────────────────────────────────────────

fig, ax = plt.subplots(figsize=(10, 5))
judge_names = ["Faithfulness", "Relevance", "Consistency", "Correctness"]
judge_baseline = [
    baseline_metrics["judge_faithfulness_mean"],
    baseline_metrics["judge_relevance_mean"],
    baseline_metrics["judge_consistency_mean"],
    baseline_metrics["judge_correctness_mean"],
]
judge_tuned = [
    tuned_metrics["judge_faithfulness_mean"],
    tuned_metrics["judge_relevance_mean"],
    tuned_metrics["judge_consistency_mean"],
    tuned_metrics["judge_correctness_mean"],
]

x = np.arange(len(judge_names))
bars1 = ax.bar(x - w/2, judge_baseline, w, label="Baseline", color=colors_baseline, edgecolor="white", linewidth=0.5)
bars2 = ax.bar(x + w/2, judge_tuned, w, label="CoT + 300 tok (Tuned)", color=colors_tuned, edgecolor="white", linewidth=0.5)

for bar, val in zip(bars1, judge_baseline):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.08, f"{val:.1f}", ha="center", va="bottom", fontweight="bold", fontsize=11, color=colors_baseline)
for bar, val in zip(bars2, judge_tuned):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.08, f"{val:.1f}", ha="center", va="bottom", fontweight="bold", fontsize=11, color=colors_tuned)

ax.set_ylabel("Score (1–5)", fontsize=12)
ax.set_title("LLM-as-Judge Scores: Baseline vs. HP-Tuned", fontsize=14, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(judge_names, fontsize=12)
ax.set_ylim(0, 5.8)
ax.axhline(y=5, color="#94a3b8", linestyle="--", alpha=0.4, linewidth=1)
ax.legend(fontsize=11, loc="upper right")
ax.grid(axis="y", alpha=0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig(FIGURES / "hp_judge_comparison.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved hp_judge_comparison.png")

# ── 3. Confusion Matrix Side-by-Side ─────────────────────────────────────

def build_cm(preds):
    cm = np.zeros((3, 3), dtype=int)
    for p in preds:
        gt_idx = CLASSES.index(p["gt"]) if p["gt"] in CLASSES else 1
        pr_idx = CLASSES.index(p["pred"]) if p["pred"] in CLASSES else 1
        cm[gt_idx][pr_idx] += 1
    return cm

if baseline_preds and tuned_preds:
    cm_base = build_cm(baseline_preds)
    cm_tune = build_cm(tuned_preds)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    for ax, cm, title, cmap in [(ax1, cm_base, "Baseline (60% acc)", "Purples"),
                                 (ax2, cm_tune, "HP-Tuned CoT+300 (70% acc)", "Greens")]:
        im = ax.imshow(cm, cmap=cmap, vmin=0, vmax=max(cm.max(), 1))
        ax.set_xticks(range(3)); ax.set_yticks(range(3))
        ax.set_xticklabels(["BUY", "HOLD", "SELL"], fontsize=11)
        ax.set_yticklabels(["BUY", "HOLD", "SELL"], fontsize=11)
        ax.set_xlabel("Predicted", fontsize=12)
        ax.set_ylabel("True", fontsize=12)
        ax.set_title(title, fontsize=13, fontweight="bold")
        for i in range(3):
            for j in range(3):
                val = cm[i][j]
                color = "white" if val > cm.max() * 0.5 else "black"
                ax.text(j, i, str(val), ha="center", va="center", fontsize=16, fontweight="bold", color=color)
    plt.suptitle("Confusion Matrix: Baseline vs. HP-Tuned", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(FIGURES / "hp_confusion_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved hp_confusion_comparison.png")
else:
    print("No detailed predictions found — skipping confusion matrix")

# ── 4. Accuracy by Prompt Strategy × Max Tokens Heatmap ──────────────────

strategies = ["baseline", "chain_of_thought", "structured_analysis"]
tokens = [300, 500, 800]
heatmap = np.zeros((len(strategies), len(tokens)))

for r in hp["results"]:
    if r["model"] != "gpt-5.2-chat":
        continue
    if r["system_prompt"] in strategies and r["max_tokens"] in tokens:
        si = strategies.index(r["system_prompt"])
        ti = tokens.index(r["max_tokens"])
        heatmap[si][ti] = r["metrics"]["accuracy"]

fig, ax = plt.subplots(figsize=(8, 4))
im = ax.imshow(heatmap, cmap="RdYlGn", vmin=0.4, vmax=0.75, aspect="auto")
ax.set_xticks(range(len(tokens)))
ax.set_xticklabels([f"{t} tokens" for t in tokens], fontsize=12)
ax.set_yticks(range(len(strategies)))
ax.set_yticklabels(["Baseline", "Chain-of-Thought", "Structured Analysis"], fontsize=12)
ax.set_xlabel("Max Output Tokens", fontsize=12)
ax.set_title("Accuracy Heatmap: Prompt Strategy × Token Budget (GPT-5.2-chat)", fontsize=13, fontweight="bold")
for i in range(len(strategies)):
    for j in range(len(tokens)):
        val = heatmap[i][j]
        color = "white" if val < 0.55 else "black"
        ax.text(j, i, f"{val:.0%}", ha="center", va="center", fontsize=16, fontweight="bold", color=color)
plt.colorbar(im, ax=ax, label="Accuracy", shrink=0.8)
plt.tight_layout()
plt.savefig(FIGURES / "hp_accuracy_heatmap.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved hp_accuracy_heatmap.png")

# ── 5. Model Comparison Bar Chart ────────────────────────────────────────

model_data = {}
for r in hp["results"]:
    key = r["model"]
    if key not in model_data:
        model_data[key] = []
    model_data[key].append(r["metrics"]["accuracy"])

fig, ax = plt.subplots(figsize=(8, 4))
models = list(model_data.keys())
avg_accs = [np.mean(model_data[m]) for m in models]
max_accs = [np.max(model_data[m]) for m in models]
colors = ["#22c55e" if m == "gpt-5.2-chat" else "#94a3b8" for m in models]

x = np.arange(len(models))
bars_avg = ax.bar(x - 0.15, avg_accs, 0.3, label="Avg Accuracy", color=colors, alpha=0.6, edgecolor="white")
bars_max = ax.bar(x + 0.15, max_accs, 0.3, label="Best Accuracy", color=colors, edgecolor="white")

for bar, val in zip(bars_avg, avg_accs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, f"{val:.0%}", ha="center", va="bottom", fontsize=11, fontweight="bold")
for bar, val in zip(bars_max, max_accs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, f"{val:.0%}", ha="center", va="bottom", fontsize=11, fontweight="bold")

ax.set_ylabel("Accuracy", fontsize=12)
ax.set_title("Model Comparison: Average vs. Best Accuracy", fontsize=13, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(models, fontsize=11)
ax.set_ylim(0, 0.85)
ax.legend(fontsize=11)
ax.grid(axis="y", alpha=0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig(FIGURES / "hp_model_comparison.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved hp_model_comparison.png")

print("\nAll comparison plots generated!")
