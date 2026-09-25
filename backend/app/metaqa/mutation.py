from __future__ import annotations

import hashlib
import logging
import re

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.llm.base import LLMClient, LLMError
from app.llm.prompts import (
    CLAIM_SYSTEM,
    CLAIM_USER,
    MUTATION_FILL_USER,
    MUTATION_SYSTEM,
    MUTATION_USER,
)
from app.metaqa.scoring import MutationType

logger = logging.getLogger("verifact.metaqa.mutation")

_MIN_MUTATION_WORDS = 5
_MAX_MUTATION_WORDS = 35
_MIN_CLAIM_WORDS = 4
_MAX_CLAIM_WORDS = 40
_DEFAULT_MAX_CLAIMS = 4
_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_FORBIDDEN_PREFIXES = (
    "synonym mutation:",
    "antonym mutation:",
    "synonym:",
    "antonym:",
    "here is the mutation:",
    "here is a mutation:",
    "mutation:",
    "this means that",
    "the mutation is",
    "expected verdict",
    "verdict:",
    "according to the answer",
    "the original answer",
    "based on claim",
)
_INTERROGATIVES = frozenset(
    {"who", "what", "when", "where", "why", "how", "is", "are", "do", "does", "did", "can", "could", "would", "should"}
)
_VERB_CUES = frozenset(
    {
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "can",
        "could",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "need",
        "needs",
        "seem",
        "seems",
        "appear",
        "appears",
        "remain",
        "remains",
        "contain",
        "contains",
        "include",
        "includes",
        "report",
        "reports",
        "reported",
        "show",
        "shows",
        "make",
        "makes",
        "cause",
        "causes",
        "exist",
        "exists",
        "lack",
        "lacks",
        "serve",
        "serves",
        "equals",
        "equal",
        "formulated",
        "wrote",
        "painted",
        "discovered",
        "occurs",
        "occur",
        "works",
        "work",
        "uses",
        "use",
        "converts",
        "convert",
        "blocks",
        "block",
        "support",
        "supports",
        "supported",
        "experience",
        "experiences",
        "experienced",
        "suffer",
        "suffers",
        "suffered",
        "face",
        "faces",
        "faced",
        "without",
        "not",
        "no",
        "never",
        "incorrect",
        "false",
        "wrong",
        "contrary",
        "opposite",
        "instead",
        "unlike",
        "became",
        "become",
        "becomes",
        "fell",
        "fall",
        "falls",
        "flew",
        "fly",
        "flies",
        "absorb",
        "absorbs",
        "absorbed",
        "holds",
        "hold",
        "held",
        "means",
        "mean",
        "meant",
        "indicates",
        "indicate",
        "indicated",
        "noted",
        "note",
        "notes",
        "concerning",
        "regarding",
        "possess",
        "possesses",
        "possessed",
        "designed",
        "announced",
        "transferred",
        "transfer",
        "transferred",
        "died",
        "die",
        "extinct",
    }
)
_RETRY_HINT = (
    "\n\nPrevious output included invalid mutations (phrases, fragments, overly long text, "
    "or incomplete sentences). Every mutated_text MUST be a complete grammatical sentence "
    "of about 10–30 words (max 35). original_text must exactly match one core claim. "
    "Never return noun/adjective phrases such as \"structural stability\"."
)


