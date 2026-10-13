from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import Run
from app.llm.base import LLMClient, LLMError, LLMRateLimitError
from app.llm.mock import MockLLMClient
from app.llm.registry import (
    MODEL_REGISTRY,
    get_model_client,
    is_model_configured,
    resolve_model_id,
    validate_answer_model,
)
from app.schemas.detect import IndependentVerifierVerdict, MultiModelVerificationSummary

logger = logging.getLogger("verifact.independent_verifiers")

INDEPENDENT_VERIFIER_SYSTEM = """You are an independent AI verifier evaluating an answer to a factual question.
Judge whether the generated answer is factually accurate, consistent, and directly supported.

Verdict options:
- Correct: The generated answer is factually accurate and supported.
- Incorrect: The generated answer is factually incorrect, contains a hallucination, or contradicts facts.
- Uncertain: The factual accuracy of the answer cannot be determined reliably.

Rules:
- Evaluate independently without assumptions about what other models decide.
- Do not assume the answer is automatically true or false.
- Identify specific contradictory statements or claims that appear incorrect or unsupported, if any.
- Provide a concise reasoning (under 30 words).
- If you can produce a meaningful confidence estimate, provide a confidence score between 0.0 and 1.0; otherwise return null.
- Return JSON only:
{
  "verdict": "Correct" | "Incorrect" | "Uncertain",
  "reasoning": "...",
  "contradictory_claims": ["..."],
  "confidence": null
}"""

INDEPENDENT_VERIFIER_USER = """Question:
{question}

Generated Answer to evaluate:
{answer}
{context_section}
Judge whether this generated answer is factually accurate and supported.
Return JSON only (no markdown):
{{
  "verdict": "Correct" | "Incorrect" | "Uncertain",
  "reasoning": "...",
  "contradictory_claims": [],
  "confidence": null
}}"""


def _normalize_verdict_label(raw: str) -> tuple[str, bool]:
    """Map string verdict into 'Correct', 'Incorrect', 'Uncertain', or mark as failed."""
    cleaned = (raw or "").strip().strip("\"'").upper()
    if cleaned in ("CORRECT", "YES"):
        return "Correct", False
    if cleaned in ("INCORRECT", "NO"):
        return "Incorrect", False
    if cleaned in ("UNCERTAIN", "NOT SURE", "NOT_SURE"):
        return "Uncertain", False
    if "CORRECT" in cleaned and "INCORRECT" not in cleaned:
        return "Correct", False
    if "INCORRECT" in cleaned or cleaned == "NO":
        return "Incorrect", False
    if "UNCERTAIN" in cleaned or "NOT SURE" in cleaned:
        return "Uncertain", False
    return "FAILED", True


