# VeriFact Research Analysis & Output Archive

This directory contains preserved research analysis artifacts from the historical 2×2 study alongside documentation of VeriFact's evaluation export mechanisms.

---

## Directory Overview

- **`output/`**: An immutable historical archive containing tabular CSV files and visualization figures derived from the baseline mock research run (`58baff20-fb86-4f43-b20e-895a086ceb6b`). See [`analysis/output/README.md`](output/README.md) for details.
- **Live Evaluation Exports**: For current benchmarking and evaluation over datasets (such as `pilot.json`), VeriFact uses the standalone evaluations API (`/api/evaluations/*`).

---

## Historical Research Artifacts in `analysis/output/`

The files in [`analysis/output/`](output/) were generated to validate the research pipeline and provide baseline visual comparisons:

### Tabular CSV Data
- **`condition_rows.csv`**: Detailed per-question metrics, answer texts, and hallucination scores across experimental conditions.
- **`condition_summary.csv`**: Aggregated means, standard deviations, confidence intervals, and error rates per condition.
- **`paired_comparisons.csv`**: Within-subject paired score differences between same-model and cross-model verifier conditions.
- **`classification_flips.csv`**: Frequency and direction of classification label changes between conditions.
- **`threshold_sweep.csv`**: Sensitivity analysis sweeping classification thresholds $\theta \in [0.10, 0.90]$.

### Visualization Charts
- **`chart1_condition_means.png`**: Bar chart comparing mean hallucination scores across conditions.
- **`chart2_score_difference.png`**: Distribution plot of paired score differences (same-model minus cross-model).
- **`chart3_flip_rate.png`**: Proportion of questions exhibiting classification outcome flips.
- **`chart4_threshold_sweep.png`**: Precision, Recall, and F1 curves across classification thresholds.

> [!WARNING]
> **Mock Data Notice**: Artifacts in `analysis/output/` were generated under `LLM_MODE=mock` as deterministic software verification fixtures. They represent test pipeline validation data, not empirical findings from live LLMs.

---

## Live Evaluation API & Exporting Results

In the current VeriFact architecture, offline dataset evaluation runs are executed through the live backend API and exported directly as CSV:

### 1. Trigger an Evaluation Run
```bash
curl -X POST http://127.0.0.1:8000/api/evaluations/run \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "pilot",
    "threshold": 0.5,
    "name": "Live Evaluation Run",
    "generator_model": "gemma4:26b",
    "verifier_model": "gemini-3.8-flash"
  }'
```

### 2. Export Evaluation Results to CSV
```bash
# Download CSV containing all evaluated question rows, labels, and scores:
curl -O http://127.0.0.1:8000/api/evaluations/{evaluation_id}/export
```

In the web interface, evaluation records and traces can be inspected and exported directly from the browser.
