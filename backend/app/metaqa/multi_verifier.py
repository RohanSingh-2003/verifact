from __future__ import annotations

import asyncio
from collections import Counter
import json
import logging
import time
from typing import Any, Callable

from app.config import Settings
from app.llm.base import LLMClient, LLMError, LLMRateLimitError, LLMTimeoutError
from app.llm.mock import MockLLMClient
from app.llm.prompts import VERIFY_SYSTEM, VERIFY_USER
from app.llm.registry import (
    MODEL_REGISTRY,
    get_model_client,
    is_model_configured,
    validate_answer_model,
)
from app.metaqa.mutation import GeneratedMutation
from app.metaqa.scoring import (
    MutationType,
    Verdict,
    contribution_score,
    expected_verdict,
)
from app.schemas.detect import ModelVerifierVerdict

logger = logging.getLogger("verifact.metaqa.multi_verifier")


async def evaluate_mutation_for_model(
    model_id: str,
    *,
    question: str,
    answer: str,
    mutation: GeneratedMutation,
    settings: Settings,
    test_llm: LLMClient | None = None,
) -> ModelVerifierVerdict:
    """Evaluate a single mutation with a single verifier model.
    
    CRITICAL RESEARCH RULES:
    1. NEVER reveals the expected verdict (YES for synonym, NO for antonym) to the verifier.
    2. Performs a real independent cloud API call.
    3. If the verifier fails/times out, returns FAILED / API Error. NEVER converts failures to NOT SURE.
    4. Failed verification calls return contribution=None so they are excluded from scoring.
    """
    mdef = MODEL_REGISTRY.get(model_id)
    if mdef is None:
        return ModelVerifierVerdict(
            model_id=model_id,
            model_name=model_id,
            provider="Unknown",
            verdict="FAILED",
            rationale="",
            error=f"Unknown model identifier '{model_id}'",
            status="failed",
            contribution=None,
        )

    model_name = mdef.display_name
    provider_name = mdef.provider_display

    # Check configuration in live mode when not using a test/mock client
    if test_llm is None and settings.llm_mode == "live" and not is_model_configured(model_id, settings):
        return ModelVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict="FAILED",
            rationale="",
            error=f"API Error: {mdef.env_key_name} is not configured in backend environment.",
            status="failed",
            contribution=None,
        )

    # Prompt does NOT reveal the expected verdict or mutation type!
    user_prompt = VERIFY_USER.format(
        question=question,
        answer=answer,
        statement=mutation.mutated_text,
    )

    client: Any = None
    try:
        if isinstance(test_llm, MockLLMClient):
            payload = await test_llm.complete_json(
                model=mdef.default_model_name,
                system_prompt=VERIFY_SYSTEM,
                user_prompt=user_prompt,
            )
        else:
            client = get_model_client(model_id, settings)
            payload = await client.complete_json(
                system_prompt=VERIFY_SYSTEM,
                user_prompt=user_prompt,
            )

        if not isinstance(payload, dict):
            return ModelVerifierVerdict(
                model_id=model_id,
                model_name=model_name,
                provider=provider_name,
                verdict="FAILED",
                rationale="",
                error="API Error: Model returned invalid non-dict JSON payload.",
                status="failed",
                contribution=None,
            )

        raw_verdict = str(payload.get("verdict") or "").strip().upper()
        rationale = str(payload.get("rationale") or "").strip()

        # Parse verdict into YES, NO, or NOT SURE
        if raw_verdict in {"YES", "TRUE", "CONSISTENT"}:
            verdict_enum = Verdict.YES
            verdict_str = "YES"
        elif raw_verdict in {"NO", "FALSE", "CONTRADICTION"}:
            verdict_enum = Verdict.NO
            verdict_str = "NO"
        elif raw_verdict in {"NOT SURE", "NOT_SURE", "UNCERTAIN"}:
            verdict_enum = Verdict.NOT_SURE
            verdict_str = "NOT SURE"
        else:
            return ModelVerifierVerdict(
                model_id=model_id,
                model_name=model_name,
                provider=provider_name,
                verdict="FAILED",
                rationale=rationale,
                error=f"API Error: Unsupported verdict value '{raw_verdict}'",
                status="failed",
                contribution=None,
            )

        # MetaQA scoring:
        # Synonym: YES=0, NO=1, NOT SURE=0.5
        # Antonym: YES=1, NO=0, NOT SURE=0.5
        contrib = contribution_score(mutation.type, verdict_enum)

        return ModelVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict=verdict_str,
            rationale=rationale,
            error=None,
            contribution=contrib,
            status="completed",
        )

    except LLMRateLimitError as exc:
        logger.warning("verifier rate limit model=%s statement=%r: %s", model_id, mutation.mutated_text[:60], exc)
        return ModelVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict="FAILED — Rate limit exceeded",
            rationale="",
            error=f"API Error: {str(exc)}",
            status="failed",
            contribution=None,
        )
    except LLMTimeoutError as exc:
        logger.warning("verifier timeout model=%s statement=%r: %s", model_id, mutation.mutated_text[:60], exc)
        return ModelVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict="FAILED",
            rationale="",
            error=f"API Error: Request timed out ({str(exc)})",
            status="failed",
            contribution=None,
        )
    except Exception as exc:
        is_rl = "rate limit" in str(exc).lower() or "rate-limit" in str(exc).lower() or "429" in str(exc)
        verdict_str = "FAILED — Rate limit exceeded" if is_rl else "FAILED"
        logger.warning("verifier error model=%s statement=%r (is_rl=%s): %s", model_id, mutation.mutated_text[:60], is_rl, exc)
        return ModelVerifierVerdict(
            model_id=model_id,
            model_name=model_name,
            provider=provider_name,
            verdict=verdict_str,
            rationale="",
            error=f"API Error: {str(exc)}",
            status="failed",
            contribution=None,
        )
    finally:
        if client is not None and not isinstance(client, MockLLMClient):
            close = getattr(client, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    logger.debug("Failed to close client for %s", model_id)


async def verify_mutation_across_models(
    mutation: GeneratedMutation,
    *,
    question: str,
    answer: str,
    verifier_model_ids: list[str],
    settings: Settings,
    test_llm: LLMClient | None = None,
) -> Any:
    """Run verification of ONE mutation concurrently across all verifier models."""
    from app.metaqa.detector import ScoredMutation

    tasks = [
        evaluate_mutation_for_model(
            mid,
            question=question,
            answer=answer,
            mutation=mutation,
            settings=settings,
            test_llm=test_llm,
        )
        for mid in verifier_model_ids
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    verdicts: list[ModelVerifierVerdict] = []
    for mid, res in zip(verifier_model_ids, raw_results, strict=True):
        if isinstance(res, Exception):
            mdef = MODEL_REGISTRY.get(mid)
            verdicts.append(
                ModelVerifierVerdict(
                    model_id=mid,
                    model_name=mdef.display_name if mdef else mid,
                    provider=mdef.provider_display if mdef else "Unknown",
                    verdict="FAILED",
                    rationale="",
                    error=f"API Error: {str(res)}",
                    status="failed",
                    contribution=None,
                )
            )
        else:
            verdicts.append(res)

    # Exclude failed calls from numerical aggregation
    successful = [v for v in verdicts if v.status == "completed" and v.contribution is not None]
    expected = expected_verdict(mutation.type)

    if successful:
        agg_contribution = sum(v.contribution for v in successful) / len(successful)
        unavailable = False
        parse_failed = False

        # Representative verdict: most common successful verdict
        counts = Counter(v.verdict for v in successful)
        most_common_verdict_str = counts.most_common(1)[0][0]
        if most_common_verdict_str == "YES":
            primary_verdict = Verdict.YES
        elif most_common_verdict_str == "NO":
            primary_verdict = Verdict.NO
        else:
            primary_verdict = Verdict.NOT_SURE

        rationale_parts = [f"{v.model_name}: {v.verdict}" for v in verdicts]
        rationale = "; ".join(rationale_parts)
    else:
        agg_contribution = 0.0
        unavailable = True
        parse_failed = True
        primary_verdict = None
        rationale = "All independent model verifications failed."

    return ScoredMutation(
        mutation=mutation,
        verdict=primary_verdict,
        expected=expected,
        contribution=round(agg_contribution, 4),
        rationale=rationale,
        parse_failed=parse_failed,
        unavailable=unavailable,
        verdicts=tuple(verdicts),
    )


async def verify_all_mutations_multi_model(
    mutations: list[GeneratedMutation],
    *,
    question: str,
    answer: str,
    verifier_model_ids: list[str],
    settings: Settings,
    on_result: Callable[[int, Any], None] | None = None,
    test_llm: LLMClient | None = None,
    concurrency: int = 3,
) -> list[Any]:
    """Verify all mutations across all independent verifier models.
    
    Each mutation is verified by all verifier models concurrently.
    Calls `on_result(index, scored_mutation)` as each mutation completes.
    """
    semaphore = asyncio.Semaphore(max(1, concurrency))
    results: list[Any] = [None] * len(mutations)

    async def _verify_one(index: int, mut: GeneratedMutation) -> Any:
        async with semaphore:
            scored = await verify_mutation_across_models(
                mut,
                question=question,
                answer=answer,
                verifier_model_ids=verifier_model_ids,
                settings=settings,
                test_llm=test_llm,
            )
            results[index] = scored
            if on_result is not None:
                try:
                    on_result(index, scored)
                except Exception:
                    logger.exception("on_result callback failed for mutation %s", index)
            return scored

    tasks = [_verify_one(i, mut) for i, mut in enumerate(mutations)]
    await asyncio.gather(*tasks)
    return results