class CoreClaim(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator("id", "text")
    @classmethod
    def strip_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Claim fields cannot be empty.")
        return cleaned


class GeneratedMutation(BaseModel):
    type: MutationType
    original_text: str = Field(min_length=1)
    mutated_text: str = Field(min_length=1)

    @field_validator("original_text", "mutated_text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Mutation text cannot be empty.")
        return cleaned


class MutationBatch(BaseModel):
    mutations: list[GeneratedMutation]


def mutation_key(mutation: GeneratedMutation) -> tuple[str, str]:
    return mutation.type.value, mutation.mutated_text.casefold()


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def looks_like_complete_sentence(
    text: str,
    *,
    min_words: int = _MIN_MUTATION_WORDS,
    max_words: int | None = _MAX_MUTATION_WORDS,
) -> bool:
    """Heuristic gate: reject fragments/phrases; keep concise full sentences."""
    cleaned = text.strip().strip("\"'`")
    if not cleaned:
        return False
    lower = cleaned.casefold()
    if any(lower.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES):
        return False
    if "\n" in cleaned:
        return False
    words = _WORD_RE.findall(cleaned)
    if len(words) < min_words:
        return False
    if max_words is not None and len(words) > max_words:
        return False
    if cleaned.rstrip().endswith("?") and words[0].casefold() in _INTERROGATIVES:
        return False
    if cleaned.endswith(":") or cleaned.endswith("-"):
        return False
    lower_words = {word.casefold() for word in words}
    has_verb_cue = bool(lower_words & _VERB_CUES)
    has_inflected = any(
        len(word) > 4 and word.casefold().endswith(("ed", "ing", "es")) for word in words
    )
    if not has_verb_cue and not has_inflected:
        return False
    return True


def fallback_claims_from_answer(answer: str, max_claims: int = _DEFAULT_MAX_CLAIMS) -> list[CoreClaim]:
    """Deterministic sentence split when LLM claim extraction is unavailable."""
    cleaned = " ".join(answer.split()).strip()
    if not cleaned:
        return []
    parts = _SENTENCE_SPLIT_RE.split(cleaned)
    claims: list[CoreClaim] = []
    seen: set[str] = set()
    for part in parts:
        text = part.strip()
        if not text:
            continue
        if text[-1] not in ".!?":
            text = f"{text}."
        if not looks_like_complete_sentence(
            text,
            min_words=_MIN_CLAIM_WORDS,
            max_words=_MAX_CLAIM_WORDS,
        ):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        claims.append(CoreClaim(id=f"claim_{len(claims) + 1}", text=text))
        if len(claims) >= max_claims:
            break
    if not claims and cleaned:
        # Last resort: treat the whole answer (truncated) as one claim.
        short = cleaned
        words = _WORD_RE.findall(cleaned)
        if len(words) > _MAX_CLAIM_WORDS:
            short = " ".join(words[:_MAX_CLAIM_WORDS]) + "."
        if short[-1] not in ".!?":
            short = f"{short}."
        claims.append(CoreClaim(id="claim_1", text=short))
    return claims


def collect_valid_claims(raw_items: object, *, max_claims: int = _DEFAULT_MAX_CLAIMS) -> list[CoreClaim]:
    if not isinstance(raw_items, list):
        raise ValueError("Claim payload must contain a list named claims.")
    valid: list[CoreClaim] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items):
        try:
            if isinstance(item, str):
                claim = CoreClaim(id=f"claim_{index + 1}", text=item)
            elif isinstance(item, dict):
                claim = CoreClaim.model_validate(
                    {
                        "id": item.get("id") or f"claim_{index + 1}",
                        "text": item.get("text") or item.get("claim") or "",
                    }
                )
            else:
                continue
        except ValidationError:
            logger.warning("Rejected malformed claim at index %s.", index)
            continue
        if not looks_like_complete_sentence(
            claim.text,
            min_words=_MIN_CLAIM_WORDS,
            max_words=_MAX_CLAIM_WORDS,
        ):
            logger.warning("Rejected incomplete claim: %s", claim.text[:160])
            continue
        key = claim.text.casefold()
        if key in seen:
            continue
        seen.add(key)
        valid.append(CoreClaim(id=f"claim_{len(valid) + 1}", text=claim.text))
        if len(valid) >= max_claims:
            break
    return valid


def format_claims_block(claims: list[CoreClaim]) -> str:
    return "\n".join(f"{index}. {claim.text}" for index, claim in enumerate(claims, start=1))


def format_accepted_mutations_block(mutations: list[GeneratedMutation]) -> str:
    if not mutations:
        return "(none yet)"
    lines: list[str] = []
    for index, item in enumerate(mutations, start=1):
        lines.append(f"{index}. [{item.type.value}] {item.mutated_text}")
    return "\n".join(lines)


