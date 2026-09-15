"""Aggregate 2×2 experiment records into paper-ready summaries.

Self-verification score difference is reported without labeling it as bias.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass

from app.evaluation.ground_truth import resolve_ground_truth
from app.evaluation.metrics import compute_metrics, confusion_counts
from app.evaluation.schemas import DatasetExample
from app.experiment.stats import paired_t_test, summarize_scores, wilcoxon_signed_rank
from app.metaqa.scoring import Classification

ALPHA = 0.05
EXPLORATORY_N = 20
MIN_CATEGORY_N = 5


@dataclass(frozen=True)
class ConditionSummary:
    generator_model: str
    verifier_model: str
    pair_type: str
    label: str
    n: int
    mean_score: float
    median_score: float
    stdev: float
    ci95_low: float | None
    ci95_high: float | None
    reliable_count: int
    hallucinated_count: int
    reliable_rate: float
    hallucinated_rate: float
    not_sure_rate: float
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    accuracy: float | None = None


def pair_type_for(generator_model: str, verifier_model: str) -> str:
    return "same" if generator_model == verifier_model else "cross"


def _rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


def summarize_condition(
    *,
    generator_model: str,
    verifier_model: str,
    scores: list[float],
    classifications: list[str],
    not_sure_rates: list[float],
    actuals: list[Classification] | None = None,
    labeled_classifications: list[str] | None = None,
    label: str | None = None,
) -> ConditionSummary:
    summary = summarize_scores(scores)
    n = len(scores)
    reliable = sum(1 for item in classifications if item == Classification.RELIABLE.value)
    hallucinated = n - reliable
    precision = recall = f1 = accuracy = None
    if actuals and labeled_classifications and len(actuals) == len(labeled_classifications):
        preds = [Classification(item) for item in labeled_classifications]
        metrics = compute_metrics(confusion_counts(actuals, preds))
        precision = metrics.precision
        recall = metrics.recall
        f1 = metrics.f1
        accuracy = metrics.accuracy
    return ConditionSummary(
        generator_model=generator_model,
        verifier_model=verifier_model,
        pair_type=pair_type_for(generator_model, verifier_model),
        label=label or f"{_short(generator_model)} → {_short(verifier_model)}",
        n=summary.n,
        mean_score=summary.mean,
        median_score=summary.median,
        stdev=summary.stdev,
        ci95_low=summary.ci95_low,
        ci95_high=summary.ci95_high,
        reliable_count=reliable,
        hallucinated_count=hallucinated,
        reliable_rate=_rate(reliable, n),
        hallucinated_rate=_rate(hallucinated, n),
        not_sure_rate=round(sum(not_sure_rates) / n, 4) if n else 0.0,
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
    )


def _short(model: str) -> str:
    if model.lower() in {"model-a", "model_a", "a"}:
        return "A"
    if model.lower() in {"model-b", "model_b", "b"}:
        return "B"
    return model


def _pair_key(item: dict) -> tuple[str, int]:
    return item["question_id"], int(item.get("trial_num") or 1)


def paired_rows(
    same_rows: list[dict],
    cross_rows: list[dict],
) -> list[dict]:
    by_key = {_pair_key(item): item for item in cross_rows}
    paired: list[dict] = []
    for same in same_rows:
        other = by_key.get(_pair_key(same))
        if other is None:
            continue
        difference = round(same["hallucination_score"] - other["hallucination_score"], 4)
        trial_num = int(same.get("trial_num") or 1)
        paired.append(
            {
                "question_id": same["question_id"],
                "question": same["question"],
                "generator_model": same["generator_model"],
                "generation_id": same.get("generation_id"),
                "trial_num": trial_num,
                "same_model_score": same["hallucination_score"],
                "cross_model_score": other["hallucination_score"],
                "difference": difference,
                "same_label": same["classification"],
                "cross_label": other["classification"],
                "classification_flip": same["classification"] != other["classification"],
            }
        )
    return paired


def self_verification_block(paired: list[dict], generator_model: str) -> dict:
    diffs = [item["difference"] for item in paired]
    same_scores = [item["same_model_score"] for item in paired]
    cross_scores = [item["cross_model_score"] for item in paired]
    same_mean = round(sum(same_scores) / len(same_scores), 4) if same_scores else 0.0
    cross_mean = round(sum(cross_scores) / len(cross_scores), 4) if cross_scores else 0.0
    difference = round(same_mean - cross_mean, 4)
    abs_effect = round(abs(difference), 4)
    pct = round((difference / cross_mean) * 100, 2) if cross_mean else None
    flips = sum(1 for item in paired if item["classification_flip"])
    wilcoxon = wilcoxon_signed_rank(diffs)
    ttest = paired_t_test(diffs)
    exploratory = len(paired) < EXPLORATORY_N
    p_below_alpha = wilcoxon.p_value is not None and wilcoxon.p_value < ALPHA
    # Do not call a small-n result "statistically significant".
    significant = p_below_alpha and not exploratory
    median_diff = round(statistics.median(diffs), 4) if diffs else 0.0
    return {
        "generator_model": generator_model,
        "same_model_mean": same_mean,
        "cross_model_mean": cross_mean,
        "self_verification_score_difference": difference,
        "mean_paired_difference": difference,
        "median_paired_difference": median_diff,
        "absolute_effect": abs_effect,
        "percent_difference": pct,
        "classification_flip_rate": _rate(flips, len(paired)),
        "flip_count": flips,
        "n": len(paired),
        "exploratory": exploratory,
        "wilcoxon": asdict(wilcoxon),
        "paired_t_test": asdict(ttest),
        "significant": significant,
        "alpha": ALPHA,
    }


def format_p_value(p_value: float | None) -> str:
    if p_value is None:
        return "n/a"
    if p_value < 0.001:
        return "p<0.001"
    return f"p={p_value}"


def key_finding_text(blocks: list[dict], *, demo: bool, dataset: str) -> str:
    prefix = "DEMO / MOCK DATA. " if demo else ""
    prefix += f"Empirical result on dataset '{dataset}'. "
    if not blocks:
        return prefix + "No paired comparisons were available."
    parts: list[str] = []
    for block in blocks:
        name = _short(block["generator_model"])
        diff = block["self_verification_score_difference"]
        p_value = block["wilcoxon"]["p_value"]
        p_text = format_p_value(p_value)
        exploratory = bool(block.get("exploratory"))
        small = " This sample is small; treat the result as exploratory." if exploratory else ""
        if p_value is None:
            parts.append(
                f"Generator {name}: paired differences could not be tested statistically.{small}"
            )
            continue
        p_below_alpha = p_value < ALPHA
        if not p_below_alpha:
            parts.append(
                f"Generator {name}: no statistically significant difference was detected between "
                f"same-model and cross-model verification under these experimental conditions "
                f"({p_text}).{small}"
            )
            continue
        if diff == 0:
            parts.append(
                f"Generator {name}: paired scores differed in rank but the mean difference was zero "
                f"({p_text}).{small}"
            )
            continue
        direction = "lower" if diff < 0 else "higher"
        if exploratory:
            parts.append(
                f"Same-model verification produced {direction} hallucination scores for Generator {name} "
                f"({p_text}).{small}"
            )
        else:
            parts.append(
                f"Same-model verification produced {direction} hallucination scores for Generator {name}, "
                f"with a statistically significant paired difference ({p_text})."
            )
    return prefix + " ".join(parts)


def research_summary(
    *,
    blocks: list[dict],
    condition_summaries: list[dict],
    question_count: int,
    classification_flip_rate: float,
    demo: bool,
    dataset: str,
) -> dict:
    """Factual summary derived only from computed experiment numbers."""
    generators = []
    for block in blocks:
        generators.append(
            {
                "generator_model": block["generator_model"],
                "n": block["n"],
                "same_model_score": block["same_model_mean"],
                "cross_model_score": block["cross_model_mean"],
                "score_difference": block["self_verification_score_difference"],
                "absolute_effect": block["absolute_effect"],
                "flip_rate": block["classification_flip_rate"],
                "p_value": block["wilcoxon"]["p_value"],
                "effect_size": block["wilcoxon"]["effect_size"],
                "statistically_significant": block["significant"],
                "exploratory": block["exploratory"],
            }
        )
    return {
        "dataset": dataset,
        "sample_size": question_count,
        "demo_data": demo,
        "alpha": ALPHA,
        "condition_means": [
            {
                "label": item["label"],
                "generator_model": item["generator_model"],
                "verifier_model": item["verifier_model"],
                "pair_type": item["pair_type"],
                "n": item["n"],
                "mean_score": item["mean_score"],
            }
            for item in condition_summaries
        ],
        "generators": generators,
        "classification_flip_rate": classification_flip_rate,
        "narrative": key_finding_text(blocks, demo=demo, dataset=dataset),
    }


def actual_label_for(answer: str, example: DatasetExample | None) -> Classification | None:
    if example is None:
        return None
    decision = resolve_ground_truth(answer, example)
    return None if decision.is_review else decision.label


def group_condition_rows(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["generator_model"], row["verifier_model"])].append(row)
    return grouped


def category_analysis(paired: list[dict], rows: list[dict]) -> list[dict]:
    """Secondary analysis from saved scores. No additional LLM calls."""
    category_by_qid = {}
    for row in rows:
        if row.get("category"):
            category_by_qid[row["question_id"]] = row["category"]
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in paired:
        category = category_by_qid.get(item["question_id"], "unknown")
        grouped[(category, item["generator_model"])].append(item)
    out: list[dict] = []
    for (category, generator), items in sorted(grouped.items()):
        n = len(items)
        insufficient = n < MIN_CATEGORY_N
        same_mean = round(sum(i["same_model_score"] for i in items) / n, 4) if n else 0.0
        cross_mean = round(sum(i["cross_model_score"] for i in items) / n, 4) if n else 0.0
        flips = sum(1 for i in items if i["classification_flip"])
        out.append(
            {
                "category": category,
                "generator_model": generator,
                "n": n,
                "same_model_mean": same_mean,
                "cross_model_mean": cross_mean,
                "score_difference": round(same_mean - cross_mean, 4),
                "flip_rate": round(flips / n, 4) if n else 0.0,
                "insufficient_data": insufficient,
                "note": (
                    f"n={n} is below {MIN_CATEGORY_N}; treat category statistics as insufficient."
                    if insufficient
                    else ""
                ),
            }
        )
    return out
