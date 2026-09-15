from __future__ import annotations

import logging
import re
from enum import Enum

logger = logging.getLogger("verifact.metaqa")


class MutationType(str, Enum):
    SYNONYM = "synonym"
    ANTONYM = "antonym"


class Verdict(str, Enum):
    YES = "YES"
    NO = "NO"
    NOT_SURE = "NOT SURE"


class Classification(str, Enum):
    HALLUCINATED = "Hallucinated"
    RELIABLE = "Reliable"


SYNONYM_CONTRIBUTION: dict[Verdict, float] = {
    Verdict.YES: 0.0,
    Verdict.NO: 1.0,
    Verdict.NOT_SURE: 0.5,
}

ANTONYM_CONTRIBUTION: dict[Verdict, float] = {
    Verdict.YES: 1.0,
    Verdict.NO: 0.0,
    Verdict.NOT_SURE: 0.5,
}

_LABELS = {item.value for item in Verdict}
_PREFIX = re.compile(r"^(VERDICT|ANSWER|LABEL|OUTPUT)\s*[:\-]\s*", re.IGNORECASE)
_TRAILING_PUNCT = re.compile(r"[\s.!,;:]+$")
_NOT_SURE_RE = re.compile(r"\bNOT[\s_-]*SURE\b", re.IGNORECASE)
_YES_RE = re.compile(r"\bYES\b", re.IGNORECASE)
_NO_RE = re.compile(r"\bNO\b", re.IGNORECASE)


def expected_verdict(mutation_type: MutationType) -> Verdict:
    if mutation_type is MutationType.SYNONYM:
        return Verdict.YES
    if mutation_type is MutationType.ANTONYM:
        return Verdict.NO
    raise ValueError(f"Unsupported mutation type: {mutation_type}")


def contribution_score(mutation_type: MutationType, verdict: Verdict) -> float:
    if mutation_type is MutationType.SYNONYM:
        return SYNONYM_CONTRIBUTION[verdict]
    if mutation_type is MutationType.ANTONYM:
        return ANTONYM_CONTRIBUTION[verdict]
    raise ValueError(f"Unsupported mutation type: {mutation_type}")


def aggregate_score(contributions: list[float]) -> float:
    if not contributions:
        raise ValueError("Cannot aggregate an empty contribution list.")
    mean = sum(contributions) / len(contributions)
    bounded = min(1.0, max(0.0, mean))
    return round(bounded, 4)


def classify(score: float, threshold: float) -> Classification:
    if score >= threshold:
        return Classification.HALLUCINATED
    return Classification.RELIABLE


def not_sure_rate(verdicts: list[Verdict]) -> float:
    if not verdicts:
        raise ValueError("Cannot compute NOT SURE rate for an empty verdict list.")
    count = sum(1 for item in verdicts if item is Verdict.NOT_SURE)
    return round(count / len(verdicts), 4)


def parse_verdict(raw: str | None) -> tuple[Verdict, bool]:
    """Parse a verifier label.

    Returns (verdict, parse_failed). Unparseable values become NOT SURE.
    Ambiguous text that contains both YES and NO is never guessed.
    """
    if raw is None:
        logger.warning("Verifier returned an empty verdict; treating as NOT SURE.")
        return Verdict.NOT_SURE, True

    text = str(raw).strip().strip("\"'`")
    if not text:
        logger.warning("Verifier returned an empty verdict; treating as NOT SURE.")
        return Verdict.NOT_SURE, True

    normalized = _TRAILING_PUNCT.sub("", _PREFIX.sub("", re.sub(r"\s+", " ", text).strip())).upper()
    if normalized in _LABELS:
        return Verdict(normalized), False

    if _NOT_SURE_RE.search(text):
        return Verdict.NOT_SURE, False

    has_yes = bool(_YES_RE.search(text))
    has_no = bool(_NO_RE.search(text))
    if has_yes and not has_no:
        return Verdict.YES, False
    if has_no and not has_yes:
        return Verdict.NO, False

    logger.warning("Unparseable verifier verdict %r; treating as NOT SURE.", text[:200])
    return Verdict.NOT_SURE, True
