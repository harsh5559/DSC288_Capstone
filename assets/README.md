# Assets for GitHub Pages

- **demo_embed.js** — Filled by `python scripts/export_demo_data.py` (test-set demo entries for index.html).
- **eval_summary_embed.js** — Filled by `python scripts/run_explainability_eval.py` (train/test metrics for index.html).
- **figures/eval/** — Eval plots (confusion matrix, judge scores, accuracy by sector); copied here by `run_explainability_eval.py`.

Root **index.html** loads these from `assets/` so the site works when published from repo root (e.g. GitHub Pages with source = main branch / root).
