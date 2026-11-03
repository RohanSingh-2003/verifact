from __future__ import annotations

from collections import Counter, defaultdict
import random
from typing import Any


def compute_cohens_kappa(rater1: list[str], rater2: list[str]) -> float | None:
    """Calculate Cohen's kappa coefficient between two raters.
    
    Formula:
        kappa = (P_o - P_e) / (1 - P_e)
    Where:
        P_o = observed proportionate agreement
        P_e = hypothetical probability of chance agreement
    Returns None if fewer than 2 paired ratings exist or denominator is 0.
    """
    if len(rater1) != len(rater2) or len(rater1) < 2:
        return None

    paired = [(r1.strip().upper(), r2.strip().upper()) for r1, r2 in zip(rater1, rater2, strict=True) if r1 and r2]
    n = len(paired)
    if n < 2:
        return None

    # Distinct categories
    categories = sorted({c for p in paired for c in p})
    if len(categories) <= 1:
        return 1.0  # Perfect agreement on single category

    # Observed agreement
    observed_matches = sum(1 for c1, c2 in paired if c1 == c2)
    p_o = observed_matches / n

    # Marginal totals
    r1_counts = Counter(c1 for c1, _ in paired)
    r2_counts = Counter(c2 for _, c2 in paired)

    # Expected chance agreement
    p_e = sum((r1_counts[c] / n) * (r2_counts[c] / n) for c in categories)

    if abs(1.0 - p_e) < 1e-9:
        return 1.0 if p_o == 1.0 else 0.0

    kappa = (p_o - p_e) / (1.0 - p_e)
    return round(float(kappa), 4)


def compute_judge_human_agreement(judge_labels: list[str], human_labels: list[str]) -> dict[str, Any]:
    """Calculate agreement metrics between Gemini judge preliminary labels and human adjudicated labels."""
    if len(judge_labels) != len(human_labels) or len(judge_labels) == 0:
        return {
            "total_pairs": 0,
            "observed_agreement": None,
            "cohens_kappa": None,
            "matches": 0,
            "mismatches": 0,
        }

    paired = [
        (j.strip().upper(), h.strip().upper())
        for j, h in zip(judge_labels, human_labels, strict=True)
        if j and h and j not in {"NONE", "NOT_RUN", "FAILED"} and h not in {"NONE", "UNREVIEWED"}
    ]
    n = len(paired)
    if n == 0:
        return {
            "total_pairs": 0,
            "observed_agreement": None,
            "cohens_kappa": None,
            "matches": 0,
            "mismatches": 0,
        }

    matches = sum(1 for j, h in paired if j == h)
    p_o = round(matches / n, 4)
    kappa = compute_cohens_kappa([j for j, _ in paired], [h for _, h in paired])

    return {
        "total_pairs": n,
        "observed_agreement": p_o,
        "cohens_kappa": kappa,
        "matches": matches,
        "mismatches": n - matches,
    }


def select_stratified_sample(
    items: list[dict[str, Any]],
    sample_size: int = 100,
    *,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Select a stratified research sample of generated answers for human review.
    
    Stratified by dataset/category and judge preliminary label.
    """
    if len(items) <= sample_size:
        return list(items)

    rng = random.Random(seed)
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for item in items:
        cat = str(item.get("category") or item.get("dataset_name") or "general_fact")
        judge = str(item.get("judge_label") or item.get("actual_label") or "UNKNOWN")
        strata[(cat, judge)].append(item)

    selected: list[dict[str, Any]] = []
    # Calculate target per stratum
    num_strata = len(strata)
    per_stratum_base = max(1, sample_size // num_strata)

    remaining_pool: list[dict[str, Any]] = []
    for key, group in strata.items():
        shuffled = list(group)
        rng.shuffle(shuffled)
        take = min(len(shuffled), per_stratum_base)
        selected.extend(shuffled[:take])
        remaining_pool.extend(shuffled[take:])

    # Fill remainder up to sample_size
    if len(selected) < sample_size and remaining_pool:
        rng.shuffle(remaining_pool)
        needed = sample_size - len(selected)
        selected.extend(remaining_pool[:needed])

    return selected[:sample_size]

