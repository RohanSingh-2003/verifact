from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.llm.base import LLMClient, LLMError
from app.web_evidence.types import ExtractedClaim

logger = logging.getLogger("verifact.web_evidence.claims")

WEB_CLAIM_SYSTEM = """You extract factual claims from an AI answer for external evidence verification.
You must not invent facts that are not supported by the answer.
You must not use tools, retrieval, browsing, or outside knowledge beyond the answer text.
Return JSON only."""

WEB_CLAIM_USER = """Question:
{question}

Answer:
{answer}

Extract up to {max_claims} important factual claims from the answer.

Rules:
- Each claim must be one short, self-contained factual sentence.
- Claims must be independently verifiable on the open web when possible.
- Prefer atomic claims (one fact each): entities, dates, places, events, quantities.
- Preserve qualifiers (some, approximately, reported, may).
- Do not invent outside knowledge.
- Do NOT extract greetings, thanks, or conversational filler.
- Do NOT extract vague conclusions with no checkable fact.
- Do NOT extract pure opinions, preferences, or subjective judgments.
- Do NOT extract duplicate or near-duplicate claims.
- If the answer has no verifiable factual claims, return {{"claims": []}}.

Return JSON only:
{{
  "claims": [
    {{"id": "claim_1", "text": "short factual sentence"}}
  ]
}}"""

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
_OPINION_RE = re.compile(
    r"\b("
    r"i think|i believe|in my opinion|it seems|seems like|probably|maybe|perhaps|"
    r"i feel|personally|prefer|should|ought|beautiful|wonderful|amazing|terrible|"
    r"best ever|worst|love this|hate this"
    r")\b",
    re.IGNORECASE,
)
_GREETING_RE = re.compile(
    r"^(hi|hello|hey|thanks|thank you|good (morning|afternoon|evening)|sure|of course)\b",
    re.IGNORECASE,
)
_VAGUE_RE = re.compile(
    r"^(it is important|this is interesting|as we (all )?know|in conclusion|"
    r"overall|to summarize|in summary|needless to say)\b",
    re.IGNORECASE,
)


