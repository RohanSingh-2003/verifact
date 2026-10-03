from __future__ import annotations

import logging
import re
import time
from typing import Any

from app.llm.base import LLMClient, LLMError
from app.web_evidence.types import EvidenceVerdict
from app.web_search.base import WebSource

logger = logging.getLogger("verifact.web_evidence.verifier")

EVIDENCE_VERIFY_SYSTEM = """You verify factual claims using ONLY the retrieved evidence snippets provided.
Do not use prior knowledge, browsing, tools, or facts outside each claim's Evidence block.
URL and domain are identifiers only — they are NOT evidence. Judge solely from snippet text.
If snippets are missing, vague, off-topic, or do not clearly address a claim, return INSUFFICIENT_EVIDENCE.
Never invent citations. Never treat "no search results" as CONTRADICTED.
Return JSON only. Keep each reason ≤40 words."""

EVIDENCE_VERIFY_USER = """Claim:
{claim}

Evidence:
{evidence}

Decide whether the evidence supports the claim, contradicts it, or is insufficient.

Allowed verdicts:
- SUPPORTED — a snippet explicitly states the same factual content as the claim.
- CONTRADICTED — a snippet explicitly states a conflicting fact about the same subject.
- INSUFFICIENT_EVIDENCE — snippets are missing, off-topic, too vague, or do not settle the claim.

Reasoning rules:
- Write a short claim-specific reason (1–2 sentences, ≤40 words).
- For SUPPORTED: mention the specific fact from a snippet that matches the claim.
- For CONTRADICTED: contrast what the snippet states vs what the claim states.
- For INSUFFICIENT_EVIDENCE: say what is missing or why snippets do not settle the claim.
- Do not cite URLs as proof.

Return JSON only:
{{
  "verdict": "SUPPORTED" | "CONTRADICTED" | "INSUFFICIENT_EVIDENCE",
  "reason": "claim-specific explanation grounded in the snippets"
}}"""

BATCH_EVIDENCE_VERIFY_SYSTEM = """You verify multiple factual claims using ONLY each claim's retrieved evidence snippets.
Do not use prior knowledge outside the Evidence blocks.
URL and domain are identifiers only — not evidence.
If snippets are missing, vague, or off-topic for a claim, return INSUFFICIENT_EVIDENCE for that claim.
Never invent citations. Never treat empty evidence as CONTRADICTED.
Return one verdict per claim_id. Keep each reason ≤40 words. Return JSON only."""

BATCH_EVIDENCE_VERIFY_USER = """Verify each claim independently using only its Evidence block.

{claim_blocks}

Allowed verdicts per claim:
- SUPPORTED
- CONTRADICTED
- INSUFFICIENT_EVIDENCE

Return JSON only:
{{
  "claims": [
    {{
      "claim_id": "claim_1",
      "verdict": "SUPPORTED" | "CONTRADICTED" | "INSUFFICIENT_EVIDENCE",
      "reason": "short claim-specific reason"
    }}
  ]
}}"""

_ALLOWED = {item.value for item in EvidenceVerdict}
_SNIPPET_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def sources_have_usable_snippets(sources: list[WebSource], *, min_words: int = 5) -> bool:
    """True when at least one source has enough textual content to judge from."""
    for source in sources:
        words = _SNIPPET_WORD_RE.findall(source.snippet or "")
        if len(words) >= min_words:
            return True
        title_words = _SNIPPET_WORD_RE.findall(source.title or "")
        if not words and len(title_words) >= 6:
            return True
    return False


