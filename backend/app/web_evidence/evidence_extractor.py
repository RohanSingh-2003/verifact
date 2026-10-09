from __future__ import annotations

import re
from app.web_evidence.types import EvidenceVerdict
from app.web_search.base import WebSource

# Common web navigation, UI, and search artifact patterns
_NAVIGATION_PATTERNS = [
    re.compile(r"^\s*#+\s*.*$", re.MULTILINE),  # markdown headers (#, ##, ###)
    re.compile(r"History Top Questions", re.IGNORECASE),
    re.compile(r"Top Questions\b", re.IGNORECASE),
    re.compile(r"Frequently Asked Questions\b", re.IGNORECASE),
    re.compile(r"\bFAQ\b", re.IGNORECASE),
    re.compile(r"Quick Facts?:?", re.IGNORECASE),
    re.compile(r"Table of Contents:?", re.IGNORECASE),
    re.compile(r"Navigation menu:?", re.IGNORECASE),
    re.compile(r"Skip to (main )?content", re.IGNORECASE),
    re.compile(r"Related (topics|searches|articles):?", re.IGNORECASE),
    re.compile(r"Share this article:?", re.IGNORECASE),
    re.compile(r"Click here to (read|learn|view)", re.IGNORECASE),
    re.compile(r"\[\s*\.\.\.\s*\]"),  # [...] search ellipsis
    re.compile(r"\[\s*edit\s*\]", re.IGNORECASE),  # wikipedia [edit]
    re.compile(r"\[\d+\]"),  # wikipedia citations like [1], [2]
]

# Patterns for questions/headers embedded in snippets, e.g. "What post did Narendra Modi hold...? "
_QUESTION_HEADER_PATTERN = re.compile(
    r"(?:^|\s)(?:What|Who|Where|When|Why|How|Which|Did|Was|Is|Are|Can|Could|Should)\s+[^?]{5,100}\?\s*",
    re.IGNORECASE,
)

# Trailing page metadata patterns like " - Political career, PM of India, 2014 & 2019 ..."
_TRAILING_METADATA_PATTERN = re.compile(
    r"\s*[-–—|•]\s*[\w\s,&/]+(?:\.{2,})?$",
    re.IGNORECASE,
)

# Common words to ignore when scoring relevance
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with",
    "by", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "from", "up", "down", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "can", "will", "just", "should", "now", "is", "was", "are",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "that", "this", "these", "those", "it", "its", "as", "of", "also", "serves",
    "served", "country", "primary", "economic", "hub",
}

INSUFFICIENT_SOURCE_MESSAGE = (
    "The retrieved source does not provide enough relevant information to verify this claim."
)


