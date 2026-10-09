"""Topical relevance evaluation, relevance filtering, and compound-claim coverage.

Ensures that search results are evaluated for true topical relevance to the specific
claim before being passed to the verifier. An official government domain from an unrelated
jurisdiction or topic does not make an irrelevant page acceptable evidence.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.web_evidence.authority import CountryAuthority
from app.web_evidence.evidence_extractor import clean_raw_snippet
from app.web_search.base import WebSource

# Stopwords dropped when extracting claim concept tokens
_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with",
        "by", "about", "against", "between", "into", "through", "during", "before",
        "after", "above", "below", "from", "up", "down", "out", "off", "over",
        "under", "again", "further", "then", "once", "here", "there", "when", "where",
        "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than",
        "too", "very", "can", "will", "just", "should", "now", "is", "was", "are",
        "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "that", "this", "these", "those", "it", "its", "as", "of", "also", "serves",
        "served", "serve", "located", "location", "country", "state", "city",
    }
)

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[a-z]+)?")


def extract_claim_anchors_and_concepts(claim_text: str) -> tuple[list[str], list[str]]:
    """Extract primary subject anchors and core conceptual terms from a claim.

    Primary anchors: capitalized proper nouns/entities (e.g. 'Tokyo', 'Imperial Palace', 'Japan').
    Conceptual terms: significant verbs, nouns, adjectives (e.g. 'seat', 'government', 'economic', 'cultural', 'hub').
    """
    clean_claim = " ".join(claim_text.split()).strip()

    # Identify multi-word proper nouns like "Imperial Palace", "New South Wales"
    multi_word_anchors = re.findall(
        r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", clean_claim
    )

    # Individual capitalized words (excluding first word if followed by lowercase unless recognized entity)
    words = clean_claim.split()
    single_anchors: list[str] = []
    for i, w in enumerate(words):
        stripped = re.sub(r"[^\w]", "", w)
        if not stripped:
            continue
        if stripped[0].isupper() and (i > 0 or len(stripped) > 3):
            lower = stripped.casefold()
            if lower not in _STOP_WORDS and lower not in [a.casefold() for a in single_anchors]:
                single_anchors.append(stripped)

    anchors = list(multi_word_anchors)
    for sa in single_anchors:
        if not any(sa.casefold() in mwa.casefold() for mwa in multi_word_anchors):
            anchors.append(sa)

    # Core concept words
    all_tokens = _WORD_RE.findall(clean_claim)
    concepts = [
        t.casefold()
        for t in all_tokens
        if len(t) > 2 and t.casefold() not in _STOP_WORDS and not t.isdigit()
    ]

    return anchors, concepts


def extract_claim_components(claim_text: str) -> list[str]:
    """Decompose compound claims into distinct factual components.

    E.g. "Tokyo serves as the seat of the Japanese government, the Imperial Palace,
          and the primary economic and cultural hub of the country."
    Decomposes into:
    1. Seat of the Japanese government
    2. Imperial Palace
    3. Primary economic and cultural hub
    """
    cleaned = " ".join(claim_text.split()).strip().rstrip(".!?")
    if not cleaned:
        return []

    # Check for serial commas or coordinate conjunctions
    if "," in cleaned:
        # Split on commas (including Oxford comma before 'and')
        comma_splits = [p.strip() for p in re.split(r",\s*(?:and\s+)?", cleaned) if p.strip()]
        if len(comma_splits) >= 2:
            return comma_splits
    elif " and " in cleaned:
        # Two-part assertion joined by 'and' without comma
        parts = [p.strip() for p in re.split(r"\s+and\s+", cleaned) if p.strip()]
        if len(parts) >= 2:
            return parts

    return [cleaned]


def compute_topical_relevance(
    claim_text: str,
    source: WebSource,
    detected_countries: list[CountryAuthority] | None = None,
) -> float:
    """Compute topical relevance score (0.0 to 1.0) of a WebSource to claim_text.

    Penalizes unrelated foreign domestic government sources (e.g. Queensland parliament
    for a claim about Tokyo/Japan) and sources that lack the primary claim subject anchors.
    """
    clean_snippet = clean_raw_snippet(source.snippet or "")
    clean_title = clean_raw_snippet(source.title or "")
    combined = f"{clean_title} {clean_snippet}".casefold()

    if not combined.strip():
        return 0.0

    anchors, concepts = extract_claim_anchors_and_concepts(claim_text)
    if not concepts and not anchors:
        return 0.5  # Neutral fallback for empty extracted concepts

    # 1. Primary Subject Anchor Check
    # If the claim has a primary named entity subject (e.g. Tokyo), verify presence
    has_primary_anchor = False
    if anchors:
        primary = anchors[0].casefold()
        has_primary_anchor = primary in combined
        if not has_primary_anchor and len(anchors) > 1:
            has_primary_anchor = any(a.casefold() in combined for a in anchors)
    else:
        has_primary_anchor = True

    # Critical anchor penalty: if the primary subject entity is completely missing,
    # the source cannot be sufficient evidence for this claim.
    if anchors and not has_primary_anchor:
        return 0.05

    # 2. Informative Concept Overlap
    matched_concepts = sum(1 for c in concepts if c in combined)
    concept_ratio = matched_concepts / max(1, len(concepts))

    # 3. Anchor Match Ratio
    anchor_ratio = 1.0
    if anchors:
        matched_anchors = sum(1 for a in anchors if a.casefold() in combined)
        anchor_ratio = matched_anchors / len(anchors)

    base_relevance = (concept_ratio * 0.6) + (anchor_ratio * 0.4)

    # 4. Jurisdiction & Foreign Institutional Mismatch Penalty
    # An official government domain from an unrelated jurisdiction must not be
    # accepted as evidence for a domestic geographic or constitutional claim.
    if detected_countries:
        claim_country_codes = {c.country_code for c in detected_countries}
        source_domain = (source.domain or "").lower()

        # Check if the source is from a foreign government domain
        is_foreign_gov = False
        foreign_unrelated_terms = False

        if "JP" in claim_country_codes:
            # Claim is specifically about Japan/Tokyo
            if any(source_domain.endswith(sfx) for sfx in (".gov.au", ".gov.in", ".gov.uk", ".gc.ca", ".fed.us")):
                is_foreign_gov = True
            # Foreign bilateral trade, tourism, or overseas parliamentary delegation mentions
            if any(term in combined for term in ("trade delegation", "trade mission", "export", "bilateral investment", "beef", "coal")):
                foreign_unrelated_terms = True

        elif "AU" in claim_country_codes:
            if any(source_domain.endswith(sfx) for sfx in (".gov.in", ".gov.uk", ".gc.ca", ".go.jp")):
                is_foreign_gov = True

        elif "IN" in claim_country_codes:
            if any(source_domain.endswith(sfx) for sfx in (".gov.au", ".gov.uk", ".gc.ca", ".go.jp")):
                is_foreign_gov = True

        if is_foreign_gov:
            # Foreign government source discussing trade/overseas affairs
            # rather than domestic constitutional geography
            if foreign_unrelated_terms or base_relevance < 0.40:
                return 0.05

    return min(1.0, max(0.0, base_relevance))


def is_source_topically_relevant(
    claim_text: str,
    source: WebSource,
    min_threshold: float = 0.20,
    detected_countries: list[CountryAuthority] | None = None,
) -> bool:
    """Return True if source meets minimum topical relevance to the claim."""
    return compute_topical_relevance(claim_text, source, detected_countries=detected_countries) >= min_threshold


def filter_topically_relevant_sources(
    claim_text: str,
    sources: list[WebSource],
    min_threshold: float = 0.20,
    detected_countries: list[CountryAuthority] | None = None,
) -> list[WebSource]:
    """Filter out sources that are off-topic or irrelevant to the claim."""
    import dataclasses

    relevant: list[WebSource] = []
    for s in sources:
        score = compute_topical_relevance(claim_text, s, detected_countries=detected_countries)
        if score >= min_threshold:
            if s.relevance_score is None or score > s.relevance_score:
                relevant.append(dataclasses.replace(s, relevance_score=round(score, 3)))
            else:
                relevant.append(s)
    return relevant


def compute_source_priority(
    claim_text: str,
    source: WebSource,
    detected_countries: list[CountryAuthority] | None = None,
) -> float:
    """Composite ranking score combining authority tier and topical relevance.

    Prefer relevant official government sources (e.g. Tokyo Metropolitan Government),
    then credible reference/secondary sources that directly address the claim.
    Irrelevant sources receive a priority score of 0.0.
    """
    from app.web_evidence.source_quality import source_tier_rank

    relevance = compute_topical_relevance(claim_text, source, detected_countries=detected_countries)
    if relevance < 0.20:
        return 0.0

    # Tier rank: 1 (Primary/Gov) -> 6 (Low priority)
    tier = source_tier_rank(source.source_type)
    tier_weight = max(0.1, 1.1 - (tier * 0.15))

    # Bonus for country authority alignment
    jurisdiction_bonus = 0.0
    if detected_countries:
        domain = (source.domain or "").lower()
        for ca in detected_countries:
            if any(domain == pd or domain.endswith("." + pd) for pd in ca.primary_domains):
                jurisdiction_bonus = 0.15
                break

    return round((relevance * 0.65) + (tier_weight * 0.25) + jurisdiction_bonus, 3)


def evaluate_compound_components_coverage(
    claim_text: str,
    sources: list[WebSource],
) -> tuple[bool, list[str], list[str]]:
    """Evaluate whether retrieved sources cover all factual components of a compound claim.

    Returns: (is_fully_covered, supported_components, missing_components)
    """
    components = extract_claim_components(claim_text)
    if len(components) <= 1:
        # Single assertion claim: check overall relevance
        clean_text = " ".join(f"{s.title} {s.snippet}" for s in sources).casefold()
        _anchors, concepts = extract_claim_anchors_and_concepts(claim_text)
        has_min_concepts = sum(1 for c in concepts if c in clean_text) >= max(1, len(concepts) // 2)
        if has_min_concepts:
            return True, [claim_text], []
        return False, [], [claim_text]

    combined_evidence = " ".join(f"{s.title} {s.snippet}" for s in sources).casefold()

    supported: list[str] = []
    missing: list[str] = []

    for comp in components:
        anchors, concepts = extract_claim_anchors_and_concepts(comp)

        # Check anchors if any multi-word or distinct proper nouns exist in component
        if anchors and any(len(a.split()) > 1 or a.isupper() for a in anchors):
            anchor_match = any(a.casefold() in combined_evidence for a in anchors)
            if anchor_match:
                supported.append(comp)
                continue

        substantive = [c for c in concepts if not any(c == a.casefold() for a in anchors)] or concepts
        if not substantive:
            supported.append(comp)
            continue

        # Check substantive concept presence in evidence
        matches = sum(1 for c in substantive if c in combined_evidence)
        if matches >= max(1, int(len(substantive) * 0.5)):
            supported.append(comp)
        else:
            missing.append(comp)

    is_fully_covered = (len(missing) == 0 and len(supported) > 0)
    return is_fully_covered, supported, missing
