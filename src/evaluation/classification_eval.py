"""
Classification evaluation: Macro F1, per-class precision/recall, confusion matrix.

Loads val or test split from data/processed/{split}_final.parquet.
Uses a baseline predictor (always-hold or optional rule-based) when no model is provided,
so the MCP tool can display real metrics.

Usage:
  from src.evaluation.classification_eval import run_classification_eval, format_metrics_report
  result = run_classification_eval("test")
  print(format_metrics_report(result))
"""

import json
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

try:
    from sklearn.metrics import (
        f1_score,
        precision_score,
        recall_score,
        confusion_matrix,
        classification_report,
        accuracy_score,
        balanced_accuracy_score,
    )
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
TARGET_COL = "target"
CLASSES = ["buy", "hold", "sell"]


def _load_split(split: str) -> pd.DataFrame:
    """Load validation or test parquet. Raises FileNotFoundError if missing."""
    name = "val_final.parquet" if split == "validation" else "test_final.parquet"
    path = PROCESSED_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Split file not found: {path}. Run the pipeline first: python scripts/run_pipeline.py"
        )
    df = pd.read_parquet(path)
    if TARGET_COL not in df.columns:
        raise ValueError(f"Dataset missing column '{TARGET_COL}'")
    return df


def baseline_predict_hold(df: pd.DataFrame) -> np.ndarray:
    """Always predict 'hold'. Returns array of shape (n,) with 'hold'."""
    return np.array(["hold"] * len(df))


def baseline_predict_majority(df: pd.DataFrame) -> np.ndarray:
    """Predict the majority class (hold) for all. Same as hold baseline for our data."""
    majority = df[TARGET_COL].mode().iloc[0]
    return np.array([majority] * len(df))


def run_classification_eval(
    split: str,
    y_pred: Optional[np.ndarray] = None,
    use_baseline: str = "hold",
) -> dict:
    """
    Run classification evaluation on the given split.

    Args:
        split: "validation" or "test"
        y_pred: Optional array of predictions (same order as df). If None, uses baseline.
        use_baseline: "hold" (always predict hold) or "majority"

    Returns:
        Dict with keys: split, n_samples, macro_f1, per_class (precision, recall, f1),
        confusion_matrix (list of lists), baseline_used, classification_report_str.
    """
    if not HAS_SKLEARN:
        return {
            "error": "sklearn not installed",
            "split": split,
        }

    df = _load_split(split)
    y_true = df[TARGET_COL].astype(str).str.lower().values
    # Normalize to our classes
    y_true = np.where(np.isin(y_true, CLASSES), y_true, "hold")

    if y_pred is not None:
        y_pred = np.asarray(y_pred).flatten()
        if len(y_pred) != len(y_true):
            raise ValueError(f"y_pred length {len(y_pred)} != y_true {len(y_true)}")
        baseline_used = None
    else:
        if use_baseline == "majority":
            y_pred = baseline_predict_majority(df)
        else:
            y_pred = baseline_predict_hold(df)
        baseline_used = use_baseline

    # Ensure both use same labels
    labels = CLASSES
    y_true = np.where(np.isin(y_true, labels), y_true, "hold")
    y_pred = np.where(np.isin(y_pred, labels), y_pred, "hold")

    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    accuracy = float(accuracy_score(y_true, y_pred))
    balanced_accuracy = float(balanced_accuracy_score(y_true, y_pred))
    precision_per = precision_score(
        y_true, y_pred, average=None, labels=labels, zero_division=0
    )
    recall_per = recall_score(
        y_true, y_pred, average=None, labels=labels, zero_division=0
    )
    f1_per = f1_score(y_true, y_pred, average=None, labels=labels, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    report_str = classification_report(
        y_true, y_pred, labels=labels, zero_division=0
    )

    per_class = {
        label: {
            "precision": float(precision_per[i]),
            "recall": float(recall_per[i]),
            "f1": float(f1_per[i]),
        }
        for i, label in enumerate(labels)
    }

    return {
        "split": split,
        "n_samples": int(len(y_true)),
        "accuracy": round(accuracy, 4),
        "balanced_accuracy": round(balanced_accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": labels,
        "baseline_used": baseline_used,
        "classification_report": report_str,
    }


def format_metrics_report(result: dict) -> str:
    """Format evaluation result as a clear text report for display (e.g. in MCP)."""
    if result.get("error"):
        return f"Error: {result['error']}"

    lines = [
        "=" * 60,
        "CLASSIFICATION EVALUATION",
        f"Split: {result['split']}  |  N = {result['n_samples']:,}",
        "=" * 60,
        "",
        f"  Accuracy:           {result.get('accuracy', 0):.4f}",
        f"  Balanced accuracy:  {result.get('balanced_accuracy', 0):.4f}",
        f"  Macro F1 (primary): {result['macro_f1']:.4f}",
        "",
        "  Per-class metrics:",
    ]
    for label in result.get("confusion_matrix_labels", ["buy", "hold", "sell"]):
        pc = result.get("per_class", {}).get(label, {})
        lines.append(
            f"    {label.upper():5s}  P: {pc.get('precision', 0):.4f}  R: {pc.get('recall', 0):.4f}  F1: {pc.get('f1', 0):.4f}"
        )
    if result.get("baseline_used"):
        lines.append(f"\n  Baseline predictor: always '{result['baseline_used']}' (no trained model).")
    lines.append("")
    lines.append("  Confusion matrix (rows=true, cols=predicted):")
    labels = result.get("confusion_matrix_labels", [])
    cm = result.get("confusion_matrix", [])
    if labels and cm:
        header = "              " + "  ".join(f"{l:>6s}" for l in labels)
        lines.append(header)
        for i, row in enumerate(cm):
            lines.append(f"    {labels[i]:6s}    " + "  ".join(f"{v:>6d}" for v in row))
    lines.append("")
    lines.append("  Classification report (sklearn):")
    lines.append(result.get("classification_report", "").strip())
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
