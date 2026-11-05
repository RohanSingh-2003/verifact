from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import Settings
from app.llm.base import (
    LLMClient,
    LLMError,
    LLMMalformedResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
)

logger = logging.getLogger("verifact.evaluation.gemini_judge")

JudgeLabel = Literal["RELIABLE", "HALLUCINATED", "NEEDS_REVIEW"]

GEMINI_JUDGE_SYSTEM = """You are an independent AI research judge evaluating the factual accuracy of AI-generated answers for a scientific benchmark study.
Your task is to judge whether a generated answer is factually accurate, consistent with verified reference information, or contains fact-conflicting hallucinations.

Evaluation Protocol & Rules:
1. Complete Answer Analysis: Evaluate the complete generated answer, not merely whether it contains specific reference keywords.
2. Paraphrasing & Vocabulary: Valid paraphrasing, alternative technical phrasing, or synonyms must NEVER be marked as hallucinations.
3. Reference Incompleteness: A reference answer is not necessarily exhaustive. The presence of true supplementary facts absent from the reference does NOT make the answer hallucinated.
4. Unsupported Claims: Unsupported claims that do not contradict established facts must not automatically be marked as hallucinated.
5. Strict Grounds for HALLUCINATED: Mark as HALLUCINATED only when the answer makes an assertion that directly contradicts gold reference answers, verified supporting evidence, or established real-world facts.
6. When to Return NEEDS_REVIEW:
   - When reference information is insufficient to verify the claims.
   - When available evidence conflicts.
   - When the question or answer is ambiguous or subjective.
   - When you cannot reliably distinguish between a factual error and a valid alternative formulation.

Output JSON format ONLY (no markdown fences, no explanatory text outside JSON):
{
  "label": "RELIABLE" | "HALLUCINATED" | "NEEDS_REVIEW",
  "reasoning_summary": "<Concise rationale under 40 words>",
  "supported_claims": ["<Claim 1>", ...],
  "contradicted_claims": ["<Claim 1>", ...],
  "unsupported_claims": ["<Claim 1>", ...],
  "evidence_used": ["<Evidence snippet or reference fact used>", ...],
  "confidence": <float between 0.0 and 1.0, or null>
}"""

GEMINI_JUDGE_USER = """Question:
{question}

Reference Gold Answer:
{reference_answer}
{aliases_section}
{correct_answers_section}
{incorrect_answers_section}
{evidence_section}

Generated Answer to Evaluate:
{generated_answer}

Evaluate the generated answer against the reference information. Return valid JSON only:"""


class GeminiJudgeVerdict(BaseModel):
    """Structured research evaluation result produced by the Gemini judge."""
    label: JudgeLabel = "NEEDS_REVIEW"
    reasoning_summary: str = ""
    supported_claims: list[str] = Field(default_factory=list)
    contradicted_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)
    confidence: float | None = None
    status: Literal["completed", "failed", "unavailable"] = "completed"
    error: str | None = None
    raw_response: str | None = None


def _sanitize_error(msg: str, api_key: str | None = None) -> str:
    cleaned = str(msg)
    if api_key and len(api_key) > 4:
        cleaned = cleaned.replace(api_key, "[REDACTED_API_KEY]")
    cleaned = re.sub(r"sk-[a-zA-Z0-9_\-]{16,}", "[REDACTED_API_KEY]", cleaned)
    return cleaned