def format_evidence_block(sources: list[WebSource], *, max_snippet_chars: int = 300) -> str:
    if not sources:
        return "(no evidence retrieved)"
    lines: list[str] = []
    for index, source in enumerate(sources, start=1):
        snippet = source.snippet.strip() or "(no snippet)"
        if len(snippet) > max_snippet_chars:
            snippet = snippet[:max_snippet_chars].rstrip() + "..."
        source_type = (source.source_type or "GENERAL").strip() or "GENERAL"
        lines.append(
            f"[{index}] title={source.title}\n"
            f"domain={source.domain} (identifier only; not evidence)\n"
            f"source_type={source_type} (metadata only; not proof)\n"
            f"url={source.url} (identifier only; not evidence)\n"
            f"snippet={snippet}"
        )
    return "\n\n".join(lines)


def parse_evidence_verdict(payload: dict[str, Any] | None) -> tuple[EvidenceVerdict, str]:
    if not isinstance(payload, dict):
        return EvidenceVerdict.INSUFFICIENT_EVIDENCE, "Verifier returned an invalid response."
    raw = str(payload.get("verdict") or "").strip().upper().replace(" ", "_")
    aliases = {
        "SUPPORT": EvidenceVerdict.SUPPORTED.value,
        "SUPPORTED": EvidenceVerdict.SUPPORTED.value,
        "CONTRADICT": EvidenceVerdict.CONTRADICTED.value,
        "CONTRADICTED": EvidenceVerdict.CONTRADICTED.value,
        "INSUFFICIENT": EvidenceVerdict.INSUFFICIENT_EVIDENCE.value,
        "INSUFFICIENT_EVIDENCE": EvidenceVerdict.INSUFFICIENT_EVIDENCE.value,
        "NOT_ENOUGH_EVIDENCE": EvidenceVerdict.INSUFFICIENT_EVIDENCE.value,
        "UNKNOWN": EvidenceVerdict.INSUFFICIENT_EVIDENCE.value,
        "HALLUCINATED": EvidenceVerdict.INSUFFICIENT_EVIDENCE.value,
        "FALSE": EvidenceVerdict.CONTRADICTED.value,
        "TRUE": EvidenceVerdict.SUPPORTED.value,
    }
    mapped = aliases.get(raw, raw)
    if mapped not in _ALLOWED:
        return EvidenceVerdict.INSUFFICIENT_EVIDENCE, "Verifier verdict could not be parsed."
    reason = str(payload.get("reason") or "").strip()
    if len(reason) > 320:
        reason = reason[:317] + "..."
    if not reason:
        reason = "No reason provided."
    return EvidenceVerdict(mapped), reason


def _empty_source_result(sources: list[WebSource]) -> tuple[EvidenceVerdict, str] | None:
    if not sources:
        return (
            EvidenceVerdict.INSUFFICIENT_EVIDENCE,
            "No web sources were retrieved for this claim.",
        )
    if not sources_have_usable_snippets(sources):
        return (
            EvidenceVerdict.INSUFFICIENT_EVIDENCE,
            "Retrieved sources do not include enough textual evidence to verify this claim.",
        )
    return None


async def verify_claim_against_evidence(
    llm: LLMClient,
    *,
    model: str,
    claim: str,
    sources: list[WebSource],
    max_tokens: int | None = None,
) -> tuple[EvidenceVerdict, str]:
    short_circuit = _empty_source_result(sources)
    if short_circuit is not None:
        return short_circuit
    user_prompt = EVIDENCE_VERIFY_USER.format(
        claim=claim,
        evidence=format_evidence_block(sources),
    )
    try:
        payload = await llm.complete_json(
            model=model,
            system_prompt=EVIDENCE_VERIFY_SYSTEM,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )
        verdict, reason = parse_evidence_verdict(payload if isinstance(payload, dict) else None)
        if verdict is EvidenceVerdict.SUPPORTED and not sources_have_usable_snippets(sources):
            return (
                EvidenceVerdict.INSUFFICIENT_EVIDENCE,
                "Retrieved sources do not include enough textual evidence to verify this claim.",
            )
        return verdict, reason
    except (LLMError, AttributeError, TypeError, ValueError) as exc:
        logger.warning("Evidence verification failed: %s", exc)
        return (
            EvidenceVerdict.INSUFFICIENT_EVIDENCE,
            "Evidence verification could not be completed for this claim.",
        )


