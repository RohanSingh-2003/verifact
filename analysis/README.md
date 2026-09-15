"""
Research artifacts for VeriFact.

Generate CSVs, experiment config JSON, and publication charts from a completed
experiment (and optionally an evaluation run):

    cd backend
    .venv\\Scripts\\python.exe scripts\\build_research_artifacts.py --out ..\\analysis\\output

Charts are produced from the exported CSV files. They do not hardcode findings.
Mock-mode outputs are DEMO / MOCK DATA and must not be treated as paper results.

Files written:

- condition_rows.csv
- condition_summary.csv
- paired_comparisons.csv
- classification_flips.csv
- threshold_sweep.csv
- experiment_config.json
- chart1_condition_means.png
- chart2_score_difference.png
- chart3_flip_rate.png
- chart4_threshold_sweep.png (from experiment sweep or evaluation sweep)
"""
