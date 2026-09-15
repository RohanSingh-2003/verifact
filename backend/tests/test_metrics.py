from app.evaluation.metrics import (
    ConfusionCounts,
    best_threshold_by_f1,
    compute_metrics,
    confusion_counts,
    outcome_label,
    sweep_thresholds,
)
from app.metaqa.scoring import Classification


H = Classification.HALLUCINATED
R = Classification.RELIABLE


def test_confusion_and_metrics_standard_case() -> None:
    actuals = [H, H, R, R, H, R]
    preds = [H, R, R, H, H, R]
    counts = confusion_counts(actuals, preds)
    assert counts == ConfusionCounts(tp=2, tn=2, fp=1, fn=1)
    metrics = compute_metrics(counts)
    assert metrics.precision == 0.6667
    assert metrics.recall == 0.6667
    assert metrics.f1 == 0.6667
    assert metrics.accuracy == 0.6667
    assert metrics.fpr == 0.3333
    assert metrics.fnr == 0.3333
    assert metrics.specificity == 0.6667


def test_outcomes() -> None:
    assert outcome_label(H, H) == "TP"
    assert outcome_label(R, R) == "TN"
    assert outcome_label(R, H) == "FP"
    assert outcome_label(H, R) == "FN"


def test_zero_denominators() -> None:
    metrics = compute_metrics(ConfusionCounts(tp=0, tn=4, fp=0, fn=0))
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0
    assert metrics.fpr == 0.0
    assert metrics.fnr == 0.0
    assert metrics.accuracy == 1.0
    assert metrics.specificity == 1.0

    empty = compute_metrics(ConfusionCounts(tp=0, tn=0, fp=0, fn=0))
    assert empty.accuracy == 0.0
    assert empty.precision == 0.0
    assert empty.recall == 0.0
    assert empty.f1 == 0.0
    assert empty.fpr == 0.0
    assert empty.fnr == 0.0


def test_all_false_positives() -> None:
    metrics = compute_metrics(ConfusionCounts(tp=0, tn=0, fp=5, fn=0))
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.fpr == 1.0
    assert metrics.accuracy == 0.0


def test_threshold_sweep_uses_saved_scores() -> None:
    actuals = [H, H, R, R]
    scores = [0.8, 0.4, 0.2, 0.6]
    rows = sweep_thresholds(actuals, scores, thresholds=(0.3, 0.5, 0.7))
    at_half = dict(rows)[0.5]
    assert at_half.tp == 1
    assert at_half.fn == 1
    assert at_half.fp == 1
    assert at_half.tn == 1
    assert best_threshold_by_f1(rows) in {0.3, 0.5, 0.7}


def test_best_f1_threshold_prefers_higher_f1_then_lower_threshold() -> None:
    actuals = [H, H, R, R]
    scores = [0.62, 0.58, 0.41, 0.39]
    rows = sweep_thresholds(actuals, scores, thresholds=(0.4, 0.5, 0.6))
    assert best_threshold_by_f1(rows) == 0.5