def _parse_batch_payload(
    payload: dict[str, Any] | None,
    claim_ids: list[str],
) -> dict[str, tuple[EvidenceVerdict, str]]:
    out: dict[str, tuple[EvidenceVerdict, str]] = {}
    if not isinstance(payload, dict):
        return out
    rows = payload.get("claims")
    if not isinstance(rows, list):
        return out
    by_id = {cid: None for cid in claim_ids}
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("claim_id") or "").strip()
        if cid not in by_id and claim_ids:
            # Allow positional fallback later; ignore unknown ids unless exact match.
            continue
        verdict, reason = parse_evidence_verdict(row)
        if cid:
            out[cid] = (verdict, reason)
    return out


async def verify_claims_batch(
    llm: LLMClient,
    *,
    model: str,
    claims: list[tuple[str, str, list[WebSource]]],
    max_tokens: int | None = None,
) -> dict[str, tuple[EvidenceVerdict, str]]:
    """Verify multiple claims in one structured LLM call when possible.

    claims: list of (claim_id, claim_text, sources)
    Returns map claim_id → (verdict, reason). Claims that can be short-circuited
    without an LLM (no usable snippets) are resolved locally.
    """
    results: dict[str, tuple[EvidenceVerdict, str]] = {}
    needs_llm: list[tuple[str, str, list[WebSource]]] = []

    for claim_id, claim_text, sources in claims:
        short = _empty_source_result(sources)
        if short is not None:
            results[claim_id] = short
        else:
            needs_llm.append((claim_id, claim_text, sources))

    if not needs_llm:
        return results

    if len(needs_llm) == 1:
        cid, text, sources = needs_llm[0]
        results[cid] = await verify_claim_against_evidence(
            llm, model=model, claim=text, sources=sources, max_tokens=max_tokens
        )
        return results

    blocks: list[str] = []
    for cid, text, sources in needs_llm:
        blocks.append(
            f"claim_id: {cid}\n"
            f"Claim:\n{text}\n\n"
            f"Evidence:\n{format_evidence_block(sources)}"
        )
    user_prompt = BATCH_EVIDENCE_VERIFY_USER.format(claim_blocks="\n\n---\n\n".join(blocks))
    started = time.perf_counter()
    try:
        payload = await llm.complete_json(
            model=model,
            system_prompt=BATCH_EVIDENCE_VERIFY_SYSTEM,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )
        parsed = _parse_batch_payload(
            payload if isinstance(payload, dict) else None,
            [cid for cid, _, _ in needs_llm],
        )
        for cid, text, sources in needs_llm:
            if cid in parsed:
                verdict, reason = parsed[cid]
                if verdict is EvidenceVerdict.SUPPORTED and not sources_have_usable_snippets(sources):
                    results[cid] = (
                        EvidenceVerdict.INSUFFICIENT_EVIDENCE,
                        "Retrieved sources do not include enough textual evidence to verify this claim.",
                    )
                else:
                    results[cid] = (verdict, reason)
            else:
                # Fall back to single-claim verify for missing ids only.
                logger.warning("batch verify missing claim_id=%s; falling back to single call", cid)
                results[cid] = await verify_claim_against_evidence(
                    llm, model=model, claim=text, sources=sources, max_tokens=max_tokens
                )
        logger.info(
            "web_verification_ms=%.0f claims=%s mode=batch",
            (time.perf_counter() - started) * 1000,
            len(needs_llm),
        )
        return results
    except (LLMError, AttributeError, TypeError, ValueError) as exc:
        logger.warning("Batch evidence verification failed (%s); falling back per claim", exc)
        for cid, text, sources in needs_llm:
            results[cid] = await verify_claim_against_evidence(
                llm, model=model, claim=text, sources=sources, max_tokens=max_tokens
            )
        return results
