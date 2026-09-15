from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import EvaluationMetric, EvaluationResult, EvaluationRun, utcnow
from app.evaluation.dataset_loader import load_dataset
from app.evaluation.ground_truth import resolve_ground_truth
from app.evaluation.metrics import (
    DEFAULT_THRESHOLDS,
    best_threshold_by_f1,
    compute_metrics,
    confusion_counts,
    outcome_label,
    sweep_thresholds,
)
from app.evaluation.schemas import DatasetExample
from app.experiment.cost import estimate_evaluation_calls
from app.llm.base import LLMClient, LLMError
from app.llm.instrumented import InstrumentedLLMClient
from app.llm.mock import MockLLMClient
from app.llm.prompts import (
    ANSWER_PROMPT_VERSION,
    MUTATION_PROMPT_VERSION,
    PROMPT_BUNDLE_VERSION,
    VERIFY_PROMPT_VERSION,
)
from app.metaqa.detector import DetectionResult, run_detection
from app.metaqa.scoring import classify
from app.services.run_service import persist_detection

logger = logging.getLogger("verifact.evaluation")

DetectFn = Callable[[DatasetExample], Awaitable[DetectionResult]]


class EvaluationConfigError(ValueError):
    """Invalid evaluation configuration."""


def llm_for_evaluation(
    base_llm: LLMClient,
    settings: Settings,
    examples: list[DatasetExample],
) -> LLMClient:
    """Use per-question mock answers/scenarios without exposing reference answers."""
    if settings.llm_mode != "mock":
        return base_llm
    answers = {item.question: item.mock_base_answer for item in examples if item.mock_base_answer}
    scenarios = {item.question: item.mock_scenario for item in examples if item.mock_scenario}
    return MockLLMClient(
        scenario=settings.mock_scenario,
        answers_by_question=answers,
        scenarios_by_question=scenarios,
    )