class _ClaimItem(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator("id", "text")
    @classmethod
    def strip_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("empty")
        return cleaned


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def normalize_claim_key(text: str) -> str:
    """Normalize claim text for exact duplicate detection."""
    lowered = text.casefold().strip()
    lowered = _NON_ALNUM_RE.sub(" ", lowered)
    return " ".join(lowered.split())


def _word_set(text: str) -> set[str]:
    return {token for token in _WORD_RE.findall(text.casefold()) if len(token) > 1}


def is_near_duplicate(candidate: str, existing: list[str], *, threshold: float = 0.85) -> bool:
    """True when candidate overlaps an existing claim too strongly (Jaccard)."""
    cand_words = _word_set(candidate)
    if not cand_words:
        return False
    for prior in existing:
        prior_words = _word_set(prior)
        if not prior_words:
            continue
        union = cand_words | prior_words
        if not union:
            continue
        jaccard = len(cand_words & prior_words) / len(union)
        if jaccard >= threshold:
            return True
        # Also catch near-subset duplicates ("X discovered Y" vs "X discovered Y in 1928").
        smaller, larger = (
            (cand_words, prior_words)
            if len(cand_words) <= len(prior_words)
            else (prior_words, cand_words)
        )
        if smaller and len(smaller & larger) / len(smaller) >= 0.9 and abs(len(cand_words) - len(prior_words)) <= 3:
            return True
    return False


def is_non_factual_claim(text: str) -> bool:
    """Filter greetings, vague filler, and clearly subjective statements."""
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return True
    if _GREETING_RE.search(cleaned):
        return True
    if _VAGUE_RE.search(cleaned):
        return True
    if _OPINION_RE.search(cleaned):
        return True
    # Pure rhetorical questions are not claims.
    if cleaned.endswith("?") and _word_count(cleaned) < 12:
        return True
    return False


def collect_web_claims(raw_items: object, *, max_claims: int) -> list[ExtractedClaim]:
    if not isinstance(raw_items, list):
        raise ValueError("Claim payload must contain a list named claims.")
    valid: list[ExtractedClaim] = []
    seen_keys: set[str] = set()
    kept_texts: list[str] = []
    for index, item in enumerate(raw_items):
        try:
            if isinstance(item, str):
                parsed = _ClaimItem(id=f"claim_{index + 1}", text=item)
            elif isinstance(item, dict):
                parsed = _ClaimItem.model_validate(
                    {
                        "id": item.get("id") or f"claim_{index + 1}",
                        "text": item.get("text") or item.get("claim") or "",
                    }
                )
            else:
                continue
        except ValidationError:
            continue
        text = parsed.text
        if text[-1] not in ".!?":
            text = f"{text}."
        if _word_count(text) < 3 or _word_count(text) > 40:
            continue
        if is_non_factual_claim(text):
            continue
        key = normalize_claim_key(text)
        if not key or key in seen_keys:
            continue
        if is_near_duplicate(text, kept_texts):
            continue
        seen_keys.add(key)
        kept_texts.append(text)
        valid.append(ExtractedClaim(id=f"claim_{len(valid) + 1}", text=text))
        if len(valid) >= max_claims:
            break
    return valid


def fallback_web_claims(answer: str, *, max_claims: int) -> list[ExtractedClaim]:
    cleaned = " ".join(answer.split()).strip()
    if not cleaned:
        return []
    parts = _SENTENCE_SPLIT_RE.split(cleaned)
    claims: list[ExtractedClaim] = []
    seen_keys: set[str] = set()
    kept_texts: list[str] = []
    for part in parts:
        text = part.strip()
        if not text:
            continue
        if text[-1] not in ".!?":
            text = f"{text}."
        if _word_count(text) < 3 or _word_count(text) > 40:
            continue
        if is_non_factual_claim(text):
            continue
        key = normalize_claim_key(text)
        if not key or key in seen_keys:
            continue
        if is_near_duplicate(text, kept_texts):
            continue
        seen_keys.add(key)
        kept_texts.append(text)
        claims.append(ExtractedClaim(id=f"claim_{len(claims) + 1}", text=text))
        if len(claims) >= max_claims:
            break
    return claims


async def extract_web_claims(
    llm: LLMClient,
    *,
    model: str,
    question: str,
    answer: str,
    max_claims: int,
    max_tokens: int | None = None,
) -> list[ExtractedClaim]:
    effective_max = min(max_claims, 3)
    clean_answer = " ".join(answer.split()).strip()
    word_cnt = _word_count(clean_answer)

    # For concise answers (1-2 short sentences, <= 35 words), extract claims directly
    # without waiting for a heavy 26B LLM call when no opinion/filler markers are present.
    if word_cnt <= 35 and not _OPINION_RE.search(clean_answer) and not _GREETING_RE.search(clean_answer):
        quick_claims = fallback_web_claims(clean_answer, max_claims=effective_max)
        if quick_claims and len(quick_claims) <= 2:
            logger.info("web claims extracted via fast factual parsing count=%s", len(quick_claims))
            return quick_claims

    user_prompt = WEB_CLAIM_USER.format(
        question=question,
        answer=answer,
        max_claims=effective_max,
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            payload = await llm.complete_json(
                model=model,
                system_prompt=WEB_CLAIM_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
            )
            claims = collect_web_claims(
                payload.get("claims") if isinstance(payload, dict) else None,
                max_claims=max_claims,
            )
            # Empty list is a valid outcome (answer has no verifiable facts).
            if isinstance(payload, dict) and isinstance(payload.get("claims"), list):
                logger.info("web claims extracted count=%s attempt=%s", len(claims), attempt + 1)
                return claims
            last_error = ValueError("Web claim extractor returned no valid claims.")
        except (ValidationError, ValueError, LLMError, AttributeError, TypeError) as exc:
            last_error = exc
            logger.warning("Web claim extraction attempt %s failed: %s", attempt + 1, exc)

    fallback = fallback_web_claims(answer, max_claims=max_claims)
    if fallback:
        logger.warning(
            "Using fallback web claims count=%s after extraction failure: %s",
            len(fallback),
            last_error,
        )
        return fallback
    # Still empty after fallback — treat as no verifiable claims, not a hard LLM crash.
    if last_error is None or isinstance(last_error, ValueError):
        return []
    raise LLMError("Web claim extractor did not return usable factual claims.") from last_error
