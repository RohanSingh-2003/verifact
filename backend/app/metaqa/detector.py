from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.config import Settings
from app.llm.base import LLMClient, LLMError
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


@dataclass(frozen=True)
class BaseAnswer:
    text: str
    model: str


@dataclass(frozen=True)
class ScoredMutation:
    mutation: GeneratedMutation
    verdict: Verdict
    expected: Verdict
    contribution: float
    rationale: str
    parse_failed: bool = False


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
    llm_mode: str


def score_mutation(mutation: GeneratedMutation, result: VerifierResult) -> ScoredMutation:
    expected = expected_verdict(mutation.type)
    contribution = contribution_score(mutation.type, result.verdict)
    return ScoredMutation(
        mutation=mutation,
        verdict=result.verdict,
        expected=expected,
        contribution=contribution,
        rationale=result.rationale,
        parse_failed=result.parse_failed,
    )


async def generate_answer(llm: LLMClient, question: str, model: str) -> BaseAnswer:
    text = await llm.complete_text(
        model=model,
        system_prompt=ANSWER_SYSTEM,
        user_prompt=ANSWER_USER.format(question=question),
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
) -> DetectionResult:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("Question must not be empty.")

    generator = settings.require_model(generator_model or settings.generator_model)
    verifier = settings.require_model(verifier_model or settings.verifier_model)
    verifier_client = verifier_llm or llm
    logger.info(
        "run started generator=%s verifier=%s llm_mode=%s question_len=%s",
        generator,
        verifier,
        settings.llm_mode,
        len(cleaned_question),
    )

    try:
        answer = await generate_answer(llm, cleaned_question, generator)
        logger.info("base answer generated")
        mutations = await generate_mutations(
            llm,
            model=generator,
            question=cleaned_question,
            answer=answer.text,
            synonym_count=settings.synonym_count,
            antonym_count=settings.antonym_count,
        )
        scored = await verify_mutations(
            verifier_client,
            question=cleaned_question,
            answer=answer.text,
            mutations=mutations,
            verifier_model=verifier,
            concurrency=settings.verify_concurrency,
        )
        malformed = sum(1 for item in scored if item.parse_failed)
        if malformed:
            logger.warning("malformed verdict count=%s of %s", malformed, len(scored))
        contributions = [item.contribution for item in scored]
        verdicts = [item.verdict for item in scored]
        score = aggregate_score(contributions)
        classification = classify(score, settings.threshold)
        rate = not_sure_rate(verdicts)
        logger.info(
            "run completed score=%s classification=%s not_sure_rate=%s mutations=%s",
            score,
            classification.value,
            rate,
            len(scored),
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
        )
    except Exception:
        logger.exception("run failed generator=%s verifier=%s", generator, verifier)
        raise


async def verify_mutations(
    llm: LLMClient,
    *,
    question: str,
    answer: str,
    mutations: list[GeneratedMutation],
    verifier_model: str,
    concurrency: int,
) -> list[ScoredMutation]:
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(mutation: GeneratedMutation) -> ScoredMutation:
        async with semaphore:
            try:
                result = await verify_mutation(
                    llm,
                    model=verifier_model,
                    question=question,
                    answer=answer,
                    statement=mutation.mutated_text,
                )
            except Exception:
                logger.exception("verification failed; recording NOT SURE")
                result = VerifierResult(verdict=Verdict.NOT_SURE, rationale="", parse_failed=True)
            return score_mutation(mutation, result)

    scored = list(await asyncio.gather(*[_one(item) for item in mutations]))
    logger.info("verification completed count=%s", len(scored))
    return scored
