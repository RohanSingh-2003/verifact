"""Write experiment artifacts without overwriting previous raw files."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from app.database.models import Experiment

REPO_ROOT = Path(__file__).resolve().parents[3]


def experiment_dirs(experiment_id: str, *, root: Path | None = None) -> dict[str, Path]:
    base = root or (REPO_ROOT / "experiments")
    return {
        "raw": base / "raw" / experiment_id,
        "processed": base / "processed" / experiment_id,
        "results": base / "results" / experiment_id,
    }


def write_experiment_artifacts(experiment: Experiment, *, root: Path | None = None) -> dict[str, str]:
    from app.experiment.charts import (
        plot_category_comparison,
        plot_classification_flip_rate,
        plot_condition_means,
        plot_self_verification_difference,
        plot_threshold_sweep,
    )
    from app.experiment.report import write_results_summary
    from app.services.experiment_service import (
        export_condition_summary_csv,
        export_conditions_csv,
        export_flip_csv,
        export_paired_csv,
        export_research_log_json,
        export_threshold_sweep_csv,
        generation_trace,
    )

    dirs = experiment_dirs(experiment.id, root=root)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    raw = dirs["raw"]
    processed = dirs["processed"]
    results = dirs["results"]

    config_path = raw / "experiment_config.json"
    if not config_path.exists():
        config_path.write_text(export_research_log_json(experiment), encoding="utf-8")
    traces_path = raw / "generation_traces.json"
    if not traces_path.exists():
        traces = [generation_trace(experiment, item.id) for item in experiment.generations]
        traces_path.write_text(json.dumps([item for item in traces if item], indent=2), encoding="utf-8")

    files = {
        "condition_summary.csv": export_condition_summary_csv(experiment),
        "question_level_results.csv": export_conditions_csv(experiment),
        "paired_comparisons.csv": export_paired_csv(experiment),
        "classification_flips.csv": export_flip_csv(experiment),
        "threshold_sweep.csv": export_threshold_sweep_csv(experiment),
    }
    summary = json.loads(experiment.summary_stats_json or "{}")
    category_rows = summary.get("category_analysis") or []
    if category_rows:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(category_rows[0].keys()))
        writer.writeheader()
        writer.writerows(category_rows)
        files["category_analysis.csv"] = buffer.getvalue()

    written: dict[str, str] = {"raw_config": str(config_path)}
    exclusions = summary.get("exclusions") or []
    (processed / "exclusions.json").write_text(json.dumps(exclusions, indent=2), encoding="utf-8")
    written["exclusions.json"] = str(processed / "exclusions.json")
    for name, body in files.items():
        dest = processed / name
        dest.write_text(body, encoding="utf-8")
        written[name] = str(dest)
    (processed / "experiment_config.json").write_text(export_research_log_json(experiment), encoding="utf-8")
    (results / "experiment_config.json").write_text(export_research_log_json(experiment), encoding="utf-8")
    written["experiment_config.json"] = str(processed / "experiment_config.json")

    summary_csv = processed / "condition_summary.csv"
    paired_csv = processed / "paired_comparisons.csv"
    sweep_csv = processed / "threshold_sweep.csv"
    if summary_csv.exists() and summary_csv.read_text(encoding="utf-8").count("\n") > 1:
        plot_condition_means(summary_csv, results / "chart1_condition_means.png")
        written["chart1"] = str(results / "chart1_condition_means.png")
    if paired_csv.exists() and paired_csv.read_text(encoding="utf-8").count("\n") > 1:
        plot_self_verification_difference(paired_csv, results / "chart2_score_difference.png")
        plot_classification_flip_rate(paired_csv, results / "chart3_flip_rate.png")
        written["chart2"] = str(results / "chart2_score_difference.png")
        written["chart3"] = str(results / "chart3_flip_rate.png")
    if sweep_csv.exists() and sweep_csv.read_text(encoding="utf-8").count("\n") > 1:
        plot_threshold_sweep(sweep_csv, results / "chart4_threshold_sweep.png")
        written["chart4"] = str(results / "chart4_threshold_sweep.png")
    category_csv = processed / "category_analysis.csv"
    if category_csv.exists() and category_csv.read_text(encoding="utf-8").count("\n") > 1:
        plot_category_comparison(category_csv, results / "chart5_category.png")
        written["chart5"] = str(results / "chart5_category.png")
    summary_md = write_results_summary(experiment, results / "results_summary.md")
    written["results_summary"] = str(summary_md)
    return written
