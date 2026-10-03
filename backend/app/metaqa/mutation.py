from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

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
        "function",
        "functions",
        "functioned",
        "lies",
        "lie",
        "located",
        "locates",
        "border",
        "borders",
        "belong",
        "belongs",
        "govern",
        "governs",
        "represent",
        "represents",
        "connect",
        "connects",
        "house",
        "houses",
        "feature",
        "features",
        "consist",
        "consists",
        "span",
        "spans",
        "act",
        "acts",
        "operate",
        "operates",
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
    if cleaned.endswith((":", "-")):
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


def resolve_original_claim(
    candidate: str | None,
    claims: list[CoreClaim] | None,
    mutated_text: str | None = None,
) -> str:
    """Resolve original_text to one of the extracted claims with tolerant matching."""
    if not claims:
        return candidate.strip() if candidate else ""
    if not candidate or not candidate.strip():
        if mutated_text:
            mut_words = set(_WORD_RE.findall(mutated_text.casefold()))
            best = claims[0]
            best_ov = -1
            for claim in claims:
                c_words = set(_WORD_RE.findall(claim.text.casefold()))
                ov = len(mut_words & c_words)
                if ov > best_ov:
                    best_ov = ov
                    best = claim
            if best_ov > 0:
                return best.text
        return claims[0].text

    cleaned = candidate.strip()
    c_lower = cleaned.casefold()

    # Exact casefold match
    for claim in claims:
        if claim.text.casefold() == c_lower:
            return claim.text

    # Match ignoring trailing punctuation and whitespace
    c_stripped = c_lower.strip(".!? ")
    for claim in claims:
        if claim.text.casefold().strip(".!? ") == c_stripped:
            return claim.text

    # Substring match
    for claim in claims:
        cl_clean = claim.text.casefold().strip(".!? ")
        if c_stripped in cl_clean or cl_clean in c_stripped:
            return claim.text

    # Word overlap match
    c_words = set(_WORD_RE.findall(c_lower))
    best_claim = claims[0]
    best_overlap = -1
    for claim in claims:
        claim_words = set(_WORD_RE.findall(claim.text.casefold()))
        overlap = len(c_words & claim_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_claim = claim

    if best_overlap > 0:
        return best_claim.text

    return claims[0].text


def clean_mutation_sentence(text: str) -> str:
    cleaned = " ".join(text.strip().strip("\"'`").split())
    # Clean leading markdown fences or bullet numbering
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = re.sub(r"^(\d+[\.\)]|\-|\*)\s*", "", cleaned).strip()
    # Clean known prefixes like "synonym:", "antonym:", "mutation:", "[synonym]"
    cleaned = re.sub(
        r"^(?:\[?(?:synonym(?:\s+mutation)?|antonym(?:\s+mutation)?|paraphrase|negation|mutation)\]?[\s:\-]+)+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


def normalize_mutation_payload(
    payload: object,
    claims: list[CoreClaim] | None = None,
) -> tuple[list[GeneratedMutation], dict[str, list[str]]]:
    """Normalize any mutation response payload into a standardized list of GeneratedMutation

    and the canonical dictionary:
    {
      "synonym_mutations": [...],
      "antonym_mutations": [...]
    }
    """
    raw_synonyms: list[Any] = []
    raw_antonyms: list[Any] = []

    if isinstance(payload, str):
        from app.llm.client import parse_json_object
        parsed = parse_json_object(payload)
        if parsed is not None:
            payload = parsed

    if isinstance(payload, dict):
        # Look for explicit synonym arrays
        for k in ("synonym_mutations", "synonyms", "synonym", "synonym_mutation", "syn"):
            if k in payload and isinstance(payload[k], list):
                raw_synonyms.extend(payload[k])
                break
        # Look for explicit antonym arrays
        for k in ("antonym_mutations", "antonyms", "antonym", "antonym_mutation", "ant", "negation_mutations", "negations"):
            if k in payload and isinstance(payload[k], list):
                raw_antonyms.extend(payload[k])
                break

        # If mutations key is present
        mut_val = payload.get("mutations")
        if isinstance(mut_val, dict):
            for k in ("synonym_mutations", "synonyms", "synonym"):
                if k in mut_val and isinstance(mut_val[k], list):
                    raw_synonyms.extend(mut_val[k])
            for k in ("antonym_mutations", "antonyms", "antonym", "negation_mutations", "negations"):
                if k in mut_val and isinstance(mut_val[k], list):
                    raw_antonyms.extend(mut_val[k])
        elif isinstance(mut_val, list):
            for item in mut_val:
                if isinstance(item, dict):
                    t = str(item.get("type") or item.get("mutation_type") or item.get("kind") or "").casefold()
                    if t in ("synonym", "paraphrase", "same", "consistent"):
                        raw_synonyms.append(item)
                    elif t in ("antonym", "negation", "contradiction", "opposite", "inconsistent"):
                        raw_antonyms.append(item)
                    else:
                        raw_synonyms.append(item)
                elif isinstance(item, str):
                    lower_item = item.strip().casefold()
                    if lower_item.startswith(("antonym", "negation", "opposite")):
                        raw_antonyms.append(item)
                    else:
                        raw_synonyms.append(item)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                t = str(item.get("type") or item.get("mutation_type") or item.get("kind") or "").casefold()
                if t in ("antonym", "negation", "contradiction", "opposite"):
                    raw_antonyms.append(item)
                else:
                    raw_synonyms.append(item)
            elif isinstance(item, str):
                lower_item = item.strip().casefold()
                if lower_item.startswith(("antonym", "negation", "opposite")):
                    raw_antonyms.append(item)
                else:
                    raw_synonyms.append(item)

    def _extract_text_and_orig(item: Any) -> tuple[str, str]:
        if isinstance(item, str):
            return clean_mutation_sentence(item), ""
        if isinstance(item, dict):
            mutated = (
                item.get("mutated_text")
                or item.get("mutation")
                or item.get("text")
                or item.get("statement")
                or item.get("mutated")
                or item.get("sentence")
                or ""
            )
            original = (
                item.get("original_text")
                or item.get("original")
                or item.get("claim")
                or item.get("source")
                or item.get("base")
                or ""
            )
            return clean_mutation_sentence(str(mutated)), str(original).strip()
        return "", ""

    valid_mutations: list[GeneratedMutation] = []
    seen: set[tuple[str, str]] = set()

    for item in raw_synonyms:
        m_text, o_text = _extract_text_and_orig(item)
        if not m_text:
            continue
        if not looks_like_complete_sentence(m_text):
            if not m_text.endswith((".", "!", "?")) and looks_like_complete_sentence(m_text + "."):
                m_text = m_text + "."
            else:
                continue
        orig = resolve_original_claim(o_text, claims, mutated_text=m_text)
        if m_text.casefold() == orig.casefold():
            continue
        key = ("synonym", m_text.casefold())
        if key in seen:
            continue
        seen.add(key)
        valid_mutations.append(
            GeneratedMutation(type=MutationType.SYNONYM, original_text=orig, mutated_text=m_text)
        )

    for item in raw_antonyms:
        m_text, o_text = _extract_text_and_orig(item)
        if not m_text:
            continue
        if not looks_like_complete_sentence(m_text):
            if not m_text.endswith((".", "!", "?")) and looks_like_complete_sentence(m_text + "."):
                m_text = m_text + "."
            else:
                continue
        orig = resolve_original_claim(o_text, claims, mutated_text=m_text)
        if m_text.casefold() == orig.casefold():
            continue
        key = ("antonym", m_text.casefold())
        if key in seen:
            continue
        seen.add(key)
        valid_mutations.append(
            GeneratedMutation(type=MutationType.ANTONYM, original_text=orig, mutated_text=m_text)
        )

    canonical_dict = {
        "synonym_mutations": [m.mutated_text for m in valid_mutations if m.type is MutationType.SYNONYM],
        "antonym_mutations": [m.mutated_text for m in valid_mutations if m.type is MutationType.ANTONYM],
    }
    return valid_mutations, canonical_dict


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
            # Tolerant claim matching: check if stripped or substring matches any allowed claim
            orig_stripped = mutation.original_text.casefold().strip(".!? ")
            matched_claim = next(
                (c for c in allowed_claims or () if c.casefold().strip(".!? ") == orig_stripped),
                None,
            )
            if matched_claim is not None:
                mutation.original_text = matched_claim
            else:
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
    """Generate synonym and antonym mutations in a single concise LLM call.

    Extracts claims deterministically from the candidate answer in 0ms (avoiding
    an extra LLM call), then generates the required mutations in one request.
    If the initial response is incomplete, at most one fill round is attempted.
    """
    claims = fallback_claims_from_answer(answer, max_claims=max_claims)
    kept_synonyms: list[GeneratedMutation] = []
    kept_antonyms: list[GeneratedMutation] = []
    seen: set[tuple[str, str]] = set()
    last_error: Exception | None = None
    max_rounds = 2

    for round_index in range(max_rounds):
        need_syn = synonym_count - len(kept_synonyms)
        need_ant = antonym_count - len(kept_antonyms)
        if need_syn <= 0 and need_ant <= 0:
            break

        if round_index == 0 and not kept_synonyms and not kept_antonyms:
            user_prompt = MUTATION_USER.format(
                question=question,
                answer=answer,
                synonym_count=synonym_count,
                antonym_count=antonym_count,
            )
        else:
            accepted = kept_synonyms + kept_antonyms
            user_prompt = MUTATION_FILL_USER.format(
                question=question,
                answer=answer,
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
                max_tokens=max_tokens or 300,
            )
            raw_response = payload.pop("_raw", None)
            if raw_response is None:
                raw_response = json.dumps(payload)
            logger.info("[METAQA MUTATION] Ollama response received: %s", raw_response)

            # Robust extraction accepting both standard and conceptual/alternative JSON formats
            valid, parsed_payload = normalize_mutation_payload(payload, claims=claims)
            logger.info("[METAQA MUTATION] Parsed mutation payload: %s", parsed_payload)

            round_syn = len(parsed_payload["synonym_mutations"])
            round_ant = len(parsed_payload["antonym_mutations"])
            logger.info("[METAQA MUTATION] Synonym count: %s", round_syn)
            logger.info("[METAQA MUTATION] Antonym count: %s", round_ant)

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

            if len(kept_synonyms) >= synonym_count and len(kept_antonyms) >= antonym_count:
                val_result = f"VALID (synonyms={len(kept_synonyms)}/{synonym_count}, antonyms={len(kept_antonyms)}/{antonym_count})"
            else:
                val_result = f"INCOMPLETE (synonyms={len(kept_synonyms)}/{synonym_count}, antonyms={len(kept_antonyms)}/{antonym_count})"
            logger.info("[METAQA MUTATION] Validation result: %s", val_result)

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
            logger.warning("[METAQA MUTATION] Validation result: FAILED: %s", exc)
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

    # Graceful partial mutation support: do not let a single missing mutation destroy MetaQA
    if kept_synonyms and kept_antonyms and (len(kept_synonyms) + len(kept_antonyms)) >= 3:
        selected = kept_synonyms[:synonym_count] + kept_antonyms[:antonym_count]
        logger.warning(
            "mutations partially generated syn=%s/%s ant=%s/%s total=%s; proceeding with partial set",
            len(kept_synonyms),
            synonym_count,
            len(kept_antonyms),
            antonym_count,
            len(selected),
        )
        return selected

    raise LLMError(
        "Mutation generator did not return the required mutation set."
    ) from last_error