async def evaluate_single_verifier(
    model_id: str,
    *,
    question: str,
    answer: str,
    settings: Settings,
    test_llm: LLMClient | None = None,
    claims: list[str] | None = None,
    mutations: list[str] | None = None,
    web_evidence: str | None = None,
) -> IndependentVerifierVerdict:
    """Execute an independent verification request for a single model in the verifier pool.

    If the provider fails or is unconfigured, returns FAILED / API Error.
    NEVER converts technical failures to Uncertain.
    """
    mdef = MODEL_REGISTRY.get(model_id)
    if mdef is None:
        return IndependentVerifierVerdict(
            model_id=model_id,
            model_name=model_id,
            provider="Unknown",
            verdict="FAILED",
            reasoning="",
            rationale="",
            contradictory_claims=[],
            confidence=None,
            error=f"Unknown model identifier '{model_id}'",
            status="failed",
        )

    model_name = mdef.display_name
    provider_name = mdef.provider_display

    # Check configuration in live mode
    if settings.llm_mode == "live" and not is_model_configured(model_id, settings):
        return IndependentVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict="FAILED",
            reasoning="",
            rationale="",
            contradictory_claims=[],
            confidence=None,
            error=f"API Error: {mdef.env_key_name} is not configured in backend environment.",
            status="failed",
        )

    context_parts: list[str] = []
    if claims and len(claims) > 0:
        c_lines = "\n".join(f"- {c}" for c in claims[:6])
        context_parts.append(f"\nRelevant Extracted Claims:\n{c_lines}")
    elif mutations and len(mutations) > 0:
        m_lines = "\n".join(f"- {m}" for m in mutations[:6])
        context_parts.append(f"\nRelevant Claim Variations:\n{m_lines}")

    if web_evidence and web_evidence.strip():
        snippet = web_evidence.strip()[:1200]
        context_parts.append(f"\nRetrieved Web Evidence:\n{snippet}")

    context_section = "\n".join(context_parts)
    if context_section:
        context_section += "\n"

    user_prompt = INDEPENDENT_VERIFIER_USER.format(
        question=question,
        answer=answer,
        context_section=context_section,
    )

    client: Any = None
    try:
        if isinstance(test_llm, MockLLMClient):
            client = test_llm
            payload = await client.complete_json(
                model=mdef.default_model_name,
                system_prompt=INDEPENDENT_VERIFIER_SYSTEM,
                user_prompt=user_prompt,
            )
        else:
            client = get_model_client(model_id, settings)
            payload = await client.complete_json(
                system_prompt=INDEPENDENT_VERIFIER_SYSTEM,
                user_prompt=user_prompt,
            )

        if not isinstance(payload, dict):
            return IndependentVerifierVerdict(
                model_id=model_id,
                model_name=model_name,
                provider=provider_name,
                verdict="FAILED",
                reasoning="Malformed verifier payload.",
                rationale="Malformed verifier payload.",
                contradictory_claims=[],
                confidence=None,
                error="Invalid response payload type (expected JSON object)",
                status="failed",
            )

        raw_verdict = str(payload.get("verdict") or "").strip()
        raw_reasoning = str(payload.get("reasoning") or payload.get("rationale") or "").strip()
        raw_contradictory = payload.get("contradictory_claims")
        contradictory_claims: list[str] = []
        if isinstance(raw_contradictory, list):
            contradictory_claims = [str(c).strip() for c in raw_contradictory if str(c).strip()]
        elif isinstance(raw_contradictory, str) and raw_contradictory.strip():
            contradictory_claims = [raw_contradictory.strip()]

        raw_conf = payload.get("confidence")
        confidence: float | None = None
        if raw_conf is not None:
            try:
                c_val = float(raw_conf)
                if 0.0 <= c_val <= 1.0:
                    confidence = round(c_val, 3)
            except (ValueError, TypeError):
                confidence = None

        normalized_verdict, parse_failed = _normalize_verdict_label(raw_verdict)

        if parse_failed:
            return IndependentVerifierVerdict(
                model_id=model_id,
                model_name=model_name,
                provider=provider_name,
                verdict="FAILED",
                reasoning=raw_reasoning or "Unsupported verdict.",
                rationale=raw_reasoning or "Unsupported verdict.",
                contradictory_claims=[],
                confidence=None,
                error=f"Unsupported verdict: {raw_verdict!r}",
                status="failed",
            )

        return IndependentVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict=normalized_verdict,
            reasoning=raw_reasoning or f"Evaluated as {normalized_verdict} by {model_name}.",
            rationale=raw_reasoning or f"Evaluated as {normalized_verdict} by {model_name}.",
            contradictory_claims=contradictory_claims,
            confidence=confidence,
            error=None,
            status="completed",
        )
    except LLMRateLimitError as exc:
        logger.warning("Independent verifier %s rate limited: %s", model_id, exc)
        return IndependentVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict="FAILED — Rate limit exceeded",
            reasoning="",
            rationale="",
            contradictory_claims=[],
            confidence=None,
            error=f"API Error: {str(exc)}",
            status="failed",
        )
    except LLMError as exc:
        is_rl = "rate limit" in str(exc).lower() or "rate-limit" in str(exc).lower() or "429" in str(exc)
        verdict_str = "FAILED — Rate limit exceeded" if is_rl else "FAILED"
        logger.warning("Independent verifier %s failed with LLMError (is_rl=%s): %s", model_id, is_rl, exc)
        return IndependentVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict=verdict_str,
            reasoning="",
            rationale="",
            contradictory_claims=[],
            confidence=None,
            error=f"API Error: {str(exc)}",
            status="failed",
        )
    except Exception as exc:
        is_rl = "rate limit" in str(exc).lower() or "rate-limit" in str(exc).lower() or "429" in str(exc)
        verdict_str = "FAILED — Rate limit exceeded" if is_rl else "FAILED"
        logger.exception("Independent verifier %s unexpected failure (is_rl=%s)", model_id, is_rl)
        return IndependentVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict=verdict_str,
            reasoning="",
            rationale="",
            contradictory_claims=[],
            confidence=None,
            error=f"API Error: {str(exc)}",
            status="failed",
        )
    finally:
        if client is not None and not isinstance(client, MockLLMClient):
            close = getattr(client, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    logger.debug("Failed to close client for %s", model_id)


async def evaluate_all_independent_verifiers(
    question: str,
    answer: str,
    *,
    selected_answer_model_id: str = "gemma",
    settings: Settings,
    test_llm: LLMClient | None = None,
    claims: list[str] | None = None,
    mutations: list[str] | None = None,
    web_evidence: str | None = None,
) -> list[IndependentVerifierVerdict]:
    """Dynamically evaluate Gemma's answer using ALL OTHER models in MODEL_REGISTRY.

    Gemma 4:26B is NEVER included as its own verifier.
    Every other configured/registered model executes its own independent API request.
    """
    canonical_selected = validate_answer_model(selected_answer_model_id)

    # Dynamic pool: all models except the selected answer model (gemma)
    verifier_model_ids = [mid for mid in MODEL_REGISTRY if mid != canonical_selected]

    logger.info(
        "Starting independent AI verification for answer model=%s with verifiers=%s",
        canonical_selected,
        verifier_model_ids,
    )

    tasks = [
        evaluate_single_verifier(
            mid,
            question=question,
            answer=answer,
            settings=settings,
            test_llm=test_llm,
            claims=claims,
            mutations=mutations,
            web_evidence=web_evidence,
        )
        for mid in verifier_model_ids
    ]

    outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    verdicts: list[IndependentVerifierVerdict] = []

    for mid, outcome in zip(verifier_model_ids, outcomes, strict=True):
        mdef = MODEL_REGISTRY[mid]
        if isinstance(outcome, Exception):
            logger.exception("Unhandled error evaluating verifier %s", mid, exc_info=outcome)
            verdicts.append(
                IndependentVerifierVerdict(
                    model_id=mid,
                    model_name=mdef.display_name,
                    provider=mdef.provider_display,
                    verdict="FAILED",
                    reasoning="",
                    rationale="",
                    contradictory_claims=[],
                    confidence=None,
                    error=f"API Error: {str(outcome)}",
                    status="failed",
                )
            )
        elif isinstance(outcome, IndependentVerifierVerdict):
            verdicts.append(outcome)
        else:
            verdicts.append(
                IndependentVerifierVerdict(
                    model_id=mid,
                    model_name=mdef.display_name,
                    provider=mdef.provider_display,
                    verdict="FAILED",
                    reasoning="",
                    rationale="",
                    contradictory_claims=[],
                    confidence=None,
                    error="Internal error during verifier evaluation",
                    status="failed",
                )
            )

    return verdicts


def build_multi_model_summary(
    verdicts: list[IndependentVerifierVerdict],
) -> MultiModelVerificationSummary:
    """Aggregate individual verification results into an overall summary."""
    total_verifiers = len(verdicts)
    correct_count = 0
    incorrect_count = 0
    uncertain_count = 0
    failed_count = 0
    all_contradictory: list[str] = []

    for v in verdicts:
        norm = (v.verdict or "").strip().upper()
        if v.status == "failed" or norm.startswith("FAILED") or v.error:
            failed_count += 1
        elif norm in ("CORRECT", "YES"):
            correct_count += 1
        elif norm in ("INCORRECT", "NO"):
            incorrect_count += 1
        elif norm in ("UNCERTAIN", "NOT SURE", "NOT_SURE"):
            uncertain_count += 1

        for c in v.contradictory_claims:
            if c and c not in all_contradictory:
                all_contradictory.append(c)

    completed_verifiers = correct_count + incorrect_count + uncertain_count

    if completed_verifiers == 0:
        if failed_count == total_verifiers and total_verifiers > 0:
            agreement_state = "FAILED"
            summary_text = f"All {total_verifiers} verification providers encountered errors or were unavailable."
        else:
            agreement_state = "PENDING"
            summary_text = "Multi-model verifications are in progress..."
        return MultiModelVerificationSummary(
            total_verifiers=total_verifiers,
            completed_verifiers=completed_verifiers,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            uncertain_count=uncertain_count,
            failed_count=failed_count,
            agreement_state=agreement_state,
            summary_text=summary_text,
            disagreements_detected=False,
            contradictory_claims=all_contradictory,
        )

    disagreements = correct_count > 0 and incorrect_count > 0

    if disagreements:
        agreement_state = "DISAGREEMENT"
        summary_text = (
            f"Disagreement detected among independent models: {correct_count} evaluated as Correct, "
            f"{incorrect_count} as Incorrect, and {uncertain_count} Uncertain. "
            f"Conflicting assessments highlight potential factual ambiguity or hallucinations."
        )
    elif incorrect_count > 0 and correct_count == 0:
        agreement_state = "AGREEMENT"
        summary_text = (
            f"Consensus among decisive models: {incorrect_count} verifier(s) evaluated Gemma's answer as Incorrect"
            + (f" ({uncertain_count} Uncertain)" if uncertain_count > 0 else "")
            + ". Contradictory statements or hallucinations were flagged."
        )
    elif correct_count > 0 and incorrect_count == 0 and uncertain_count == 0:
        agreement_state = "AGREEMENT"
        summary_text = (
            f"Consensus: All {correct_count} responding independent models evaluated Gemma's answer as Correct."
        )
    elif correct_count > 0 and incorrect_count == 0 and uncertain_count > 0:
        agreement_state = "UNCERTAIN"
        summary_text = (
            f"Partial agreement: {correct_count} model(s) evaluated as Correct, while {uncertain_count} model(s) were Uncertain."
        )
    else:
        agreement_state = "UNCERTAIN"
        summary_text = (
            f"Uncertainty: All {uncertain_count} responding model(s) could not determine factual accuracy reliably."
        )

    if failed_count > 0:
        summary_text += f" ({failed_count} verifier(s) unavailable or failed)."

    return MultiModelVerificationSummary(
        total_verifiers=total_verifiers,
        completed_verifiers=completed_verifiers,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        uncertain_count=uncertain_count,
        failed_count=failed_count,
        agreement_state=agreement_state,
        summary_text=summary_text,
        disagreements_detected=disagreements,
        contradictory_claims=all_contradictory,
    )


def build_pending_independent_verifiers(
    selected_answer_model_id: str,
    settings: Settings,
) -> list[IndependentVerifierVerdict]:
    """Build the initial list of pending independent verifiers excluding the selected answer model."""
    canonical_selected = validate_answer_model(selected_answer_model_id)
    verifiers: list[IndependentVerifierVerdict] = []

    for mid, mdef in MODEL_REGISTRY.items():
        if mid == canonical_selected:
            continue
        configured = is_model_configured(mid, settings)
        status = "pending" if configured or settings.llm_mode == "mock" else "failed"
        verdict = "PENDING" if status == "pending" else "FAILED"
        error = None if status == "pending" else f"API Error: {mdef.env_key_name} is not configured."
        verifiers.append(
            IndependentVerifierVerdict(
                model_id=mid,
                model_name=mdef.display_name,
                provider=mdef.provider_display,
                verdict=verdict,
                reasoning="",
                rationale="",
                contradictory_claims=[],
                confidence=None,
                error=error,
                status=status,
            )
        )
    return verifiers


def persist_independent_verdicts(
    db: Session,
    run_id: str,
    verdicts: list[IndependentVerifierVerdict],
) -> None:
    """Serialize and save independent AI verdicts into the Run."""
    run = db.get(Run, run_id)
    if run is None:
        return
    raw = [v.model_dump() for v in verdicts]
    run.ai_verdicts_json = json.dumps(raw, ensure_ascii=False)
    db.flush()


def load_independent_verdicts(
    run: Run,
    selected_answer_model_id: str,
    settings: Settings,
) -> list[IndependentVerifierVerdict]:
    """Load serialized independent AI verdicts, or construct default pending list if not yet completed."""
    raw_json = getattr(run, "ai_verdicts_json", "") or ""
    if raw_json.strip():
        try:
            items = json.loads(raw_json)
            if isinstance(items, list):
                return [IndependentVerifierVerdict.model_validate(item) for item in items]
        except Exception:
            logger.exception("Failed to parse ai_verdicts_json for run %s", run.id)

    return build_pending_independent_verifiers(selected_answer_model_id, settings)
