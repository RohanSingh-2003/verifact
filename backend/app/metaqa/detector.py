from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.config import Settings
from app.llm.base import LLMClient, LLMError, LLMTimeoutError
from app.llm.mock import MockLLMClient
from app.llm.prompts import ANSWER_SYSTEM, ANSWER_USER
from app.metaqa.mutation import GeneratedMutation, generate_mutations
from app.metaqa.scoring import (
    Classification,
    Verdict,
    aggregate_score,
    classify,
    contribution_score,
    expected_verdict,
    not_sure_rate,
)
from app.metaqa.verifier import VerifierResult, verify_mutation

logger = logging.getLogger("verifact.detector")


class MetaqaVerificationUnavailable(LLMError):
    """Raised when no mutation verifications completed successfully."""


@dataclass(frozen=True)
class BaseAnswer:
    text: str
    model: str


@dataclass(frozen=True)
class ScoredMutation:
    mutation: GeneratedMutation
    verdict: Verdict | None
    expected: Verdict
    contribution: float
    rationale: str
    parse_failed: bool = False
    unavailable: bool = False
    verdicts: tuple[Any, ...] = ()


@dataclass(frozen=True)
class StageTiming:
    answer_ms: float
    mutation_ms: float
    verify_ms: float
    total_ms: float
    synonym_count: int
    antonym_count: int
    verify_concurrency: int


@dataclass(frozen=True)
class DetectionResult:
    question: str
    base_answer: BaseAnswer
    mutations: list[ScoredMutation]
    hallucination_score: float
    threshold: float
    classification: Classification
    not_sure_rate: float
    generator_model: str
    verifier_model: str
    llm_mode: str = "live"
    timing: StageTiming | None = field(default=None)
    metaqa_completion: str = "complete"  # complete | partial
    verified_count: int = 0
    expected_count: int = 0


def score_mutation(
    mutation: GeneratedMutation,
    result: VerifierResult,
    *,
    unavailable: bool = False,
) -> ScoredMutation:
    expected = expected_verdict(mutation.type)
    if unavailable or result.parse_failed or result.verdict is None:
        return ScoredMutation(
            mutation=mutation,
            verdict=result.verdict,
            expected=expected,
            contribution=0.0,
            rationale=result.rationale or result.error or "Mutation verification did not complete.",
            parse_failed=True,
            unavailable=True,
        )
    contribution = contribution_score(mutation.type, result.verdict)
    return ScoredMutation(
        mutation=mutation,
        verdict=result.verdict,
        expected=expected,
        contribution=contribution,
        rationale=result.rationale,
        parse_failed=False,
        unavailable=False,
    )


async def generate_answer(
    llm: LLMClient,
    question: str,
    model: str,
    *,
    max_tokens: int | None = None,
) -> BaseAnswer:
    text = await llm.complete_text(
        model=model,
        system_prompt=ANSWER_SYSTEM,
        user_prompt=ANSWER_USER.format(question=question),
        max_tokens=max_tokens,
    )
    cleaned = text.strip()
    if not cleaned:
        raise LLMError("Generator returned an empty answer.")
    return BaseAnswer(text=cleaned, model=model)


async def run_detection(
    llm: LLMClient,
    *,
    question: str,
    settings: Settings,
    generator_model: str | None = None,
    verifier_model: str | None = None,
    verifier_llm: LLMClient | None = None,
    synonym_count: int | None = None,
    antonym_count: int | None = None,
) -> DetectionResult:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("Question must not be empty.")

    generator = settings.require_model(generator_model or settings.generator_model)
    verifier = settings.require_model(verifier_model or settings.verifier_model)
    verifier_client = verifier_llm or llm
    syn_n = synonym_count if synonym_count is not None else settings.synonym_count
    ant_n = antonym_count if antonym_count is not None else settings.antonym_count
    logger.info(
        "run started generator=%s verifier=%s question_len=%s mutations=%s+%s concurrency=%s",
        generator,
        verifier,
        len(cleaned_question),
        syn_n,
        ant_n,
        settings.verify_concurrency,
    )

    total_started = time.perf_counter()
    try:
        answer_started = time.perf_counter()
        answer = await generate_answer(
            llm,
            cleaned_question,
            generator,
            max_tokens=settings.llm_answer_max_tokens,
        )
        answer_ms = (time.perf_counter() - answer_started) * 1000
        logger.info("base answer generated in %.0f ms", answer_ms)

        return await run_metaqa_analysis(
            llm,
            question=cleaned_question,
            answer=answer,
            settings=settings,
            generator_model=generator,
            verifier_model=verifier,
            verifier_llm=verifier_client,
            synonym_count=syn_n,
            antonym_count=ant_n,
            answer_ms=answer_ms,
            total_started=total_started,
        )
    except Exception:
        logger.exception("run failed generator=%s verifier=%s", generator, verifier)
        raise


