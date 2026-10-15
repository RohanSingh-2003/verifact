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
        "he", "she", "they", "them", "him", "his", "her", "hers", "their", "theirs",
        "my", "mine", "your", "yours", "our", "ours", "who", "whom", "whose", "which",
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
    raw_mw = re.findall(
        r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", clean_claim
    )
    multi_word_anchors: list[str] = []
    # Individual capitalized words (excluding first word if followed by lowercase unless recognized entity)
    words = clean_claim.split()
    single_anchors: list[str] = []
    for m in raw_mw:
        parts = m.split()
        while parts and parts[0].casefold() in _STOP_WORDS:
            parts.pop(0)
        if len(parts) >= 2:
            multi_word_anchors.append(" ".join(parts))
        elif parts:
            single_anchors.append(parts[0])

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


def _concept_in_text(concept: str, text: str) -> bool:
    c = concept.casefold()
    if c in text:
        return True
    if len(c) >= 5:
        stem = re.sub(r"(?:ies|ing|ed|ers?|ations?|ions?|s|y)$", "", c)
        if len(stem) >= 4 and stem in text:
            return True
        if c[:-1] in text or (len(c) >= 6 and c[:-2] in text):
            return True
    return False


def get_source_quality_rationale(domain: str, source_type: str | None = None) -> str:
    """Return an authoritative human-readable description of source quality tier."""
    clean_domain = (domain or "").strip().lower()
    raw_type = str(source_type or "").upper()

    if "GOVERNMENT" in raw_type or any(clean_domain.endswith(sfx) for sfx in (".gov", ".gov.in", ".gov.uk", ".gov.au", ".nic.in", ".europa.eu", ".mil", ".go.jp")):
        return "Primary official government portal / public regulatory document"
    if "ACADEMIC" in raw_type or any(clean_domain.endswith(sfx) for sfx in (".edu", ".ac.in", ".ac.uk", "nature.com", "science.org", "arxiv.org", "nih.gov", "cdc.gov", "who.int", "ncbi.nlm.nih.gov")):
        return "Primary research / peer-reviewed academic or health institution"
    if clean_domain in {"britannica.com", "archives.gov", "nationalarchives.gov.uk", "loc.gov", "si.edu"} or "REFERENCE" in raw_type:
        return "Authoritative reference work / archival institution"
    if "NEWS" in raw_type or clean_domain in {"reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "npr.org"}:
        return "Reputable journalistic news organization"
    if "FACT_CHECK" in raw_type:
        return "Certified independent fact-checking organization"
    if "LOW_PRIORITY" in raw_type:
        return "Low priority aggregator / user forum / commercial blog"
    return "General web source"


def evaluate_source_relevance(
    claim_text: str,
    source: WebSource,
    min_threshold: float = 0.20,
    detected_countries: list[CountryAuthority] | None = None,
) -> tuple[bool, float, str, str]:
    """Evaluate source relevance according to the strict relevance acceptance policy.

    Relevance Criteria:
    1. Entity Identity Check: Source must discuss the target entity in the claim.
       Reject if source discusses a different entity or omits the target entity entirely.
    2. Different Fact Check: If the entity is mentioned, source must address the specific
       proposition/predicate asserted, not merely a different fact about the entity.
    3. Temporal / Date Scope Check: If the claim specifies a date or time period as a core
       proposition, reject sources that discuss conflicting dates or different timeframes.
    4. Geographic / Jurisdiction Check: Reject unrelated foreign jurisdictions that do not
       cover the geographic scope of the claim.
    5. Textual Adequacy: Reject pages with empty or insufficient textual evidence.

    Returns: (is_relevant, score, relevance_rationale, quality_rationale)
    """
    quality_rationale = get_source_quality_rationale(source.domain, source.source_type)
    clean_snippet = clean_raw_snippet(source.snippet or "")
    clean_title = clean_raw_snippet(source.title or "")
    raw_content = clean_raw_snippet(getattr(source, "extracted_passage", "") or "")
    combined = f"{clean_title} {clean_snippet} {raw_content}".casefold()

    if not combined.strip():
        return False, 0.0, "Source has no textual content to assess", quality_rationale

    words = _WORD_RE.findall(combined)
    if len(words) < 5:
        return False, 0.05, "Source snippet is too brief to substantiate claim", quality_rationale

    anchors, concepts = extract_claim_anchors_and_concepts(claim_text)
    clean_claim = " ".join(claim_text.split()).strip()
    claim_tokens = _WORD_RE.findall(clean_claim)
    claim_years = [t for t in claim_tokens if re.match(r"^\d{3,4}$", t)]

    # 1. Entity Identity Check
    if anchors:
        matched_anchors = [a for a in anchors if a.casefold() in combined]
        if not matched_anchors:
            return False, 0.05, f"Entity mismatch: target entity '{anchors[0]}' not found in source text", quality_rationale

    # 2. Proposition & Concept Check (Different Fact Check)
    anchor_tokens = {tok.casefold() for a in anchors for tok in _WORD_RE.findall(a)}
    predicate_concepts = [c for c in concepts if c not in anchor_tokens]
    matched_predicate_concepts = [c for c in predicate_concepts if _concept_in_text(c, combined)]
    matched_concepts = [c for c in concepts if _concept_in_text(c, combined)]
    matched_years = [y for y in claim_years if y in combined]

    if anchors and predicate_concepts:
        if not matched_predicate_concepts and not matched_years and len(predicate_concepts) >= 2:
            return False, 0.10, "Target entity mentioned but discusses a different fact or topic", quality_rationale
    else:
        if not matched_concepts and not matched_years:
            return False, 0.10, "Source does not address claim proposition", quality_rationale

    total_props = len(concepts) + len(claim_years)
    matched_props = len(matched_concepts) + len(matched_years)
    concept_ratio = matched_props / max(1, total_props) if total_props else 0.5

    # 3. Temporal / Date Check
    if claim_years:
        claim_year = claim_years[0]
        # If text explicitly discusses the entity with a conflicting 4-digit year for the event
        found_years = set(re.findall(r"\b(1\d{3}|20\d{2})\b", combined))
        if found_years and claim_year not in found_years and (concept_ratio < 0.60 or len(found_years) <= 2):
            return False, 0.10, f"Date mismatch: source discusses year {', '.join(sorted(found_years))} rather than {claim_year}", quality_rationale

    # 4. Jurisdiction & Foreign Institutional Mismatch Check
    if detected_countries:
        claim_country_codes = {c.country_code for c in detected_countries}
        source_domain = (source.domain or "").lower()
        is_foreign_gov = False
        foreign_unrelated_terms = False

        if "JP" in claim_country_codes:
            if any(source_domain.endswith(sfx) for sfx in (".gov.au", ".gov.in", ".gov.uk", ".gc.ca", ".fed.us")):
                is_foreign_gov = True
            if any(term in combined for term in ("trade delegation", "trade mission", "export", "bilateral investment", "beef", "coal")):
                foreign_unrelated_terms = True
        elif "AU" in claim_country_codes:
            if any(source_domain.endswith(sfx) for sfx in (".gov.in", ".gov.uk", ".gc.ca", ".go.jp")):
                is_foreign_gov = True
        elif "IN" in claim_country_codes:
            if any(source_domain.endswith(sfx) for sfx in (".gov.au", ".gov.uk", ".gc.ca", ".go.jp")):
                is_foreign_gov = True

        if is_foreign_gov and (foreign_unrelated_terms or concept_ratio < 0.35):
            return False, 0.05, "Geographic / jurisdictional mismatch: foreign government source addressing unrelated topic", quality_rationale

    # 5. Composite Relevance Score
    anchor_ratio = len([a for a in anchors if a.casefold() in combined]) / max(1, len(anchors)) if anchors else 1.0
    computed_score = round((concept_ratio * 0.6) + (anchor_ratio * 0.4), 3)

    if computed_score < min_threshold:
        return False, computed_score, f"Relevance score ({computed_score:.2f}) below threshold ({min_threshold:.2f}); insufficient topical overlap", quality_rationale

    return True, computed_score, f"Source directly discusses target entity and proposition (relevance={computed_score:.2f})", quality_rationale


def compute_topical_relevance(
    claim_text: str,
    source: WebSource,
    detected_countries: list[CountryAuthority] | None = None,
) -> float:
    """Compute topical relevance score (0.0 to 1.0) of a WebSource to claim_text."""
    _is_rel, score, _rationale, _qual = evaluate_source_relevance(
        claim_text, source, min_threshold=0.20, detected_countries=detected_countries
    )
    return score


def is_source_topically_relevant(
    claim_text: str,
    source: WebSource,
    min_threshold: float = 0.20,
    detected_countries: list[CountryAuthority] | None = None,
) -> bool:
    """Return True if source meets minimum topical relevance to the claim."""
    is_rel, _score, _rationale, _qual = evaluate_source_relevance(
        claim_text, source, min_threshold=min_threshold, detected_countries=detected_countries
    )
    return is_rel


def filter_topically_relevant_sources(
    claim_text: str,
    sources: list[WebSource],
    min_threshold: float = 0.20,
    detected_countries: list[CountryAuthority] | None = None,
) -> list[WebSource]:
    """Filter out sources that are off-topic or fail the strict relevance acceptance policy."""
    import dataclasses

    relevant: list[WebSource] = []
    for s in sources:
        is_rel, score, rel_rationale, qual_rationale = evaluate_source_relevance(
            claim_text, s, min_threshold=min_threshold, detected_countries=detected_countries
        )
        if is_rel:
            extracted_passage = getattr(s, "extracted_passage", None) or s.snippet[:1500]
            relevant.append(
                dataclasses.replace(
                    s,
                    relevance_score=score,
                    relevance_rationale=rel_rationale,
                    quality_rationale=qual_rationale,
                    extracted_passage=extracted_passage,
                )
            )
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

    is_rel, relevance, _rel_rat, _qual_rat = evaluate_source_relevance(
        claim_text, source, min_threshold=0.20, detected_countries=detected_countries
    )
    if not is_rel or relevance < 0.20:
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
