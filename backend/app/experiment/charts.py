"""Publication-style matplotlib charts from exported VeriFact CSVs.

Charts read CSV files. They do not hardcode experimental findings.
"""

from __future__ import annotations

import csv
from pathlib import Path


def _require_pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to generate research charts.") from exc
    return plt


def _style(plt) -> None:
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
        }
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def plot_condition_means(summary_csv: Path, output: Path, *, sample_size: int | None = None) -> None:
    rows = _read_csv(summary_csv)
    if not rows:
        raise ValueError("Condition summary CSV is empty.")
    plt = _require_pyplot()
    _style(plt)
    labels = [row["label"] for row in rows]
    means = [float(row["mean_score"]) for row in rows]
    figure, axes = plt.subplots(figsize=(6.5, 4.0))
    axes.bar(labels, means, color="#4a4a4a")
    axes.set_ylim(0, 1)
    axes.set_ylabel("Mean hallucination score")
    title = "Mean hallucination score by generator / verifier"
    if sample_size is not None:
        title += f" (n={sample_size})"
    axes.set_title(title)
    axes.set_xlabel("Condition")
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=200)
    plt.close(figure)


def plot_self_verification_difference(paired_csv: Path, output: Path) -> None:
    rows = _read_csv(paired_csv)
    if not rows:
        raise ValueError("Paired comparison CSV is empty.")
    plt = _require_pyplot()
    _style(plt)
    by_gen: dict[str, list[float]] = {}
    for row in rows:
        by_gen.setdefault(row["generator_model"], []).append(float(row["difference"]))
    labels = list(by_gen)
    values = [sum(items) / len(items) for items in by_gen.values()]
    sizes = [len(items) for items in by_gen.values()]
    figure, axes = plt.subplots(figsize=(6.0, 4.0))
    axes.axhline(0, color="#888888", linewidth=1)
    axes.bar(labels, values, color="#4a4a4a")
    axes.set_ylabel("Same-model − cross-model mean score")
    axes.set_title("Self-verification score difference")
    axes.set_xlabel("Generator")
    for index, (value, n) in enumerate(zip(values, sizes, strict=True)):
        axes.text(index, value, f" n={n}", ha="center", va="bottom" if value >= 0 else "top", fontsize=9)
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=200)
    plt.close(figure)


def plot_classification_flip_rate(paired_csv: Path, output: Path) -> None:
    rows = _read_csv(paired_csv)
    if not rows:
        raise ValueError("Paired comparison CSV is empty.")
    plt = _require_pyplot()
    _style(plt)
    by_gen: dict[str, list[bool]] = {}
    for row in rows:
        flag = str(row["classification_flip"]).strip().lower() in {"true", "1", "yes"}
        by_gen.setdefault(row["generator_model"], []).append(flag)
    labels = list(by_gen)
    rates = [sum(items) / len(items) for items in by_gen.values()]
    sizes = [len(items) for items in by_gen.values()]
    figure, axes = plt.subplots(figsize=(6.0, 4.0))
    axes.bar(labels, rates, color="#4a4a4a")
    axes.set_ylim(0, 1)
    axes.set_ylabel("Classification flip rate")
    axes.set_title("Same-model vs cross-model classification flips")
    axes.set_xlabel("Generator")
    for index, n in enumerate(sizes):
        axes.text(index, rates[index], f" n={n}", ha="center", va="bottom", fontsize=9)
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=200)
    plt.close(figure)


def plot_threshold_sweep(sweep_csv: Path, output: Path) -> None:
    rows = _read_csv(sweep_csv)
    if not rows:
        raise ValueError("Threshold sweep CSV is empty.")
    plt = _require_pyplot()
    _style(plt)
    if "generator_model" in rows[0]:
        first_gen = rows[0]["generator_model"]
        first_ver = rows[0]["verifier_model"]
        rows = [row for row in rows if row["generator_model"] == first_gen and row["verifier_model"] == first_ver]
    thresholds = [float(row["threshold"]) for row in rows]
    precision = [float(row["precision"]) for row in rows]
    recall = [float(row["recall"]) for row in rows]
    f1 = [float(row["f1"]) for row in rows]
    figure, axes = plt.subplots(figsize=(6.5, 4.0))
    axes.plot(thresholds, precision, marker="o", label="Precision")
    axes.plot(thresholds, recall, marker="o", label="Recall")
    axes.plot(thresholds, f1, marker="o", label="F1")
    axes.set_ylim(0, 1)
    axes.set_xlabel("Threshold")
    axes.set_ylabel("Metric")
    axes.set_title("Threshold vs precision / recall / F1")
    axes.legend(frameon=False)
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=200)
    plt.close(figure)


def plot_category_comparison(category_csv: Path, output: Path) -> None:
    rows = _read_csv(category_csv)
    if not rows:
        raise ValueError("Category analysis CSV is empty.")
    plt = _require_pyplot()
    _style(plt)
    labels = [f"{row['category']}\n{row['generator_model']}" for row in rows]
    values = [float(row["score_difference"]) for row in rows]
    figure, axes = plt.subplots(figsize=(7.5, 4.2))
    axes.axhline(0, color="#888888", linewidth=1)
    axes.bar(labels, values, color="#4a4a4a")
    axes.set_ylabel("Same-model − cross-model mean score")
    axes.set_title("Category comparison (secondary analysis)")
    axes.tick_params(axis="x", labelrotation=30)
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=200)
    plt.close(figure)
