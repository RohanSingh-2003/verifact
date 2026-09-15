"""Generate academic diagrams and DEMO-labeled result figures from saved CSVs.

Does not call LLMs or rerun experiments.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

ROOT = Path(__file__).resolve().parents[2]
EXP_ID = "58baff20-fb86-4f43-b20e-895a086ceb6b"
PROCESSED = ROOT / "experiments" / "processed" / EXP_ID
DOCS = ROOT / "docs"
FIGURES = DOCS / "figures"

NAVY = "#1f3654"
SLATE = "#4a5568"
TEAL = "#2b6e6e"
GOLD = "#8a6d3b"
LIGHT = "#f4f1ea"
BOX = "#ffffff"
EDGE = "#2c3e50"
DEMO = "DEMO / MOCK DATA"


def _box(ax, x, y, w, h, text, *, fc=BOX, ec=EDGE, fs=8.5, lw=1.2, color="#1a1a1a"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.03",
        linewidth=lw,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fs,
        color=color,
        wrap=True,
        linespacing=1.25,
    )
    return patch


def _arrow(ax, x1, y1, x2, y2, *, color=EDGE):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=1.1,
            color=color,
            shrinkA=0,
            shrinkB=0,
        )
    )


def architecture_png(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 8.2), dpi=180)
    ax.set_xlim(0, 13.5)
    ax.set_ylim(0, 8.2)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(6.75, 7.85, "VeriFact System Architecture", ha="center", va="center", fontsize=16, color=NAVY, fontweight="bold")
    ax.text(6.75, 7.48, "User detection, 2×2 experiment, and post-detection evaluation", ha="center", va="center", fontsize=9, color=SLATE)

    ax.add_patch(Rectangle((0.25, 0.35), 4.15, 6.85, linewidth=1.3, edgecolor=TEAL, facecolor="#eef6f6"))
    ax.text(2.32, 6.95, "CORE DETECTOR", ha="center", fontsize=11, color=TEAL, fontweight="bold")
    ax.text(2.32, 6.62, "Zero-resource  ·  no external evidence retrieval", ha="center", fontsize=7.5, color=TEAL)

    _box(ax, 0.55, 5.85, 3.55, 0.55, "React UI  (Vite + TypeScript + Tailwind)")
    _box(ax, 0.55, 5.05, 3.55, 0.55, "FastAPI")
    _box(ax, 0.55, 4.25, 3.55, 0.55, "Answer generator")
    _box(ax, 0.55, 3.45, 3.55, 0.55, "Mutation generator")
    _box(ax, 0.55, 2.65, 3.55, 0.55, "Verifier  (YES / NO / NOT SURE)")
    _box(ax, 0.55, 1.85, 3.55, 0.55, "MetaQA score engine")
    _box(ax, 0.55, 1.05, 3.55, 0.55, "Threshold classifier")
    _box(ax, 0.55, 0.50, 3.55, 0.40, "SQLite run store", fs=8)

    for y1, y2 in [(5.85, 5.60), (5.05, 4.80), (4.25, 4.00), (3.45, 3.20), (2.65, 2.40), (1.85, 1.60), (1.05, 0.90)]:
        _arrow(ax, 2.32, y1, 2.32, y2)

    ax.add_patch(Rectangle((4.65, 0.35), 4.25, 6.85, linewidth=1.3, edgecolor=NAVY, facecolor="#eef2f7"))
    ax.text(6.77, 6.95, "EXPERIMENT PIPELINE", ha="center", fontsize=11, color=NAVY, fontweight="bold")
    ax.text(6.77, 6.62, "Fixed mutation sets  ·  verifier identity only", ha="center", fontsize=7.5, color=NAVY)

    _box(ax, 4.95, 5.85, 3.65, 0.55, "Pilot dataset  (questions only)")
    _box(ax, 4.95, 5.05, 3.65, 0.55, "Generator A / Generator B")
    _box(ax, 4.95, 4.25, 3.65, 0.55, "Fixed mutation set (once per answer)")
    _box(ax, 4.95, 3.25, 1.65, 0.75, "Verifier A\nA→A   B→A", fs=8)
    _box(ax, 6.85, 3.25, 1.75, 0.75, "Verifier B\nA→B   B→B", fs=8)
    _box(ax, 4.95, 2.25, 3.65, 0.70, "Metrics  ·  paired differences\nWilcoxon  ·  flip rates")
    _box(ax, 4.95, 1.25, 3.65, 0.70, "Charts  ·  research artifacts")
    _box(ax, 4.95, 0.50, 3.65, 0.50, "experiments/results/<id>/", fs=8)

    _arrow(ax, 6.77, 5.85, 6.77, 5.60)
    _arrow(ax, 6.77, 5.05, 6.77, 4.80)
    _arrow(ax, 5.77, 4.25, 5.77, 4.00)
    _arrow(ax, 7.72, 4.25, 7.72, 4.00)
    _arrow(ax, 6.77, 3.25, 6.77, 2.95)
    _arrow(ax, 6.77, 2.25, 6.77, 1.95)
    _arrow(ax, 6.77, 1.25, 6.77, 1.00)

    ax.add_patch(Rectangle((9.15, 0.35), 4.10, 6.85, linewidth=1.3, edgecolor=GOLD, facecolor="#f7f3ea"))
    ax.text(11.20, 6.95, "EVALUATION LAYER", ha="center", fontsize=11, color=GOLD, fontweight="bold")
    ax.text(11.20, 6.62, "Ground truth used only after detection", ha="center", fontsize=7.5, color=GOLD)

    _box(ax, 9.45, 5.55, 3.50, 0.80, "Reference answers / labels\n(not sent to MetaQA prompts)", fs=8)
    _box(ax, 9.45, 4.45, 3.50, 0.80, "Answer correctness labeling\nReliable / Hallucinated / Needs Review")
    _box(ax, 9.45, 3.35, 3.50, 0.80, "Accuracy, precision, recall, F1\nSpecificity, FPR, FNR")
    _box(ax, 9.45, 2.25, 3.50, 0.80, "Confusion matrix\nThreshold sweep on stored scores")
    _box(ax, 9.45, 0.70, 3.50, 1.20, "Boundary\nDetection never queries Google,\nWikipedia, RAG, embeddings,\nor external fact-checking APIs.", fs=8)

    _arrow(ax, 11.20, 5.55, 11.20, 5.25)
    _arrow(ax, 11.20, 4.45, 11.20, 4.15)
    _arrow(ax, 11.20, 3.35, 11.20, 3.05)

    ax.text(
        6.75,
        0.12,
        "LLM clients: generator + verifier abstractions. SQLite stores traces. Evaluation is a separate post-detection layer.",
        ha="center",
        fontsize=7.5,
        color=SLATE,
    )
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def research_flow_png(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 9.0), dpi=180)
    ax.set_xlim(0, 12.5)
    ax.set_ylim(0, 9.0)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(6.25, 8.65, "VeriFact Research Flow", ha="center", fontsize=16, color=NAVY, fontweight="bold")
    ax.text(6.25, 8.28, "Fixed-input 2×2 same-model vs cross-model verification", ha="center", fontsize=9, color=SLATE)

    _box(ax, 4.35, 7.50, 3.80, 0.52, "Question")
    _box(ax, 4.35, 6.70, 3.80, 0.52, "Generator  (A or B, once)")
    _box(ax, 4.35, 5.90, 3.80, 0.52, "Base answer  (stored)")
    _box(ax, 4.35, 5.10, 3.80, 0.52, "Mutation generator  (once)")
    _box(ax, 3.55, 4.15, 5.40, 0.65, "Fixed mutation set\n5 synonym + 5 antonym  ·  reused across verifiers", fs=8)

    for y1, y2 in [(7.50, 7.22), (6.70, 6.42), (5.90, 5.62), (5.10, 4.80)]:
        _arrow(ax, 6.25, y1, 6.25, y2)

    _box(ax, 0.70, 2.85, 4.40, 0.85, "Verifier A\nA→A  (same)    B→A  (cross)", fc="#eef6f6", ec=TEAL)
    _box(ax, 7.40, 2.85, 4.40, 0.85, "Verifier B\nA→B  (cross)   B→B  (same)", fc="#eef2f7", ec=NAVY)

    _arrow(ax, 4.70, 4.15, 2.90, 3.70)
    _arrow(ax, 7.80, 4.15, 9.60, 3.70)

    _box(ax, 0.70, 1.80, 4.40, 0.70, "MetaQA score  ·  classification")
    _box(ax, 7.40, 1.80, 4.40, 0.70, "MetaQA score  ·  classification")
    _arrow(ax, 2.90, 2.85, 2.90, 2.50)
    _arrow(ax, 9.60, 2.85, 9.60, 2.50)

    _box(ax, 3.15, 0.45, 6.20, 0.95, "Paired statistical comparison\nWilcoxon signed-rank  ·  α = 0.05\nself-verification score difference  =  same − cross", fs=8.5)
    _arrow(ax, 2.90, 1.80, 5.20, 1.40)
    _arrow(ax, 9.60, 1.80, 7.30, 1.40)

    ax.add_patch(Rectangle((0.35, 4.00), 11.80, 0.08, facecolor="#d9d4c8", edgecolor="none"))
    ax.text(6.25, 3.85, "Only verifier identity changes between paired conditions", ha="center", fontsize=8, color=GOLD, fontstyle="italic")

    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def design_2x2_png(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 5.4), dpi=180)
    ax.set_xlim(0, 8.2)
    ax.set_ylim(0, 5.4)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.text(4.1, 5.05, "2×2 Experimental Design", ha="center", fontsize=15, color=NAVY, fontweight="bold")
    ax.text(4.1, 4.68, "Diagonal = same-model verification   ·   Off-diagonal = cross-model verification", ha="center", fontsize=8, color=SLATE)

    headers = ["", "Verifier A", "Verifier B"]
    rows = [
        ["Generator A", "A → A\nsame", "A → B\ncross"],
        ["Generator B", "B → A\ncross", "B → B\nsame"],
    ]
    colors = [
        ["#ffffff", "#e8f4f2", "#eef2f7"],
        ["#ffffff", "#eef2f7", "#e8f4f2"],
    ]
    x0, y0, cw, rh = 1.15, 1.55, 2.15, 1.20
    ax.text(x0 + cw * 1.5, y0 + 2 * rh + 0.25, "Verifier A", ha="center", fontsize=10, color=NAVY, fontweight="bold")
    ax.text(x0 + cw * 2.5, y0 + 2 * rh + 0.25, "Verifier B", ha="center", fontsize=10, color=NAVY, fontweight="bold")
    ax.text(x0 + cw * 0.5, y0 + 1.5 * rh, "Generator A", ha="center", va="center", fontsize=10, color=NAVY, fontweight="bold")
    ax.text(x0 + cw * 0.5, y0 + 0.5 * rh, "Generator B", ha="center", va="center", fontsize=10, color=NAVY, fontweight="bold")
    for i, row in enumerate(rows):
        for j, cell in enumerate(row[1:]):
            x = x0 + (j + 1) * cw
            y = y0 + (1 - i) * rh
            _box(ax, x + 0.08, y + 0.08, cw - 0.16, rh - 0.16, cell, fc=colors[i][j + 1], fs=11)
    ax.text(4.1, 0.85, "Independent variable: verifier identity relative to generator", ha="center", fontsize=8.5, color=SLATE)
    ax.text(4.1, 0.50, "Dependent variable: MetaQA hallucination score", ha="center", fontsize=8.5, color=SLATE)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _load_conditions() -> list[dict[str, str]]:
    with (PROCESSED / "condition_summary.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def result_charts() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    rows = _load_conditions()
    labels = [row["label"] for row in rows]
    means = [float(row["mean_score"]) for row in rows]
    nsure = [float(row["not_sure_rate"]) for row in rows]
    n = int(rows[0]["n"])
    colors = [TEAL, NAVY, GOLD, SLATE]

    fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=160)
    bars = ax.bar(labels, means, color=colors, width=0.62, edgecolor=EDGE, linewidth=0.6)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Mean hallucination score")
    ax.set_title(f"Mean hallucination score by 2×2 condition\n{DEMO}  ·  n={n} per condition  ·  experiment {EXP_ID[:8]}")
    ax.axhline(0.5, color="#999999", linestyle="--", linewidth=0.8, label="threshold = 0.5")
    ax.legend(frameon=False)
    for bar, value in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.03, f"{value:.2f}", ha="center", fontsize=9)
    fig.savefig(FIGURES / "fig4_mean_scores.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.4, 5.0), dpi=160)
    diffs = [-1.0, 1.0]
    ax.bar(["Generator A\n(same − cross)", "Generator B\n(same − cross)"], diffs, color=[TEAL, NAVY], width=0.45, edgecolor=EDGE)
    ax.set_ylim(-1.15, 1.15)
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.set_ylabel("Paired score difference")
    ax.set_title(f"Same-model vs cross-model paired differences\n{DEMO}  ·  n={n}")
    ax.text(0, -1.0 + 0.08, "−1.00", ha="center", fontsize=9)
    ax.text(1, 1.0 - 0.12, "+1.00", ha="center", fontsize=9)
    fig.savefig(FIGURES / "fig5_paired_differences.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    thresholds = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
    f1_a = [0.0] * 9
    f1_b = [0.6667] * 9
    prec_b = [0.5] * 9
    rec_b = [1.0] * 9
    fig, ax = plt.subplots(figsize=(8.0, 5.0), dpi=160)
    ax.plot(thresholds, f1_a, marker="o", color=TEAL, label="A→A and B→A  F1 = 0.00")
    ax.plot(thresholds, f1_b, marker="s", color=NAVY, label="A→B and B→B  F1 = 0.6667")
    ax.set_ylim(0, 1.05)
    ax.set_xlim(0.28, 0.72)
    ax.set_xlabel("Threshold")
    ax.set_ylabel("F1")
    ax.set_title(f"Threshold vs F1 (stored scores, no new LLM calls)\n{DEMO}  ·  38 labeled items; 2 Needs Review excluded")
    ax.legend(frameon=False)
    fig.savefig(FIGURES / "fig6_threshold_f1.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 5.0), dpi=160)
    ax.plot(thresholds, prec_b, marker="o", color=NAVY, label="Precision (verifier B conditions)")
    ax.plot(thresholds, rec_b, marker="s", color=GOLD, label="Recall (verifier B conditions)")
    ax.plot(thresholds, [0.0] * 9, marker="^", color=TEAL, label="Precision/recall (verifier A conditions)")
    ax.set_ylim(0, 1.08)
    ax.set_xlim(0.28, 0.72)
    ax.set_xlabel("Threshold")
    ax.set_ylabel("Score")
    ax.set_title(f"Threshold vs precision / recall\n{DEMO}  ·  values constant because scores are 0 or 1")
    ax.legend(frameon=False)
    fig.savefig(FIGURES / "fig7_threshold_pr.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.4), dpi=160)
    matrices = [
        ("A→A (verifier A)", [[19, 0], [19, 0]]),
        ("A→B (verifier B)", [[0, 19], [0, 19]]),
    ]
    for axis, (title, mat) in zip(axes, matrices):
        im = axis.imshow(mat, cmap="Blues", vmin=0, vmax=19)
        axis.set_xticks([0, 1], ["Pred. Reliable", "Pred. Hallucinated"], fontsize=8)
        axis.set_yticks([0, 1], ["Actual Reliable", "Actual Hallucinated"], fontsize=8)
        axis.set_title(title, fontsize=10)
        for i in range(2):
            for j in range(2):
                axis.text(j, i, str(mat[i][j]), ha="center", va="center", fontsize=14, color=NAVY)
        fig.colorbar(im, ax=axis, fraction=0.046)
    fig.suptitle(f"Confusion matrices at threshold 0.5  ·  {DEMO}  ·  n=38 labeled", fontsize=11, color=NAVY)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig8_confusion_matrix.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 4.8), dpi=160)
    ax.bar(labels, nsure, color=colors, width=0.62, edgecolor=EDGE)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("NOT SURE rate")
    ax.set_title(f"NOT SURE rate by condition\n{DEMO}  ·  n={n}")
    for i, value in enumerate(nsure):
        ax.text(i, value + 0.03, f"{value:.2f}", ha="center", fontsize=9)
    fig.savefig(FIGURES / "fig9_not_sure.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=160)
    ax.bar(["Generator A", "Generator B"], [1.0, 1.0], color=[TEAL, NAVY], width=0.5, edgecolor=EDGE)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Classification flip rate")
    ax.set_title(f"Classification flip rate by generator\n{DEMO}  ·  n={n}  ·  A: R→H 40/40  ·  B: H→R 40/40")
    ax.text(0, 1.03, "1.00", ha="center")
    ax.text(1, 1.03, "1.00", ha="center")
    fig.savefig(FIGURES / "fig10_flip_rate.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.experiment.stats import wilcoxon_signed_rank

    a_diffs = [-1.0] * 40
    b_diffs = [1.0] * 40
    test_a = wilcoxon_signed_rank(a_diffs)
    test_b = wilcoxon_signed_rank(b_diffs)
    print("wilcoxon_A", test_a)
    print("wilcoxon_B", test_b)

    FIGURES.mkdir(parents=True, exist_ok=True)
    architecture_png(DOCS / "architecture.png")
    research_flow_png(DOCS / "research_flow.png")
    design_2x2_png(FIGURES / "fig3_2x2_design.png")
    result_charts()
    print("wrote diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
