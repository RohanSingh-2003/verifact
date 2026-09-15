from pathlib import Path

from app.experiment.charts import (
    plot_classification_flip_rate,
    plot_condition_means,
    plot_self_verification_difference,
    plot_threshold_sweep,
)


def test_charts_are_generated_from_csv(tmp_path: Path) -> None:
    summary = tmp_path / "summary.csv"
    summary.write_text(
        "label,mean_score\nA → A,0.2\nA → B,0.8\nB → A,0.1\nB → B,0.9\n",
        encoding="utf-8",
    )
    paired = tmp_path / "paired.csv"
    paired.write_text(
        "generator_model,difference,classification_flip\n"
        "model-a,-0.6,True\nmodel-a,-0.6,True\nmodel-b,0.8,False\n",
        encoding="utf-8",
    )
    sweep = tmp_path / "sweep.csv"
    sweep.write_text(
        "threshold,precision,recall,f1\n0.3,0.5,0.8,0.62\n0.5,0.6,0.6,0.6\n0.7,0.7,0.4,0.51\n",
        encoding="utf-8",
    )
    plot_condition_means(summary, tmp_path / "c1.png", sample_size=2)
    plot_self_verification_difference(paired, tmp_path / "c2.png")
    plot_classification_flip_rate(paired, tmp_path / "c3.png")
    plot_threshold_sweep(sweep, tmp_path / "c4.png")
    assert (tmp_path / "c1.png").stat().st_size > 0
    assert (tmp_path / "c2.png").stat().st_size > 0
    assert (tmp_path / "c3.png").stat().st_size > 0
    assert (tmp_path / "c4.png").stat().st_size > 0
