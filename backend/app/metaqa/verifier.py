from __future__ import annotations

import logging
import time

from pydantic import BaseModel, Field, ValidationError

from app.llm.base import (
    LLMClient,
    LLMError,
    LLMMalformedResponseError,
    LLMTimeoutError,
)
from app.llm.prompts import VERIFY_SYSTEM, VERIFY_USER
from app.metaqa.scoring import Verdict, parse_verdict

logger = logging.getLogger("verifact.metaqa.verifier")


class VerifierResult(BaseModel):
    verdict: Verdict | None = None
    rationale: str = ""
    parse_failed: bool = False
    error: str | None = None


class VerifierPayload(BaseModel):
    verdict: str
    rationale: str = Field(default="")


def result_from_payload(payload: object) -> VerifierResult:
    """Normalize a verifier payload without using rationale for scoring.

    Distinguishes valid model verdicts (YES, NO, NOT SURE) from parse errors.
    If the payload is malformed or returns an unsupported verdict, verdict is None
    and parse_failed is True.
    """
    if isinstance(payload, dict):
        try:
            parsed = VerifierPayload.model_validate(payload)
            verdict, parse_failed = parse_verdict(parsed.verdict)
            if parse_failed:
                return VerifierResult(
                    verdict=None,
                    rationale=parsed.rationale.strip() or "Unsupported verifier verdict.",
                    parse_failed=True,
                    error=f"Unsupported verdict: {parsed.verdict!r}",
                )
            return VerifierResult(
                verdict=verdict,
                rationale=parsed.rationale.strip(),
                parse_failed=False,
            )
        except ValidationError:
            raw_verdict = payload.get("verdict")
            return VerifierResult(
                verdict=None,
                rationale=str(payload.get("rationale") or "").strip() or "Malformed verifier payload.",
                parse_failed=True,
                error=f"Payload validation error for verdict: {raw_verdict!r}",
            )
    return VerifierResult(
        verdict=None,
        rationale="Malformed verifier payload.",
        parse_failed=True,
        error="Invalid payload type",
    )


async def verify_mutation(
    llm: LLMClient,
    *,
    model: str,
    question: str,
    answer: str,
    statement: str,
    max_tokens: int | None = None,
) -> VerifierResult:
    start_time = time.perf_counter()
    try:
        payload = await llm.complete_json(
            model=model,
            system_prompt=VERIFY_SYSTEM,
            user_prompt=VERIFY_USER.format(
                question=question,
                answer=answer,
                statement=statement,
            ),
            max_tokens=max_tokens,
        )
    except LLMTimeoutError as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "Verifier timeout for statement %r after %.1fms: %s",
            statement[:80],
            elapsed_ms,
            exc,
        )
        return VerifierResult(
            verdict=None,
            rationale="Verification request timed out.",
            parse_failed=True,
            error="Timeout",
        )
    except LLMMalformedResponseError as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "Verifier returned malformed/incomplete JSON for statement %r after %.1fms: %s",
            statement[:80],
            elapsed_ms,
            exc,
        )
        return VerifierResult(
            verdict=None,
            rationale="Gemini returned an incomplete or invalid response.",
            parse_failed=True,
            error="Malformed JSON",
        )
    except LLMError as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "Verifier call failed for statement %r after %.1fms: %s",
            statement[:80],
            elapsed_ms,
            exc,
        )
        return VerifierResult(
            verdict=None,
            rationale=f"Verification failed: {exc}",
            parse_failed=True,
            error=str(exc),
        )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    result = result_from_payload(payload)
    logger.info(
        "Verifier call finished model=%s elapsed_ms=%.1f verdict=%s parse_failed=%s error=%s",
        model,
        elapsed_ms,
        result.verdict.value if result.verdict else "NONE",
        result.parse_failed,
        result.error or "none",
    )
    return result