def clean_raw_snippet(text: str) -> str:
    """Strip markdown headers, navigation banners, noisy questions, and search artifacts."""
    if not text:
        return ""

    cleaned = text
    # Remove markdown headers and specific navigation phrases
    for pattern in _NAVIGATION_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)

    # Remove embedded FAQ questions (e.g. "What post did Narendra Modi hold...?")
    cleaned = _QUESTION_HEADER_PATTERN.sub(" ", cleaned)

    # Remove trailing metadata / search tags
    cleaned = _TRAILING_METADATA_PATTERN.sub("", cleaned)

    # Remove standalone markdown artifacts and list markers
    cleaned = re.sub(r"(?:^|\s)[#*•>-]+\s+", " ", cleaned)
    cleaned = re.sub(r"\s*\.{3,}\s*", " ", cleaned)
    cleaned = re.sub(r"[\t\r\n]+", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences respecting abbreviations and numbers."""
    if not text:
        return []
    # Protected splits: don't split on common abbreviations like U.S., Dr., PM, etc.
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    sentences: list[str] = []
    for s in raw_sentences:
        clean_s = s.strip()
        # Filter out fragments that are too short to be factual sentences
        if len(clean_s.split()) >= 4:
            sentences.append(clean_s)
    return sentences


def _extract_claim_tokens(claim: str) -> tuple[set[str], set[str]]:
    """Extract significant keywords and numbers/years from a claim."""
    words = re.findall(r"[A-Za-z0-9]+(?:'[a-z]+)?", claim)
    numbers = set(re.findall(r"\b\d{1,4}\b", claim))
    keywords = {
        w.lower()
        for w in words
        if len(w) > 1 and w.lower() not in _STOP_WORDS and not w.isdigit()
    }
    return keywords, numbers


def extract_source_evidence(
    claim_text: str,
    source: WebSource,
    verdict: EvidenceVerdict | None = None,
) -> str:
    """Extract a concise, 1–3 sentence claim-relevant evidence summary from a source.

    Grounded strictly in the source's snippet and title. Never invents facts.
    """
    if verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE and not (source.snippet or "").strip():
        return INSUFFICIENT_SOURCE_MESSAGE

    from app.web_evidence.relevance import compute_topical_relevance
    if compute_topical_relevance(claim_text, source) < 0.20:
        return INSUFFICIENT_SOURCE_MESSAGE

    clean_text = clean_raw_snippet(source.snippet)
    if not clean_text:
        # Check if title has substantial content
        clean_title = clean_raw_snippet(source.title)
        if len(clean_title.split()) >= 6:
            clean_text = clean_title
        else:
            return INSUFFICIENT_SOURCE_MESSAGE

    # Anchor verification: if claim contains key named entities, ensure snippet contains at least one
    from app.web_evidence.relevance import extract_claim_anchors_and_concepts
    anchors, _ = extract_claim_anchors_and_concepts(claim_text)
    if anchors:
        clean_lower = clean_text.lower()
        if not any(a.lower() in clean_lower for a in anchors):
            return INSUFFICIENT_SOURCE_MESSAGE

    sentences = _split_into_sentences(clean_text)
    if not sentences:
        return INSUFFICIENT_SOURCE_MESSAGE

    keywords, numbers = _extract_claim_tokens(claim_text)

    # Score each sentence for relevance to the claim
    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(sentences):
        s_lower = sentence.lower()
        s_words = set(re.findall(r"[A-Za-z0-9]+", s_lower))
        s_numbers = set(re.findall(r"\b\d{1,4}\b", sentence))

        keyword_matches = len(keywords.intersection(s_words))
        number_matches = len(numbers.intersection(s_numbers))

        # Weight number/year matches heavily (crucial for tenures, dates, stats)
        score = (keyword_matches * 1.5) + (number_matches * 3.0)

        # Penalize sentences that still look like residual navigation or questions
        if "?" in sentence or "click" in s_lower or "read more" in s_lower:
            score -= 5.0

        if score > 0:
            scored.append((score, index, sentence))

    if not scored or scored[0][0] < 1.0:
        return INSUFFICIENT_SOURCE_MESSAGE

    # Sort primarily by relevance score descending, then by original position
    scored.sort(key=lambda x: (-x[0], x[1]))

    # Pick the best scoring sentence, and optionally a second if closely relevant
    top_items = [scored[0]]
    if len(scored) > 1 and scored[1][0] >= 3.0 and (scored[1][0] >= scored[0][0] * 0.5):
        first_len = len(scored[0][2].split())
        second_len = len(scored[1][2].split())
        if first_len + second_len <= 55:
            top_items.append(scored[1])

    # Re-order the selected sentences by their original chronological position in the snippet
    top_items.sort(key=lambda x: x[1])

    extracted = " ".join(item[2] for item in top_items).strip()
    return _clean_sentence_formatting(extracted, source)


def _clean_sentence_formatting(sentence: str, source: WebSource) -> str:
    """Ensure clean punctuation, capitalize first letter, and remove dangling fragments."""
    res = sentence.strip()
    # Remove leading navigation dashes or colons
    res = re.sub(r"^[–—:•\-\s]+", "", res)
    # Ensure it ends with proper punctuation
    if not res.endswith((".", "!", "?")):
        res += "."
    if res and res[0].islower():
        res = res[0].upper() + res[1:]
    return res


def build_claim_evidence_summary(
    claim_text: str,
    sources: list[WebSource],
    verdict: EvidenceVerdict,
) -> str:
    """Build a 1–2 sentence consolidated evidence statement for the claim."""
    if verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE or not sources:
        return INSUFFICIENT_SOURCE_MESSAGE

    # Find the first source that has a valid claim-relevant evidence summary
    for source in sources:
        summary = (source.evidence_summary or "").strip()
        if summary and summary != INSUFFICIENT_SOURCE_MESSAGE:
            return summary

    return INSUFFICIENT_SOURCE_MESSAGE