def merge_mutation_batch(
    *,
    kept_synonyms: list[GeneratedMutation],
    kept_antonyms: list[GeneratedMutation],
    incoming: list[GeneratedMutation],
    synonym_count: int,
    antonym_count: int,
    seen: set[tuple[str, str]],
) -> None:
    """Accumulate valid mutations without regenerating already-kept items."""
    for mutation in incoming:
        key = mutation_key(mutation)
        if key in seen:
            continue
        if mutation.type is MutationType.SYNONYM and len(kept_synonyms) < synonym_count:
            kept_synonyms.append(mutation)
            seen.add(key)
        elif mutation.type is MutationType.ANTONYM and len(kept_antonyms) < antonym_count:
            kept_antonyms.append(mutation)
            seen.add(key)


async def extract_core_claims(
    llm: LLMClient,
    *,
    model: str,
    question: str,
    answer: str,
    max_claims: int = _DEFAULT_MAX_CLAIMS,
    max_tokens: int | None = None,
) -> list[CoreClaim]:
    user_prompt = CLAIM_USER.format(
        question=question,
        answer=answer,
        max_claims=max_claims,
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            payload = await llm.complete_json(
                model=model,
                system_prompt=CLAIM_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
            )
            claims = collect_valid_claims(
                payload.get("claims") if isinstance(payload, dict) else None,
                max_claims=max_claims,
            )
            if claims:
                logger.info("claims extracted count=%s attempt=%s", len(claims), attempt + 1)
                return claims
            last_error = ValueError("Claim extractor returned no valid claims.")
        except (ValidationError, ValueError, LLMError, AttributeError, TypeError) as exc:
            last_error = exc
            logger.warning("Claim extraction attempt %s failed: %s", attempt + 1, exc)

    fallback = fallback_claims_from_answer(answer, max_claims=max_claims)
    if fallback:
        logger.warning(
            "Using fallback sentence claims count=%s after extraction failure: %s",
            len(fallback),
            last_error,
        )
        return fallback
    raise LLMError("Claim extractor did not return usable factual claims.") from last_error


def collect_valid_mutations(
    raw_items: object,
    *,
    allowed_claims: set[str] | None = None,
) -> list[GeneratedMutation]:
    if not isinstance(raw_items, list):
        raise ValueError("Mutation payload must contain a list named mutations.")

    allowed = {item.casefold() for item in allowed_claims} if allowed_claims is not None else None
    valid: list[GeneratedMutation] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_items):
        try:
            mutation = GeneratedMutation.model_validate(item)
        except ValidationError:
            logger.warning("Rejected malformed mutation at index %s.", index)
            continue
        if not looks_like_complete_sentence(mutation.mutated_text):
            logger.warning(
                "Rejected incomplete/fragment/long mutation: %s",
                mutation.mutated_text[:160],
            )
            continue
        if allowed is not None and mutation.original_text.casefold() not in allowed:
            logger.warning(
                "Rejected mutation whose original_text is not a core claim: %s",
                mutation.original_text[:160],
            )
            continue
        key = mutation_key(mutation)
        if key in seen:
            logger.warning("Rejected duplicate mutation: %s", mutation.mutated_text[:160])
            continue
        if mutation.mutated_text.casefold() == mutation.original_text.casefold():
            logger.warning("Rejected no-op mutation (identical original and mutated text).")
            continue
        seen.add(key)
        valid.append(mutation)
    return valid


def hash_mutation_set(mutations: list[GeneratedMutation]) -> str:
    payload = "\n".join(f"{item.type.value}\t{item.mutated_text}" for item in mutations)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_mutation_counts(
    mutations: list[GeneratedMutation],
    synonym_count: int,
    antonym_count: int,
) -> list[GeneratedMutation]:
    synonyms = [item for item in mutations if item.type is MutationType.SYNONYM]
    antonyms = [item for item in mutations if item.type is MutationType.ANTONYM]
    if len(synonyms) < synonym_count or len(antonyms) < antonym_count:
        raise ValueError(
            f"Expected {synonym_count} unique synonym and {antonym_count} unique antonym mutations, "
            f"received {len(synonyms)} synonym and {len(antonyms)} antonym."
        )
    return synonyms[:synonym_count] + antonyms[:antonym_count]


