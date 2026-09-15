"""Evaluation metrics for VeriFact.

Positive class = Hallucinated (the error VeriFact aims to detect).

Confusion matrix (Actual × Predicted):

                    Predicted
                    Reliable    Hallucinated
Actual Reliable     TN          FP
Actual Hallucinated FN          TP

TP: actual Hallucinated + predicted Hallucinated
TN: actual Reliable + predicted Reliable
FP: actual Reliable + predicted Hallucinated
FN: actual Hallucinated + predicted Reliable

Needs Review examples are excluded from these counts.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.metaqa.scoring import Classification, classify

DEFAULT_THRESHOLDS = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70)


@dataclass(frozen=True)
class ConfusionCounts:
    tp: int
    tn: int
    fp: int
    fn: int

    @property
    def total(self) -> int:
        return self.tp + self.tn + self.fp + self.fn


@dataclass(frozen=True)
class MetricSet:
    tp: int
    tn: int
    fp: int
    fn: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    specificity: float
    fpr: float
    fnr: float
    included_examples: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "tp": self.tp,
            "tn": self.tn,
            "fp": self.fp,
            "fn": self.fn,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "specificity": self.specificity,
            "fpr": self.fpr,
            "fnr": self.fnr,
            "included_examples": self.included_examples,
        }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def confusion_counts(
    actuals: list[Classification],
    predictions: list[Classification],
) -> ConfusionCounts:
    if len(actuals) != len(predictions):
        raise ValueError("Actual and predicted label lists must be the same length.")
    tp = tn = fp = fn = 0
    for actual, predicted in zip(actuals, predictions, strict=True):
        if actual is Classification.HALLUCINATED and predicted is Classification.HALLUCINATED:
            tp += 1
        elif actual is Classification.RELIABLE and predicted is Classification.RELIABLE:
            tn += 1
        elif actual is Classification.RELIABLE and predicted is Classification.HALLUCINATED:
            fp += 1
        elif actual is Classification.HALLUCINATED and predicted is Classification.RELIABLE:
            fn += 1
        else:
            raise ValueError(f"Unsupported label pair: {actual} / {predicted}")
    return ConfusionCounts(tp=tp, tn=tn, fp=fp, fn=fn)


def outcome_label(actual: Classification, predicted: Classification) -> str:
    if actual is Classification.HALLUCINATED and predicted is Classification.HALLUCINATED:
        return "TP"
    if actual is Classification.RELIABLE and predicted is Classification.RELIABLE:
        return "TN"
    if actual is Classification.RELIABLE and predicted is Classification.HALLUCINATED:
        return "FP"
    if actual is Classification.HALLUCINATED and predicted is Classification.RELIABLE:
        return "FN"
    raise ValueError(f"Unsupported label pair: {actual} / {predicted}")


def compute_metrics(counts: ConfusionCounts) -> MetricSet:
    total = counts.total
    precision = _ratio(counts.tp, counts.tp + counts.fp)
    recall = _ratio(counts.tp, counts.tp + counts.fn)
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = round(2 * precision * recall / (precision + recall), 4)
    return MetricSet(
        tp=counts.tp,
        tn=counts.tn,
        fp=counts.fp,
        fn=counts.fn,
        accuracy=_ratio(counts.tp + counts.tn, total),
        precision=precision,
        recall=recall,
        f1=f1,
        specificity=_ratio(counts.tn, counts.tn + counts.fp),
        fpr=_ratio(counts.fp, counts.fp + counts.tn),
        fnr=_ratio(counts.fn, counts.fn + counts.tp),
        included_examples=total,
    )


def classify_scores(scores: list[float], threshold: float) -> list[Classification]:
    return [classify(score, threshold) for score in scores]


def sweep_thresholds(
    actuals: list[Classification],
    scores: list[float],
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> list[tuple[float, MetricSet]]:
    """Re-classify saved scores. Does not re-run detection."""
    if len(actuals) != len(scores):
        raise ValueError("Actual labels and scores must be the same length.")
    rows: list[tuple[float, MetricSet]] = []
    for threshold in thresholds:
        predictions = classify_scores(scores, threshold)
        rows.append((threshold, compute_metrics(confusion_counts(actuals, predictions))))
    return rows


def best_threshold_by_f1(rows: list[tuple[float, MetricSet]]) -> float | None:
    if not rows:
        return None
    best_f1 = -1.0
    best_threshold = rows[0][0]
    for threshold, metrics in rows:
        if metrics.f1 > best_f1 or (metrics.f1 == best_f1 and threshold < best_threshold):
            best_f1 = metrics.f1
            best_threshold = threshold
    return best_threshold