async def run_evaluation(
    *,
    llm: LLMClient,
    db: Session,
    settings: Settings,
    dataset: str = "pilot",
    threshold: float | None = None,
    name: str | None = None,
    detect_fn: DetectFn | None = None,
    persist_traces: bool = True,
    max_questions: int | None = None,
    confirm_live_run: bool = False,
    generator_model: str | None = None,
    verifier_model: str | None = None,
) -> EvaluationRun:
    bundle = load_dataset(dataset)
    if not bundle.examples:
        raise EvaluationConfigError("Dataset cannot be empty.")
    chosen_threshold = settings.threshold if threshold is None else threshold
    limit = max_questions or settings.max_questions
    examples = bundle.examples[:limit]
    generator = generator_model or settings.generator_model_a
    verifier = verifier_model or settings.verifier_model_a
    if settings.llm_mode == "live":
        if not settings.api_key_configured:
            raise EvaluationConfigError("Live evaluations require a configured OPENAI_API_KEY.")
        try:
            settings.require_model(generator)
            settings.require_model(verifier)
        except ValueError as exc:
            raise EvaluationConfigError(str(exc)) from exc
    estimate = estimate_evaluation_calls(
        questions=len(examples),
        mutations=settings.synonym_count + settings.antonym_count,
    )
    if settings.llm_mode == "live" and len(examples) > settings.live_unconfirmed_max_questions and not confirm_live_run:
        raise EvaluationConfigError(
            f"Live evaluation of {len(examples)} questions is estimated at {estimate['total_calls']} LLM calls. "
            "Set confirm_live_run=true to proceed, or lower max_questions."
        )
    eval_llm = InstrumentedLLMClient(llm_for_evaluation(llm, settings, examples))
    config = {
        "dataset": bundle.name,
        "dataset_version": bundle.version,
        "generator_model": generator,
        "verifier_model": verifier,
        "synonym_count": settings.synonym_count,
        "antonym_count": settings.antonym_count,
        "threshold": chosen_threshold,
        "llm_mode": settings.llm_mode,
        "max_questions": limit,
        "estimated_llm_calls": estimate,
        "sweep": list(DEFAULT_THRESHOLDS),
        "best_threshold_note": "Best F1 is an experimental finding; production threshold is unchanged.",
        "ground_truth_policy": (
            "Reliable/Hallucinated labels describe generated-answer correctness. "
            "Needs Review items are excluded from automatic P/R/F1."
        ),
        "llm": {
            "provider": settings.llm_provider,
            "temperature": settings.llm_temperature,
            "max_output_tokens": settings.llm_max_output_tokens,
            "prompt_bundle": PROMPT_BUNDLE_VERSION,
            "answer_prompt": ANSWER_PROMPT_VERSION,
            "mutation_prompt": MUTATION_PROMPT_VERSION,
            "verify_prompt": VERIFY_PROMPT_VERSION,
        },
    }
    run = EvaluationRun(
        name=name or f"{bundle.name} @ {chosen_threshold:.2f}",
        dataset_name=bundle.name,
        dataset_version=bundle.version,
        generator_model=generator,
        verifier_model=verifier,
        synonym_count=settings.synonym_count,
        antonym_count=settings.antonym_count,
        mutation_count=settings.synonym_count + settings.antonym_count,
        threshold=chosen_threshold,
        total_examples=len(examples),
        status="running",
        llm_mode=settings.llm_mode,
        config_json=json.dumps(config),
    )
    db.add(run)
    db.flush()
    logger.info(
        "evaluation started id=%s dataset=%s examples=%s llm_mode=%s",
        run.id,
        bundle.name,
        len(examples),
        settings.llm_mode,
    )

    async def _detect(example: DatasetExample) -> DetectionResult:
        return await run_detection(
            eval_llm,
            question=example.question,
            settings=settings,
            generator_model=generator,
            verifier_model=verifier,
        )

    detect = detect_fn or _detect
    scored_rows: list[dict[str, Any]] = []

    try:
        for index, example in enumerate(examples):
            try:
                detection = await detect(example)
            except (LLMError, ValueError):
                logger.exception("evaluation example failed question_id=%s", example.id)
                continue
            detect_run_id = None
            if persist_traces:
                saved = persist_detection(db, detection)
                detect_run_id = saved.run_id
            predicted = classify(detection.hallucination_score, chosen_threshold)
            decision = resolve_ground_truth(detection.base_answer.text, example)
            if decision.is_review or decision.label is None:
                actual_value = "Needs Review"
                outcome = "Needs Review"
            else:
                actual_value = decision.label.value
                outcome = outcome_label(decision.label, predicted)
            row = EvaluationResult(
                evaluation_run_id=run.id,
                question_id=example.id,
                question=example.question,
                reference_answer=example.reference_answer,
                generated_answer=detection.base_answer.text,
                actual_label=actual_value,
                predicted_label=predicted.value,
                hallucination_score=detection.hallucination_score,
                category=example.category,
                outcome=outcome,
                ground_truth_source=decision.source.value,
                run_id=detect_run_id,
                position=index,
            )
            run.results.append(row)
            scored_rows.append(
                {
                    "actual": None if actual_value == "Needs Review" else decision.label,
                    "score": detection.hallucination_score,
                    "predicted": predicted,
                    "category": example.category,
                    "outcome": outcome,
                }
            )
            db.flush()
            if settings.llm_mode == "live":
                db.commit()

        labeled = [item for item in scored_rows if item["actual"] is not None]
        actuals = [item["actual"] for item in labeled]
        scores = [item["score"] for item in labeled]
        predictions = [item["predicted"] for item in labeled]
        primary = compute_metrics(confusion_counts(actuals, predictions)) if labeled else compute_metrics(
            confusion_counts([], [])
        )
        sweep = sweep_thresholds(actuals, scores) if labeled else [(value, primary) for value in DEFAULT_THRESHOLDS]
        best = best_threshold_by_f1(sweep)
        config["best_threshold_by_f1"] = best
        config["call_stats"] = eval_llm.stats()
        run.config_json = json.dumps(config)
        run.category_metrics_json = json.dumps(_category_breakdown(labeled))
        run.completed_examples = len(scored_rows)
        run.review_examples = sum(1 for item in scored_rows if item["outcome"] == "Needs Review")
        run.status = "completed"
        run.completed_at = utcnow()

        run.metrics.append(_metric_row(run.id, chosen_threshold, primary, is_primary=True))
        for threshold_value, metrics in sweep:
            if abs(threshold_value - chosen_threshold) < 1e-9:
                continue
            run.metrics.append(_metric_row(run.id, threshold_value, metrics, is_primary=False))
        db.flush()
        db.refresh(run)
        logger.info(
            "evaluation completed id=%s included=%s review=%s f1=%s",
            run.id,
            primary.included_examples,
            run.review_examples,
            primary.f1,
        )
        return run
    except Exception:
        run.status = "failed"
        run.completed_at = utcnow()
        db.flush()
        logger.exception("evaluation failed id=%s", run.id)
        raise


def _metric_row(run_id: str, threshold: float, metrics, *, is_primary: bool) -> EvaluationMetric:
    return EvaluationMetric(
        evaluation_run_id=run_id,
        threshold=threshold,
        tp=metrics.tp,
        tn=metrics.tn,
        fp=metrics.fp,
        fn=metrics.fn,
        accuracy=metrics.accuracy,
        precision=metrics.precision,
        recall=metrics.recall,
        f1=metrics.f1,
        specificity=metrics.specificity,
        fpr=metrics.fpr,
        fnr=metrics.fnr,
        included_examples=metrics.included_examples,
        is_primary=is_primary,
    )


def _category_breakdown(labeled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in labeled:
        groups[str(item["category"])].append(item)
    rows: list[dict[str, Any]] = []
    for category, items in sorted(groups.items()):
        actuals = [item["actual"] for item in items]
        predictions = [item["predicted"] for item in items]
        metrics = compute_metrics(confusion_counts(actuals, predictions))
        mean_score = round(sum(float(item["score"]) for item in items) / len(items), 4)
        rows.append(
            {
                "category": category,
                "count": len(items),
                "accuracy": metrics.accuracy,
                "mean_hallucination_score": mean_score,
                "fp": metrics.fp,
                "fn": metrics.fn,
            }
        )
    return rows
