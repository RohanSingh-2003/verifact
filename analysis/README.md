# VeriFact Research Analysis & Artifact Generation

This directory contains research analysis utilities and output artifacts generated from completed experiment and benchmark runs.

---

## Artifact Generation Script

The script `backend/scripts/build_research_artifacts.py` processes raw database evaluation traces into structured CSV tables and visualization charts.

### Usage Instructions

Open a terminal and navigate to the `backend` directory:

```bash
cd backend

# On Windows PowerShell:
.\.venv\Scripts\python.exe scripts\build_research_artifacts.py --out ..\analysis\output

# On macOS / Linux:
# python scripts/build_research_artifacts.py --out ../analysis/output
```

---

## Generated Artifacts in `analysis/output/`

Running the artifact generation script populates `analysis/output/` with the following files:

### 1. Tabular CSV Data
- **`condition_rows.csv`**: Detailed per-question metrics, answer texts, and hallucination scores across all experimental conditions.
- **`condition_summary.csv`**: Aggregated means, standard deviations, confidence intervals, and error rates per condition.
- **`paired_comparisons.csv`**: Within-subject paired score differences between same-model and cross-model verifier conditions.
- **`classification_flips.csv`**: Frequency and direction of classification label changes between conditions.
- **`threshold_sweep.csv`**: Sensitivity analysis sweeping classification thresholds $\theta \in [0.10, 0.90]$.

### 2. Visualization Charts
- **`chart1_condition_means.png`**: Bar chart comparing mean hallucination scores across experimental conditions.
- **`chart2_score_difference.png`**: Distribution plot of paired score differences (same-model minus cross-model).
- **`chart3_flip_rate.png`**: Proportion of questions exhibiting classification outcome flips.
- **`chart4_threshold_sweep.png`**: Precision, Recall, and F1 curves across classification thresholds.

---

## Important Research Notice

- **Demo / Mock Data Notice**: Output artifacts derived while running under `LLM_MODE=mock` are deterministic software demonstration fixtures designed to test the chart generation and reporting pipelines. They must **never** be cited as live LLM findings.
- **Reproducibility**: All charts and CSV summaries are derived programmatically from the stored database records without manual adjustments or hardcoded values.