async def generate_mutations(
    llm: LLMClient,
    *,
    model: str,
    question: str,
    answer: str,
    synonym_count: int,
    antonym_count: int,
    max_tokens: int | None = None,
    claim_max_tokens: int | None = None,
    max_claims: int = _DEFAULT_MAX_CLAIMS,
) -> list[GeneratedMutation]:
    """Extract core claims, then fill synonym/antonym quotas with partial retries.

    Keeps already-valid mutations across rounds and requests only the missing
    counts instead of regenerating the entire set each time.
    """
    claims = await extract_core_claims(
        llm,
        model=model,
        question=question,
        answer=answer,
        max_claims=max_claims,
        max_tokens=claim_max_tokens if claim_max_tokens is not None else min(256, max_tokens or 256),
    )
    allowed = {claim.text for claim in claims}
    claims_block = format_claims_block(claims)

    kept_synonyms: list[GeneratedMutation] = []
    kept_antonyms: list[GeneratedMutation] = []
    seen: set[tuple[str, str]] = set()
    last_error: Exception | None = None
    # Initial full request + up to 3 fill rounds for missing items only.
    max_rounds = 4

    for round_index in range(max_rounds):
        need_syn = synonym_count - len(kept_synonyms)
        need_ant = antonym_count - len(kept_antonyms)
        if need_syn <= 0 and need_ant <= 0:
            break

        if round_index == 0 and not kept_synonyms and not kept_antonyms:
            user_prompt = MUTATION_USER.format(
                question=question,
                claims_block=claims_block,
                synonym_count=synonym_count,
                antonym_count=antonym_count,
            )
        else:
            accepted = kept_synonyms + kept_antonyms
            user_prompt = MUTATION_FILL_USER.format(
                question=question,
                claims_block=claims_block,
                accepted_block=format_accepted_mutations_block(accepted),
                synonym_count=max(0, need_syn),
                antonym_count=max(0, need_ant),
            )
            if round_index > 0:
                user_prompt += _RETRY_HINT

        try:
            payload = await llm.complete_json(
                model=model,
                system_prompt=MUTATION_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
            )
            valid = collect_valid_mutations(
                payload.get("mutations") if isinstance(payload, dict) else None,
                allowed_claims=allowed,
            )
            before = len(kept_synonyms) + len(kept_antonyms)
            merge_mutation_batch(
                kept_synonyms=kept_synonyms,
                kept_antonyms=kept_antonyms,
                incoming=valid,
                synonym_count=synonym_count,
                antonym_count=antonym_count,
                seen=seen,
            )
            after = len(kept_synonyms) + len(kept_antonyms)
            logger.info(
                "mutation round=%s kept_syn=%s/%s kept_ant=%s/%s added=%s",
                round_index + 1,
                len(kept_synonyms),
                synonym_count,
                len(kept_antonyms),
                antonym_count,
                after - before,
            )
            if after == before and (need_syn > 0 or need_ant > 0):
                last_error = ValueError(
                    f"Mutation fill round added no new valid items "
                    f"(need {need_syn} synonym, {need_ant} antonym)."
                )
        except (ValidationError, ValueError, LLMError, AttributeError, TypeError) as exc:
            last_error = exc
            logger.warning("Mutation generation round %s failed: %s", round_index + 1, exc)

    if len(kept_synonyms) >= synonym_count and len(kept_antonyms) >= antonym_count:
        selected = kept_synonyms[:synonym_count] + kept_antonyms[:antonym_count]
        logger.info(
            "mutations generated count=%s claims=%s rounds_used<=%s",
            len(selected),
            len(claims),
            max_rounds,
        )
        return selected

    raise LLMError(
        "Mutation generator did not return the required mutation set."
    ) from last_error