async def run_metaqa_analysis(
    llm: LLMClient,
    *,
    question: str,
    answer: BaseAnswer,
    settings: Settings,
    generator_model: str | None = None,
    verifier_model: str | None = None,
    verifier_models: list[str] | None = None,
    verifier_llm: LLMClient | None = None,
    synonym_count: int | None = None,
    antonym_count: int | None = None,
    answer_ms: float = 0.0,
    total_started: float | None = None,
    on_stage: Callable[[str], None] | None = None,
    on_mutations_ready: Callable[[list[GeneratedMutation], float], None] | None = None,
    on_mutation_verified: Callable[[int, ScoredMutation], None] | None = None,
) -> DetectionResult:
    """Run mutation generation, verification, and scoring for an existing answer.

    MetaQA methodology is unchanged; this only isolates the post-answer stages.
    """
    cleaned_question = question.strip()
    generator = generator_model or settings.generator_model
    # The selected answer model is responsible for generating both the answer and mutations
    mutation_model = generator_model or settings.generator_model
    if verifier_models:
        verifier = verifier_model or ", ".join(verifier_models)
    else:
        verifier = (
            verifier_model or settings.effective_verifier_model
            if verifier_llm is not None
            else settings.require_model(verifier_model or settings.verifier_model)
        )
    verifier_client = verifier_llm or llm
    syn_n = synonym_count if synonym_count is not None else settings.synonym_count
    ant_n = antonym_count if antonym_count is not None else settings.antonym_count
    started = total_started if total_started is not None else time.perf_counter()

    if on_stage is not None:
        on_stage("generating_mutations")

    mutation_started = time.perf_counter()
    mutations = await generate_mutations(
        llm,
        model=mutation_model,
        question=cleaned_question,
        answer=answer.text,
        synonym_count=syn_n,
        antonym_count=ant_n,
        max_tokens=settings.llm_mutation_max_tokens,
        claim_max_tokens=settings.llm_claim_max_tokens,
    )
    mutation_ms = (time.perf_counter() - mutation_started) * 1000
    logger.info("mutations generated count=%s in %.0f ms", len(mutations), mutation_ms)

    if on_mutations_ready is not None:
        on_mutations_ready(mutations, round(mutation_ms, 1))

    if on_stage is not None:
        on_stage("verifying_mutations")

    verify_started = time.perf_counter()
    if verifier_models:
        from app.metaqa.multi_verifier import verify_all_mutations_multi_model
        test_client = None
        if isinstance(verifier_client, MockLLMClient):
            test_client = verifier_client
        elif hasattr(verifier_client, "_inner") and isinstance(getattr(verifier_client, "_inner"), MockLLMClient):
            test_client = getattr(verifier_client, "_inner")
        elif isinstance(llm, MockLLMClient):
            test_client = llm
        elif settings.llm_mode == "mock":
            test_client = verifier_client

        scored = await verify_all_mutations_multi_model(
            mutations=mutations,
            question=cleaned_question,
            answer=answer.text,
            verifier_model_ids=verifier_models,
            settings=settings,
            on_result=on_mutation_verified,
            test_llm=test_client,
        )
    else:
        # Fallback to single verifier when verifier_models is not provided
        verify_concurrency = (
            settings.gemini_verify_concurrency
            if verifier_llm is not None
            else settings.verify_concurrency
        )
        scored = await verify_mutations(
            verifier_client,
            question=cleaned_question,
            answer=answer.text,
            mutations=mutations,
            verifier_model=verifier,
            concurrency=verify_concurrency,
            max_tokens=settings.llm_verify_max_tokens,
            on_result=on_mutation_verified,
        )
    verify_ms = (time.perf_counter() - verify_started) * 1000

    if on_stage is not None:
        on_stage("calculating_score")

    total_ms = (time.perf_counter() - started) * 1000
    usable = [
        item for item in scored
        if not item.unavailable and not item.parse_failed and item.verdict is not None
    ]
    expected_count = len(scored)
    verified_count = len(usable)
    if verified_count == 0:
        logger.error(
            "metaqa verification unavailable verified=0 expected=%s verify_ms=%.0f",
            expected_count,
            verify_ms,
        )
        underlying = [item.rationale for item in scored if item.rationale]
        detail = f": {underlying[0]}" if underlying else ""
        raise MetaqaVerificationUnavailable(
            f"Mutation verification did not complete for any of {expected_count} mutations{detail}."
        )

    contributions = [item.contribution for item in usable]
    verdicts = [item.verdict for item in usable if item.verdict is not None]
    scoring_started = time.perf_counter()
    score = aggregate_score(contributions)
    classification = classify(score, settings.threshold)
    rate = not_sure_rate(verdicts) if verdicts else 0.0
    scoring_ms = (time.perf_counter() - scoring_started) * 1000
    completion = "complete" if verified_count == expected_count else "partial"
    verifier_label = verifier or "Multi-Model"
    logger.info(
        "MetaQA stage timings — Answer generation: %.1fs, Mutation generation: %.1fs, "
        "%s verification: %.1fs, MetaQA scoring: %.1fms",
        answer_ms / 1000,
        mutation_ms / 1000,
        verifier_label,
        verify_ms / 1000,
        scoring_ms,
    )
    timing = StageTiming(
        answer_ms=round(answer_ms, 1),
        mutation_ms=round(mutation_ms, 1),
        verify_ms=round(verify_ms, 1),
        total_ms=round(total_ms, 1),
        synonym_count=syn_n,
        antonym_count=ant_n,
        verify_concurrency=settings.verify_concurrency,
    )
    logger.info(
        "metaqa completed completion=%s score=%s classification=%s not_sure_rate=%s "
        "verified=%s/%s timing_ms answer=%.0f mutation=%.0f verify=%.0f total=%.0f "
        "answer_generation_ms=%.0f mutation_generation_ms=%.0f metaqa_verification_ms=%.0f",
        completion,
        score,
        classification.value,
        rate,
        verified_count,
        expected_count,
        timing.answer_ms,
        timing.mutation_ms,
        timing.verify_ms,
        timing.total_ms,
        timing.answer_ms,
        timing.mutation_ms,
        timing.verify_ms,
    )
    return DetectionResult(
        question=cleaned_question,
        base_answer=answer,
        mutations=scored,
        hallucination_score=score,
        threshold=settings.threshold,
        classification=classification,
        not_sure_rate=rate,
        generator_model=generator,
        verifier_model=verifier,
        llm_mode=settings.llm_mode,
        timing=timing,
        metaqa_completion=completion,
        verified_count=verified_count,
        expected_count=expected_count,
    )