class GeminiJudgeClient:
    """Dedicated independent Gemini research judge connecting via OpenRouter.
    
    IMPORTANT:
    - Uses OpenRouter's OpenAI-compatible API (https://openrouter.ai/api/v1).
    - Reads credentials from OPENROUTER_API_KEY.
    - Uses exact model configured by GROUND_TRUTH_JUDGE_MODEL.
    - Automatic model routing ('openrouter/auto') is strictly forbidden.
    - Model fallback is forbidden (fallback_model_name=None); never falls back to Gemma or other verifiers.
    - Exclusively used for benchmark ground-truth research evaluation.
    - NEVER added to interactive detection pipeline, independent verifier pool, or combined risk scoring.
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 30.0,
        settings: Settings | None = None,
        test_llm: LLMClient | None = None,
    ) -> None:
        self._settings = settings
        resolved_key = (api_key or (settings.openrouter_api_key if settings else "") or "").strip()
        resolved_model = (
            model
            or (getattr(settings, "ground_truth_judge_model", "") if settings else "")
            or (getattr(settings, "gemini_judge_model", "") if settings else "")
            or ""
        ).strip()
        resolved_base_url = (
            base_url
            or (getattr(settings, "openrouter_base_url", "") if settings else "")
            or "https://openrouter.ai/api/v1"
        ).strip()
        resolved_timeout = (
            timeout_seconds
            or (getattr(settings, "ground_truth_judge_timeout_seconds", 30.0) if settings else 30.0)
        )

        self._api_key = resolved_key
        self._model = resolved_model
        self._base_url = resolved_base_url
        self._timeout_seconds = resolved_timeout
        self._test_llm = test_llm

    @property
    def is_available(self) -> bool:
        if self._test_llm is not None:
            return True
        return bool(self._api_key and self._model)

    async def evaluate_answer(
        self,
        *,
        question: str,
        generated_answer: str,
        reference_answer: str,
        aliases: list[str] | None = None,
        correct_answers: list[str] | None = None,
        incorrect_answers: list[str] | None = None,
        context: str | list[str] | None = None,
        supporting_evidence: list[str] | None = None,
    ) -> GeminiJudgeVerdict:
        """Evaluate a generated answer against reference factual information using Gemini via OpenRouter."""
        if self._test_llm is None:
            if not self._api_key:
                return GeminiJudgeVerdict(
                    label="NEEDS_REVIEW",
                    reasoning_summary="OpenRouter ground truth judge is unavailable (OPENROUTER_API_KEY not configured).",
                    status="unavailable",
                    error="API Error: OPENROUTER_API_KEY is not configured in backend environment.",
                )
            if not self._model:
                return GeminiJudgeVerdict(
                    label="NEEDS_REVIEW",
                    reasoning_summary="Ground truth judge model is not configured (GROUND_TRUTH_JUDGE_MODEL not set).",
                    status="unavailable",
                    error="Configuration Error: GROUND_TRUTH_JUDGE_MODEL is not configured.",
                )
            if self._model.lower() in {"openrouter/auto", "auto"}:
                return GeminiJudgeVerdict(
                    label="NEEDS_REVIEW",
                    reasoning_summary="Automatic model routing is forbidden for ground truth judge.",
                    status="failed",
                    error="Configuration Error: Automatic model routing ('openrouter/auto') is forbidden. Specify an explicit Gemini model ID.",
                )

        # Build context sections
        aliases_sec = f"\nAcceptable Aliases: {', '.join(aliases)}" if aliases else ""
        correct_sec = "\nVerified Correct Variations:\n" + "\n".join(f"- {c}" for c in correct_answers) if correct_answers else ""
        incorrect_sec = "\nKnown Fact-Conflicting / Misconception Answers:\n" + "\n".join(f"- {w}" for w in incorrect_answers) if incorrect_answers else ""

        evidence_lines: list[str] = []
        if isinstance(context, str) and context.strip():
            evidence_lines.append(f"Context: {context.strip()[:1000]}")
        elif isinstance(context, list) and context:
            evidence_lines.extend(f"Context: {str(c).strip()[:400]}" for c in context[:4])

        if supporting_evidence:
            evidence_lines.extend(f"Evidence: {str(e).strip()[:400]}" for e in supporting_evidence[:4])

        evidence_sec = "\nSupporting Reference Evidence:\n" + "\n".join(evidence_lines) if evidence_lines else ""

        user_prompt = GEMINI_JUDGE_USER.format(
            question=question.strip(),
            reference_answer=reference_answer.strip(),
            aliases_section=aliases_sec,
            correct_answers_section=correct_sec,
            incorrect_answers_section=incorrect_sec,
            evidence_section=evidence_sec,
            generated_answer=generated_answer.strip(),
        )

        try:
            if self._test_llm is not None:
                try:
                    payload = await self._test_llm.complete_json(
                        model=self._model,
                        system_prompt=GEMINI_JUDGE_SYSTEM,
                        user_prompt=user_prompt,
                    )
                except TypeError:
                    payload = await self._test_llm.complete_json(
                        system_prompt=GEMINI_JUDGE_SYSTEM,
                        user_prompt=user_prompt,
                    )
            else:
                from app.llm.providers import OpenRouterClient
                client = OpenRouterClient(
                    base_url=self._base_url,
                    api_key=self._api_key,
                    model_name=self._model,
                    fallback_model_name=None,  # STRICT: No model fallback
                    timeout_seconds=self._timeout_seconds,
                    max_retries=1,
                )
                try:
                    max_tok = getattr(self._settings, 'llm_max_output_tokens', 800) if self._settings else 800
                    payload = await client.complete_json(
                        system_prompt=GEMINI_JUDGE_SYSTEM,
                        user_prompt=user_prompt,
                        max_tokens=max_tok,
                    )
                finally:
                    await client.aclose()

            if not isinstance(payload, dict):
                return GeminiJudgeVerdict(
                    label="NEEDS_REVIEW",
                    reasoning_summary="Malformed response from judge: expected JSON object.",
                    status="failed",
                    error="Malformed JSON response from OpenRouter Gemini judge",
                )

            # Validate and parse label
            raw_label = str(payload.get("label") or "").strip().upper()
            if raw_label in {"RELIABLE", "CORRECT", "YES"}:
                normalized_label: JudgeLabel = "RELIABLE"
            elif raw_label in {"HALLUCINATED", "INCORRECT", "NO"}:
                normalized_label: JudgeLabel = "HALLUCINATED"
            elif raw_label in {"NEEDS_REVIEW", "UNCERTAIN", "NOT SURE", "NOT_SURE"}:
                normalized_label: JudgeLabel = "NEEDS_REVIEW"
            else:
                return GeminiJudgeVerdict(
                    label="NEEDS_REVIEW",
                    reasoning_summary=f"Invalid judge label received: {raw_label!r}.",
                    status="failed",
                    error=f"Invalid judge label: {raw_label!r}",
                    raw_response=json.dumps(payload),
                )

            conf_raw = payload.get("confidence")
            confidence = None
            if conf_raw is not None:
                try:
                    c_val = float(conf_raw)
                    if 0.0 <= c_val <= 1.0:
                        confidence = round(c_val, 3)
                except (ValueError, TypeError):
                    confidence = None

            def _clean_list(val: Any) -> list[str]:
                if isinstance(val, list):
                    return [str(item).strip() for item in val if str(item).strip()]
                if isinstance(val, str) and val.strip():
                    return [val.strip()]
                return []

            return GeminiJudgeVerdict(
                label=normalized_label,
                reasoning_summary=str(payload.get("reasoning_summary") or payload.get("reasoning") or "").strip(),
                supported_claims=_clean_list(payload.get("supported_claims")),
                contradicted_claims=_clean_list(payload.get("contradicted_claims")),
                unsupported_claims=_clean_list(payload.get("unsupported_claims")),
                evidence_used=_clean_list(payload.get("evidence_used")),
                confidence=confidence,
                status="completed",
                raw_response=json.dumps(payload),
            )

        except LLMRateLimitError as exc:
            sanitized = _sanitize_error(str(exc), self._api_key)
            logger.warning("Gemini judge rate limited: %s", sanitized)
            return GeminiJudgeVerdict(
                label="NEEDS_REVIEW",
                reasoning_summary="Gemini judge rate limit exceeded.",
                status="failed",
                error=f"API Error: {sanitized}",
            )
        except LLMTimeoutError as exc:
            sanitized = _sanitize_error(str(exc), self._api_key)
            logger.warning("Gemini judge timed out: %s", sanitized)
            return GeminiJudgeVerdict(
                label="NEEDS_REVIEW",
                reasoning_summary="Gemini judge timed out.",
                status="failed",
                error=f"API Error: {sanitized}",
            )
        except LLMUnavailableError as exc:
            sanitized = _sanitize_error(str(exc), self._api_key)
            logger.warning("Gemini judge temporarily unavailable: %s", sanitized)
            return GeminiJudgeVerdict(
                label="NEEDS_REVIEW",
                reasoning_summary="Gemini judge service unavailable.",
                status="failed",
                error=f"API Error: {sanitized}",
            )
        except LLMMalformedResponseError as exc:
            sanitized = _sanitize_error(str(exc), self._api_key)
            logger.warning("Gemini judge malformed JSON: %s", sanitized)
            return GeminiJudgeVerdict(
                label="NEEDS_REVIEW",
                reasoning_summary="Gemini judge returned malformed JSON.",
                status="failed",
                error=f"Malformed JSON: {sanitized}",
            )
        except (LLMError, ValueError) as exc:
            sanitized = _sanitize_error(str(exc), self._api_key)
            logger.warning("Gemini judge error: %s", sanitized)
            return GeminiJudgeVerdict(
                label="NEEDS_REVIEW",
                reasoning_summary="Gemini judge call failed.",
                status="failed",
                error=f"API Error: {sanitized}",
            )
        except Exception as exc:
            sanitized = _sanitize_error(str(exc), self._api_key)
            logger.exception("Unexpected error in Gemini judge: %s", sanitized)
            return GeminiJudgeVerdict(
                label="NEEDS_REVIEW",
                reasoning_summary="Unexpected error during judging.",
                status="failed",
                error=f"Internal error: {sanitized}",
            )
