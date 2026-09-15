"""Write paper-ready CSVs, config JSON, and matplotlib charts from a saved experiment.

Usage:
  python -m scripts.build_research_artifacts --experiment-id <id> [--evaluation-id <id>] --out analysis/output

Does not hardcode findings. Charts are generated from exported CSV files.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database.db import SessionLocal, init_db
from app.experiment.charts import (
    plot_classification_flip_rate,
    plot_condition_means,
    plot_self_verification_difference,
    plot_threshold_sweep,
)
from app.services.evaluation_service import export_threshold_sweep_csv as export_eval_sweep
from app.services.evaluation_service import get_evaluation
from app.services.experiment_service import (
    export_condition_summary_csv,
    export_conditions_csv,
    export_flip_csv,
    export_paired_csv,
    export_research_log_json,
    export_threshold_sweep_csv,
    get_experiment,
    get_latest_experiment,
)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export VeriFact research artifacts.")
    parser.add_argument("--experiment-id", default="")
    parser.add_argument("--evaluation-id", default="")
    parser.add_argument("--out", default="analysis/output")
    args = parser.parse_args()

    init_db()
    out = Path(args.out)
    db = SessionLocal()
    try:
        experiment = get_experiment(db, args.experiment_id) if args.experiment_id else get_latest_experiment(db)
        if experiment is None:
            raise SystemExit("No experiment found. Run POST /api/experiments/run first.")
        _write(out / "condition_rows.csv", export_conditions_csv(experiment))
        _write(out / "condition_summary.csv", export_condition_summary_csv(experiment))
        _write(out / "paired_comparisons.csv", export_paired_csv(experiment))
        _write(out / "classification_flips.csv", export_flip_csv(experiment))
        _write(out / "threshold_sweep.csv", export_threshold_sweep_csv(experiment))
        _write(out / "experiment_config.json", export_research_log_json(experiment))

        plot_condition_means(out / "condition_summary.csv", out / "chart1_condition_means.png")
        plot_self_verification_difference(out / "paired_comparisons.csv", out / "chart2_score_difference.png")
        plot_classification_flip_rate(out / "paired_comparisons.csv", out / "chart3_flip_rate.png")

        sweep_path = out / "threshold_sweep.csv"
        if args.evaluation_id:
            evaluation = get_evaluation(db, args.evaluation_id)
            if evaluation is None:
                raise SystemExit("Evaluation not found.")
            _write(out / "evaluation_threshold_sweep.csv", export_eval_sweep(evaluation))
            sweep_path = out / "evaluation_threshold_sweep.csv"
        if sweep_path.exists() and sweep_path.read_text(encoding="utf-8").count("\n") > 1:
            plot_threshold_sweep(sweep_path, out / "chart4_threshold_sweep.png")
        print(f"Wrote artifacts to {out.resolve()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
