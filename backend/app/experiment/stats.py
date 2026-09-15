"""Paired statistical helpers for the 2×2 verifier experiment.

Wilcoxon signed-rank is the primary test. The paired t-test is optional.
Neither function claims significance; callers compare p to alpha=0.05.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreSummary:
    n: int
    mean: float
    median: float
    stdev: float
    ci95_low: float | None
    ci95_high: float | None


@dataclass(frozen=True)
class HypothesisTest:
    name: str
    statistic: float | None
    p_value: float | None
    n: int
    effect_size: float | None
    notes: str = ""


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def summarize_scores(values: list[float]) -> ScoreSummary:
    n = len(values)
    if n == 0:
        return ScoreSummary(n=0, mean=0.0, median=0.0, stdev=0.0, ci95_low=None, ci95_high=None)
    mean = statistics.fmean(values)
    median = statistics.median(values)
    stdev = statistics.stdev(values) if n > 1 else 0.0
    if n < 2:
        return ScoreSummary(n=n, mean=round(mean, 4), median=round(median, 4), stdev=0.0, ci95_low=None, ci95_high=None)
    se = stdev / math.sqrt(n)
    z = 1.96
    return ScoreSummary(
        n=n,
        mean=round(mean, 4),
        median=round(median, 4),
        stdev=round(stdev, 4),
        ci95_low=round(mean - z * se, 4),
        ci95_high=round(mean + z * se, 4),
    )


def _normal_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _average_ranks(abs_values: list[float]) -> list[float]:
    indexed = sorted(enumerate(abs_values), key=lambda item: item[1])
    ranks = [0.0] * len(abs_values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg
        i = j + 1
    return ranks


def wilcoxon_signed_rank(differences: list[float]) -> HypothesisTest:
    """Two-sided Wilcoxon signed-rank test on paired differences.

    Zeros are dropped. Average ranks are used for ties. For n >= 10 a normal
    approximation is used; smaller samples are labeled exploratory.
    """
    nonzero = [value for value in differences if value != 0]
    n = len(nonzero)
    if n == 0:
        return HypothesisTest(
            name="wilcoxon_signed_rank",
            statistic=None,
            p_value=None,
            n=0,
            effect_size=None,
            notes="No non-zero paired differences.",
        )
    ranks = _average_ranks([abs(value) for value in nonzero])
    t_plus = sum(rank for value, rank in zip(nonzero, ranks, strict=True) if value > 0)
    t_minus = sum(rank for value, rank in zip(nonzero, ranks, strict=True) if value < 0)
    statistic = min(t_plus, t_minus)
    mean = n * (n + 1) / 4.0
    tie_groups: dict[float, int] = {}
    for rank_size in ranks:
        tie_groups[rank_size] = tie_groups.get(rank_size, 0) + 1
    tie_term = sum(t * t * t - t for t in tie_groups.values() if t > 1)
    variance = n * (n + 1) * (2 * n + 1) / 24.0 - tie_term / 48.0
    if variance <= 0:
        return HypothesisTest(
            name="wilcoxon_signed_rank",
            statistic=_round(statistic),
            p_value=None,
            n=n,
            effect_size=None,
            notes="Wilcoxon variance collapsed; p-value not computed.",
        )
    z = (t_plus - mean) / math.sqrt(variance)
    p_raw = min(1.0, max(0.0, 2 * _normal_sf(abs(z))))
    effect = z / math.sqrt(n)
    notes = "Normal approximation to the Wilcoxon signed-rank null."
    if n < 20:
        notes += " Sample is small; treat the result as exploratory."
    if p_raw == 0.0:
        notes += " p-value underflowed floating-point precision; report as p<0.001."
        p_stored = 0.0
    else:
        p_stored = round(p_raw, 8)
    return HypothesisTest(
        name="wilcoxon_signed_rank",
        statistic=_round(statistic),
        p_value=p_stored,
        n=n,
        effect_size=_round(effect),
        notes=notes,
    )


def paired_t_test(differences: list[float]) -> HypothesisTest:
    """Optional paired t-test on the same differences. Uses a normal tail for p."""
    n = len(differences)
    if n < 2:
        return HypothesisTest(
            name="paired_t_test",
            statistic=None,
            p_value=None,
            n=n,
            effect_size=None,
            notes="Need at least two paired differences.",
        )
    mean = statistics.fmean(differences)
    stdev = statistics.stdev(differences)
    if stdev == 0:
        p_value = 0.0 if mean != 0 else 1.0
        return HypothesisTest(
            name="paired_t_test",
            statistic=None if mean == 0 else float("inf"),
            p_value=p_value,
            n=n,
            effect_size=None if stdev == 0 and mean == 0 else (None if stdev == 0 else round(mean / stdev, 4)),
            notes="Zero variance among paired differences.",
        )
    se = stdev / math.sqrt(n)
    t_stat = mean / se
    # Large-sample two-sided p-value; adequate for n around the pilot size.
    p_value = min(1.0, max(0.0, 2 * _normal_sf(abs(t_stat))))
    return HypothesisTest(
        name="paired_t_test",
        statistic=_round(t_stat),
        p_value=_round(p_value, 6),
        n=n,
        effect_size=_round(mean / stdev),
        notes="Paired t-test with normal tail approximation (optional).",
    )