async def verify_mutations(
    llm: LLMClient,
    *,
    question: str,
    answer: str,
    mutations: list[GeneratedMutation],
    verifier_model: str,
    concurrency: int,
    max_tokens: int | None = None,
    on_result: Callable[[int, ScoredMutation], None] | None = None,
) -> list[ScoredMutation]:
    """Verify mutations with a bounded semaphore. One failure never cancels siblings."""
    limit = max(1, int(concurrency))
    semaphore = asyncio.Semaphore(limit)
    results: list[ScoredMutation | None] = [None] * len(mutations)

    async def _one(index: int, mutation: GeneratedMutation) -> ScoredMutation:
        async with semaphore:
            try:
                result = await verify_mutation(
                    llm,
                    model=verifier_model,
                    question=question,
                    answer=answer,
                    statement=mutation.mutated_text,
                    max_tokens=max_tokens,
                )
                unavailable = result.parse_failed or result.verdict is None
                scored = score_mutation(mutation, result, unavailable=unavailable)
            except LLMTimeoutError:
                logger.warning(
                    "verification timed out mutation_index=%s; marking unavailable",
                    index,
                )
                scored = score_mutation(
                    mutation,
                    VerifierResult(
                        verdict=None,
                        rationale="Mutation verification timed out.",
                        parse_failed=True,
                        error="Timeout",
                    ),
                    unavailable=True,
                )
            except Exception as exc:
                logger.exception(
                    "verification failed mutation_index=%s; marking unavailable",
                    index,
                )
                scored = score_mutation(
                    mutation,
                    VerifierResult(
                        verdict=None,
                        rationale=f"Mutation verification failed: {exc}",
                        parse_failed=True,
                        error=str(exc),
                    ),
                    unavailable=True,
                )
            results[index] = scored
            if on_result is not None:
                on_result(index, scored)
            return scored

    await asyncio.gather(*[_one(index, item) for index, item in enumerate(mutations)])
    scored = [item for item in results if item is not None]
    available = sum(1 for item in scored if not item.unavailable)
    logger.info(
        "verification completed available=%s/%s concurrency=%s",
        available,
        len(scored),
        limit,
    )
    return scored
