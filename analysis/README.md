# VeriFact Research Analysis & Artifact Generation

This directory contains research analysis utilities and output artifacts derived from completed experiment and benchmark runs.

---

## Artifact Generation Script

To generate condition CSV tables, configuration metadata, and comparison charts from a completed experiment:

```bash
cd backend

# On Windows PowerShell:
.\.venv\Scripts\python.exe scripts\build_research_artifacts.py --out ..\analysis\output

# On macOS/Linux:
# python scripts/build_research_artifacts.py --out ../analysis/output
```

---

## Generated Artifacts

The generation script processes raw database runs into structured output files in `analysis/output/`:

### Tabular CSV Data
- `condition_rows.csv`: Detailed per-question metrics across all experimental conditions.
- `condition_summary.csv`: Aggregated means, standard deviations, and error rates per condition.
- `paired_comparisons.csv`: Within-subject paired score differences between same-model and cross-model verifiers.
- `classification_flips.csv`: Frequency and direction of classification label changes between conditions.
- `threshold_sweep.csv`: Sensitivity analysis sweeping classification thresholds $\theta \in [0.1, 0.9]$.

### Visualizations
- `chart1_condition_means.png`: Mean hallucination scores across experimental conditions.
- `chart2_score_difference.png`: Distribution of paired score differences.
- `chart3_flip_rate.png`: Proportion of questions with classification outcome changes.
- `chart4_threshold_sweep.png`: Precision, recall, and F1 curves across threshold ranges.

---

## Important Research Notice

- **Demo / Mock Data**: Outputs generated from `LLM_MODE=mock` are deterministic software demonstration fixtures and must **never** be cited as live LLM findings.
- **Reproducibility**: Charts are derived programmatically from the exported CSV data without manual adjustment or hardcoded values.
