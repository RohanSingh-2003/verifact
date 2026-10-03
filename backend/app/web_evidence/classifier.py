"""Deterministic question-type classifier (question text only)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.web_evidence.question_types import QUESTION_TYPE_LABELS, QuestionType

# Recency cues → prefer CURRENT_EVENT when topical.
_FRESHNESS_CUES = frozenset(
    {
        "latest",
        "yesterday",
        "today",
        "tonight",
        "this week",
        "this month",
        "breaking",
        "just announced",
        "recently",
        "ongoing",
        "currently",
        "live score",
        "live updates",
        "what happened",
        "happening now",
    }
)

# Year cues often mean historical / settled facts (not current events).
_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20[0-1]\d|202[0-3])\b")

# (type, weight, patterns) — higher weight wins; first tie-break by order below.
_RULES: list[tuple[QuestionType, float, tuple[str, ...]]] = [
    (
        QuestionType.FACT_CHECK,
        3.0,
        (
            "fact check",
            "is it true",
            "is this true",
            "did they really",
            "debunk",
            "hoax",
            "misinformation",
            "true or false",
            "verify the claim",
        ),
    ),
    (
        QuestionType.STATISTICS,
        2.8,
        (
            "gdp",
            "unemployment rate",
            "inflation rate",
            "census",
            "statistics",
            "statistical",
            "population of",
            "how many people",
            "poverty rate",
            "literacy rate",
            "crime rate",
            "growth rate",
            "official figures",
            "data show",
            "dataset",
        ),
    ),
    (
        QuestionType.MEDICINE_HEALTH,
        2.7,
        (
            "who guidelines",
            "cdc",
            "nih",
            "vaccine",
            "vaccination",
            "disease",
            "symptom",
            "treatment for",
            "clinical trial",
            "medical",
            "health ministry",
            "covid",
            "cancer",
            "diabetes",
            "antibiotic",
            "patient",
            "epidemiology",
        ),
    ),
    (
        QuestionType.ACADEMIC_RESEARCH,
        2.8,
        (
            "research paper",
            "peer reviewed",
            "peer-reviewed",
            "arxiv",
            "journal article",
            "study found",
            "meta analysis",
            "meta-analysis",
            "doi",
            "published in",
            "academic",
            "hallucination",
            "hallucinations",
            "llm hallucination",
            "technical terms",
            "technical term",
            "large language model",
            "neural network",
            "deep learning",
            "natural language processing",
            "transformer model",
        ),
    ),
    (
        QuestionType.SCIENCE,
        2.7,
        (
            "photosynthesis",
            "james webb",
            "telescope",
            "nasa",
            "esa",
            "quantum",
            "physics",
            "chemistry",
            "biology",
            "astronomy",
            "galaxy",
            "black hole",
            "molecule",
            "atom",
            "scientific",
            "experiment",
            "climate science",
            "newton's law",
            "newton's laws",
            "laws of motion",
            "isaac newton",
            "theory of relativity",
            "albert einstein",
            "gravity",
            "evolution",
        ),
    ),
    (
        QuestionType.GOVERNMENT_POLICY,
        2.6,
        (
            "government announce",
            "government announced",
            "ministry",
            "legislation",
            "regulation",
            "policy on",
            "cabinet",
            "parliament passed",
            "bill passed",
            "official gazette",
            "executive order",
            "white house",
            "prime minister announced",
            "what did the government",
        ),
    ),
    (
        QuestionType.POLITICS,
        2.5,
        (
            "election",
            "electoral",
            "candidate",
            "political party",
            "vote share",
            "parliament seat",
            "congress seat",
            "campaign",
            "ballot",
            "president elect",
            "prime minister election",
        ),
    ),
    (
        QuestionType.TECHNOLOGY,
        2.5,
        (
            "react documentation",
            "documentation say",
            "api reference",
            "software",
            "programming",
            "javascript",
            "typescript",
            "python package",
            "github",
            "open source",
            "kubernetes",
            "docker",
            "hooks",
            "react hooks",
            "explain react",
            "framework",
            "sdk",
            "rfc",
            "w3c",
            "what does the react",
        ),
    ),
    (
        QuestionType.BUSINESS_FINANCE,
        2.4,
        (
            "stock price",
            "earnings",
            "sec filing",
            "company filed",
            "market cap",
            "ipo",
            "revenue",
            "quarterly results",
            "financial report",
            "nasdaq",
            "nyse",
            "shareholder",
            "merger",
            "acquisition",
        ),
    ),
    (
        QuestionType.SPORTS,
        2.5,
        (
            "world cup",
            "champions league",
            "premier league",
            "cricket match",
            "cricket",
            "bcci",
            "icc",
            "ipl",
            "olympic",
            "fifa",
            "nba",
            "nfl",
            "match score",
            "tournament",
            "grand slam",
            "wicket",
            "goal scored",
            "who won",
        ),
    ),
    (
        QuestionType.HISTORY,
        2.3,
        (
            "in history",
            "historical",
            "ancient",
            "medieval",
            "world war",
            "who discovered",
            "who invented",
            "who formulated",
            "founded in",
            "independence",
            "revolution of",
            "century",
            "archaeology",
            "museum",
        ),
    ),
    (
        QuestionType.CURRENT_EVENT,
        2.2,
        (
            "news about",
            "headline",
            "breaking news",
            "trade negotiations",
            "summit",
            "press conference",
        ),
    ),
    (
        QuestionType.GENERAL_FACT,
        1.5,
        (
            "capital of",
            "who is",
            "what is the",
            "where is",
            "when was",
            "definition of",
            "meaning of",
        ),
    ),
]


@dataclass(frozen=True)
class QuestionClassification:
    type: QuestionType
    confidence: float
    reason: str
    freshness_required: bool = False

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "label": QUESTION_TYPE_LABELS[self.type],
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "freshness_required": self.freshness_required,
        }


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _has_freshness_cue(normalized: str) -> bool:
    return any(cue in normalized for cue in _FRESHNESS_CUES)


def classify_question(question: str) -> QuestionClassification:
    """Classify a user question for evidence routing (no answer text used)."""
    raw = (question or "").strip()
    if not raw:
        return QuestionClassification(
            type=QuestionType.OTHER,
            confidence=0.4,
            reason="Empty question.",
            freshness_required=False,
        )

    normalized = _normalize(raw)
    freshness = _has_freshness_cue(normalized)
    has_old_year = bool(_YEAR_RE.search(normalized))

    scores: dict[QuestionType, float] = {}
    matched: dict[QuestionType, str] = {}
    for qtype, weight, patterns in _RULES:
        for pattern in patterns:
            if pattern in normalized:
                scores[qtype] = scores.get(qtype, 0.0) + weight
                matched.setdefault(qtype, pattern)
                break

    # Freshness without a strong topical match → CURRENT_EVENT.
    if freshness and not has_old_year:
        scores[QuestionType.CURRENT_EVENT] = scores.get(QuestionType.CURRENT_EVENT, 0.0) + 2.0
        matched.setdefault(QuestionType.CURRENT_EVENT, "recency cue")

    # Historical year + sports/history: dampen CURRENT_EVENT.
    if has_old_year and QuestionType.CURRENT_EVENT in scores:
        scores[QuestionType.CURRENT_EVENT] *= 0.25

    if not scores:
        return QuestionClassification(
            type=QuestionType.OTHER if not _looks_like_general_fact(normalized) else QuestionType.GENERAL_FACT,
            confidence=0.45 if _looks_like_general_fact(normalized) else 0.35,
            reason="No strong topical cues; using a broad search strategy.",
            freshness_required=freshness and not has_old_year,
        )

    best_type = max(scores.items(), key=lambda item: item[1])[0]
    best_score = scores[best_type]
    # Softmax-ish confidence from relative score.
    total = sum(scores.values()) or best_score
    confidence = min(0.97, max(0.5, best_score / (total + 0.5)))

    # Prefer CURRENT_EVENT when freshness is strong and topical type is newsy.
    # Note: for sports, "yesterday" or "today" signals a breaking event report,
    # whereas "latest cricket match" routes to sports federations (ICC / BCCI / leagues).
    is_newsy_fresh = (
        freshness
        and not has_old_year
        and (
            (
                best_type in {QuestionType.POLITICS, QuestionType.BUSINESS_FINANCE, QuestionType.GOVERNMENT_POLICY}
                and scores.get(QuestionType.CURRENT_EVENT, 0) >= best_score * 0.8
                and ("latest" in normalized or "yesterday" in normalized or "today" in normalized)
            )
            or (
                best_type is QuestionType.SPORTS
                and scores.get(QuestionType.CURRENT_EVENT, 0) >= best_score * 0.8
                and ("yesterday" in normalized or "today" in normalized)
            )
        )
    )
    if is_newsy_fresh:
        best_type = QuestionType.CURRENT_EVENT
        matched[best_type] = matched.get(best_type, "recency cue")

    freshness_required = bool(
        best_type is QuestionType.CURRENT_EVENT
        or (freshness and not has_old_year and best_type in {
            QuestionType.POLITICS,
            QuestionType.SPORTS,
            QuestionType.BUSINESS_FINANCE,
            QuestionType.GOVERNMENT_POLICY,
        })
    )

    cue = matched.get(best_type, "topical cues")
    reason = f"Matched question cues for {QUESTION_TYPE_LABELS[best_type].lower()} ({cue})."
    return QuestionClassification(
        type=best_type,
        confidence=round(confidence, 3),
        reason=reason,
        freshness_required=freshness_required,
    )


def _looks_like_general_fact(normalized: str) -> bool:
    starters = (
        "what is",
        "who is",
        "who was",
        "where is",
        "when was",
        "when did",
        "which",
        "who formulated",
        "who proposed",
        "who created",
    )
    return any(normalized.startswith(s) for s in starters) or "capital of" in normalized
