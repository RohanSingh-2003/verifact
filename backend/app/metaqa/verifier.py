from __future__ import annotations

import logging

from pydantic import BaseModel, Field, ValidationError

from app.llm.base import LLMClient, LLMError
from app.llm.prompts import VERIFY_SYSTEM, VERIFY_USER
from app.metaqa.scoring import Verdict, parse_verdict

logger = logging.getLogger("verifact.metaqa.verifier")


class VerifierResult(BaseModel):
    verdict: Verdict
    rationale: str = ""
    parse_failed: bool = False


class VerifierPayload(BaseModel):
    verdict: str
    rationale: str = Field(default="")


def result_from_payload(payload: object) -> VerifierResult:
    """Normalize a verifier payload without using rationale for scoring."""
    if isinstance(payload, dict):
        try:
            parsed = VerifierPayload.model_validate(payload)
            verdict, parse_failed = parse_verdict(parsed.verdict)
            return VerifierResult(
                verdict=verdict,
                rationale=parsed.rationale.strip(),
                parse_failed=parse_failed,
            )
        except ValidationError:
            raw_verdict = payload.get("verdict")
            verdict, parse_failed = parse_verdict(None if raw_verdict is None else str(raw_verdict))
            return VerifierResult(
                verdict=verdict,
                rationale=str(payload.get("rationale") or "").strip(),
                parse_failed=True,
            )
    verdict, parse_failed = parse_verdict(str(payload) if payload is not None else None)
    return VerifierResult(verdict=verdict, rationale="", parse_failed=parse_failed or True)


async def verify_mutation(
    llm: LLMClient,
    *,
    model: str,
    question: str,
    answer: str,
    statement: str,
    max_tokens: int | None = None,
) -> VerifierResult:
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
    except LLMError:
        logger.warning("Verifier call failed; recording NOT SURE.")
        return VerifierResult(verdict=Verdict.NOT_SURE, rationale="", parse_failed=True)

    result = result_from_payload(payload)
    if result.parse_failed:
        logger.warning("Malformed verdict recorded as NOT SURE for statement %r", statement[:160])
    return result
