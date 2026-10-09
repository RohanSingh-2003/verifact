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
from app.metaqa.scoring import Verdict, parse_verdict
from app.schemas.detect import IndependentVerifierVerdict

logger = logging.getLogger("verifact.independent_verifiers")

INDEPENDENT_VERIFIER_SYSTEM = """You are an independent AI verifier evaluating an answer to a factual question.
Judge whether the generated answer is factually accurate, consistent, and directly supported.

Verdict options:
- YES: The generated answer is factually accurate and supported.
- NO: The generated answer is factually incorrect, contains a hallucination, or contradicts facts.
- NOT SURE: The factual accuracy of the answer cannot be determined reliably.

Rules:
- Evaluate independently without assumptions about what other models decide.
- Do not assume the answer is automatically true or false.
- Provide a brief rationale (under 25 words).
- Return JSON only: {"verdict": "YES" | "NO" | "NOT SURE", "rationale": "..."}"""

INDEPENDENT_VERIFIER_USER = """Question:
{question}

Generated Answer to evaluate:
{answer}

Judge whether this generated answer is factually accurate and supported.
Return JSON only (no markdown):
{{
  "verdict": "YES" | "NO" | "NOT SURE",
  "rationale": "..."
}}"""


async def evaluate_single_verifier(
    model_id: str,
    *,
    question: str,
    answer: str,
    settings: Settings,
    test_llm: LLMClient | None = None,
) -> IndependentVerifierVerdict:
    """Execute an independent verification request for a single model in the verifier pool.

    If the provider fails or is unconfigured, returns FAILED / API Error.
    NEVER converts technical failures to NOT SURE.
    """
    mdef = MODEL_REGISTRY.get(model_id)
    if mdef is None:
        return IndependentVerifierVerdict(
            model_id=model_id,
            model_name=model_id,
            provider="Unknown",
            verdict="FAILED",
            rationale="",
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
            rationale="",
            error=f"API Error: {mdef.env_key_name} is not configured in backend environment.",
            status="failed",
        )

    client: Any = None
    try:
        if isinstance(test_llm, MockLLMClient):
            client = test_llm
            payload = await client.complete_json(
                model=mdef.default_model_name,
                system_prompt=INDEPENDENT_VERIFIER_SYSTEM,
                user_prompt=INDEPENDENT_VERIFIER_USER.format(
                    question=question,
                    answer=answer,
                ),
            )
        else:
            client = get_model_client(model_id, settings)
            payload = await client.complete_json(
                system_prompt=INDEPENDENT_VERIFIER_SYSTEM,
                user_prompt=INDEPENDENT_VERIFIER_USER.format(
                    question=question,
                    answer=answer,
                ),
            )

        if not isinstance(payload, dict):
            return IndependentVerifierVerdict(
                model_id=model_id,
                model_name=model_name,
                provider=provider_name,
                verdict="FAILED",
                rationale="Malformed verifier payload.",
                error="Invalid response payload type (expected JSON object)",
                status="failed",
            )

        raw_verdict = str(payload.get("verdict") or "").strip()
        raw_rationale = str(payload.get("rationale") or "").strip()
        verdict_enum, parse_failed = parse_verdict(raw_verdict)

        if parse_failed or verdict_enum is None:
            return IndependentVerifierVerdict(
                model_id=model_id,
                model_name=model_name,
                provider=provider_name,
                verdict="FAILED",
                rationale=raw_rationale or "Unsupported verdict.",
                error=f"Unsupported verdict: {raw_verdict!r}",
                status="failed",
            )

        return IndependentVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict=verdict_enum.value,
            rationale=raw_rationale or f"Evaluated as {verdict_enum.value} by {model_name}.",
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
            rationale="",
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
            rationale="",
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
            rationale="",
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
    selected_answer_model_id: str,
    settings: Settings,
    test_llm: LLMClient | None = None,
) -> list[IndependentVerifierVerdict]:
    """Dynamically evaluate the generated answer using ALL OTHER models in MODEL_REGISTRY.

    The selected answer model is NEVER included as its own verifier.
    Every other model executes its own independent API request.
    """
    canonical_selected = validate_answer_model(selected_answer_model_id)

    # Dynamic pool: all models except the selected answer model
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
                    rationale="",
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
                    rationale="",
                    error="Internal error during verifier evaluation",
                    status="failed",
                )
            )

    return verdicts


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
                rationale="",
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
