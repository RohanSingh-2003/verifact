from __future__ import annotations

import json

import logging

import time

from collections import defaultdict

from collections.abc import Awaitable, Callable

from typing import Any, Literal

from sqlalchemy.orm import Session

from app.config import Settings

from app.database.models import EvaluationMetric, EvaluationResult, EvaluationRun, Run, utcnow

from app.evaluation.dataset_loader import load_dataset

from app.evaluation.ground_truth import resolve_ground_truth

from app.evaluation.schemas import GroundTruthSource

from app.evaluation.metrics import (

    DEFAULT_THRESHOLDS,

    ConfusionCounts,

    MetricSet,

    best_threshold_by_f1,

    compute_metrics,

    confusion_counts,

    outcome_label,

    sweep_thresholds,

)

from app.evaluation.schemas import DatasetExample

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

from app.metaqa.scoring import Classification, classify

from app.schemas.detect import RunStatus

from app.services.run_service import persist_detection

from app.web_search.base import WebSearchClient

logger = logging.getLogger("verifact.evaluation")

DetectFn = Callable[[DatasetExample], Awaitable[DetectionResult]]

class EvaluationConfigError(ValueError):

    """Invalid evaluation configuration."""

def estimate_evaluation_calls(

    *,

    questions: int,

    mutations: int = 10,

    evaluate_web: bool = False,

    evaluate_multi: bool = False,

) -> dict[str, int]:

    """Estimate total LLM calls required for an evaluation run across enabled components."""

    # Generator: 1 call per question

    # MetaQA: 1 mutation generation + mutations verifications

    metaqa_calls = 2 + mutations

    web_calls = 3 if evaluate_web else 0  # 1 claim extraction + ~2 batch/claim verifications

    multi_calls = 4 if evaluate_multi else 0  # 4 independent verifier models

    per_question = metaqa_calls + web_calls + multi_calls

    return {

        "questions": questions,

        "mutations": mutations,

        "metaqa_calls_per_question": metaqa_calls,

        "web_calls_per_question": web_calls,

        "multi_calls_per_question": multi_calls,

        "calls_per_question": per_question,

        "total_calls": per_question * questions,

    }

def llm_for_evaluation(

    base_llm: LLMClient,

    settings: Settings,

    examples: list[DatasetExample],

) -> LLMClient:

    """Use per-question mock answers/scenarios without exposing reference answers."""

    if settings.llm_mode != "mock":

        return base_llm

    if type(base_llm) is not MockLLMClient:

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

    search_client: WebSearchClient | None = None,

    evaluate_web_evidence: bool | None = None,

    evaluate_multi_model: bool | None = None,

    min_completed_verifiers: int | None = None,

    benchmark_mode: Literal["formal", "legacy"] = "legacy",

    evaluate_judge: bool | None = None,

    judge_client: Any | None = None,

) -> EvaluationRun:

    """Run an automated benchmark evaluation measuring all components against the same generated answer."""

    bundle = load_dataset(dataset)

    if not bundle.examples:

        raise EvaluationConfigError("Dataset cannot be empty.")

    chosen_threshold = settings.threshold if threshold is None else threshold

    limit = max_questions or settings.max_questions

    examples = bundle.examples[:limit]

    generator = generator_model or getattr(settings, "generator_model", "gemma4:26b")

    verifier = verifier_model or getattr(settings, "verifier_model", "gemma4:26b")

    # Determine component enablement:

    # When a custom detect_fn is passed in legacy unit tests, default extra components to False unless requested.

    # In standard evaluation (detect_fn is None), default both to True.

    run_web = evaluate_web_evidence if evaluate_web_evidence is not None else (detect_fn is None)

    run_multi = evaluate_multi_model if evaluate_multi_model is not None else (detect_fn is None)

    if settings.llm_mode == "live":

        if not settings.api_key_configured:

            raise EvaluationConfigError("Live evaluations require configured cloud LLM credentials.")

        try:

            settings.require_model(generator)

            settings.require_model(verifier)

        except ValueError as exc:

            raise EvaluationConfigError(str(exc)) from exc

    estimate = estimate_evaluation_calls(

        questions=len(examples),

        mutations=settings.synonym_count + settings.antonym_count,

        evaluate_web=run_web,

        evaluate_multi=run_multi,

    )

    if settings.llm_mode == "live" and len(examples) > settings.live_unconfirmed_max_questions and not confirm_live_run:

        raise EvaluationConfigError(

            f"Live evaluation of {len(examples)} questions is estimated at {estimate['total_calls']} LLM calls. "

            "Set confirm_live_run=true to proceed, or lower max_questions."

        )

    eval_llm = InstrumentedLLMClient(llm_for_evaluation(llm, settings, examples))

    # Resolve judge client for independent ground truth evaluation

    run_judge = evaluate_judge if evaluate_judge is not None else getattr(settings, "ground_truth_judge_enabled", False)

    effective_judge = None

    if run_judge:

        from app.evaluation.gemini_judge import GeminiJudgeClient

        if judge_client is not None:

            effective_judge = judge_client

        else:

            effective_judge = GeminiJudgeClient(
                api_key=settings.openrouter_api_key,
                model=getattr(settings, "ground_truth_judge_model", "") or getattr(settings, "gemini_judge_model", ""),
                timeout_seconds=getattr(settings, "ground_truth_judge_timeout_seconds", getattr(settings, "gemini_judge_timeout_seconds", 30.0)),
                base_url=getattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1"),
                settings=settings,
                test_llm=eval_llm if settings.llm_mode == "mock" else None,
            )

    # Resolve search client for web evidence

    effective_search: WebSearchClient | None = search_client

    if effective_search is None and run_web:

        if not settings.web_evidence_enabled:

            effective_search = None

        elif settings.llm_mode == "mock":

            from app.web_search.mock import MockTavilyClient

            effective_search = MockTavilyClient()

        elif settings.tavily_configured:

            from app.web_evidence.pipeline import build_web_search_client

            effective_search = build_web_search_client(settings)

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

        "evaluate_web_evidence": run_web,

        "evaluate_multi_model": run_multi,

        "estimated_llm_calls": estimate,

        "sweep": list(DEFAULT_THRESHOLDS),

        "best_threshold_note": "Best F1 is an experimental finding; production threshold is unchanged.",

        "ground_truth_policy": (

            "Reliable/Hallucinated labels describe generated-answer correctness. "

            "Needs Review items and abstentions are excluded from automatic P/R/F1."

        ),

        "positive_class": "Hallucinated (the error VeriFact aims to detect)",

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

        "evaluation started id=%s dataset=%s examples=%s web=%s multi=%s llm_mode=%s",

        run.id,

        bundle.name,

        len(examples),

        run_web,

        run_multi,

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

            start_example_time = time.perf_counter()

            try:

                detection = await detect(example)

            except (LLMError, ValueError):

                logger.exception("evaluation example failed question_id=%s", example.id)

                continue

            generated_text = detection.base_answer.text

            metaqa_score = detection.hallucination_score

            metaqa_pred = classify(metaqa_score, chosen_threshold)

            # Execute Gemini Judge if enabled

            judge_verdict = None

            if run_judge and effective_judge is not None:

                judge_verdict = await effective_judge.evaluate_answer(

                    question=example.question,

                    generated_answer=generated_text,

                    reference_answer=example.reference_answer,

                    aliases=example.aliases,

                    correct_answers=getattr(example, "correct_answers", None),

                    incorrect_answers=getattr(example, "incorrect_answers", None),

                    context=getattr(example, "context", None),

                    supporting_evidence=getattr(example, "supporting_evidence", None),

                )

            # Resolve ground truth against the generated answer

            decision = resolve_ground_truth(

                generated_text,

                example,

                mode=benchmark_mode,

            )

            if decision.is_review or decision.label is None:

                actual_value = "Needs Review"

                actual_label = None

            else:

                actual_value = decision.label.value

                actual_label = decision.label

            # ── Component B: Web Evidence ─────────────────────────────────────

            web_result = None

            web_score = None

            web_verdict = None

            web_pred = None

            web_status = "not_run"

            if run_web:

                if effective_search is not None:

                    try:

                        from app.web_evidence.pipeline import run_web_evidence

                        web_result = await run_web_evidence(

                            eval_llm,

                            effective_search,

                            question=example.question,

                            answer=generated_text,

                            settings=settings,

                            model=verifier,

                        )

                        web_status = web_result.status.value

                        web_score = web_result.consistency_score

                        web_verdict = web_result.consistency_verdict

                        # Prediction mapping:

                        # Contradictions -> HALLUCINATED

                        # Supported without contradictions -> RELIABLE

                        # Insufficient / unavailable / unassessed -> None (Abstain)

                        if web_result.contradicted_claims > 0:

                            web_pred = Classification.HALLUCINATED

                        elif web_result.supported_claims > 0 and web_result.contradicted_claims == 0:

                            web_pred = Classification.RELIABLE

                        else:

                            web_pred = None

                    except Exception as exc:

                        logger.warning("Web evidence evaluation error for question %s: %s", example.id, exc)

                        web_status = "failed"

                else:

                    web_status = "unavailable"

            # ── Component C: Multi-model Verification ────────────────────────

            ai_verdicts = None

            multi_summary = None

            multi_status = "not_run"

            multi_consensus = None

            multi_pred = None

            multi_agreement = None

            if run_multi:

                try:

                    from app.llm.registry import resolve_model_id

                    from app.services.independent_verifiers import (

                        build_multi_model_summary,

                        evaluate_all_independent_verifiers,

                    )

                    canonical_gen = resolve_model_id(generator) or "gemma"

                    claim_texts = [c.text for c in web_result.claims] if web_result and web_result.claims else None

                    evidence_snippet = None

                    if web_result and web_result.claims:

                        snippets = [s.snippet for c in web_result.claims for s in c.sources if s.snippet]

                        if snippets:

                            evidence_snippet = " ".join(snippets[:5])

                    ai_verdicts = await evaluate_all_independent_verifiers(

                        question=example.question,

                        answer=generated_text,

                        selected_answer_model_id=canonical_gen,

                        settings=settings,

                        test_llm=eval_llm,

                        claims=claim_texts,

                        web_evidence=evidence_snippet,

                    )

                    quorum = min_completed_verifiers or getattr(settings, "min_completed_verifiers", 2)

                    multi_summary = build_multi_model_summary(ai_verdicts, min_quorum=quorum)

                    completed = multi_summary.completed_verifiers

                    failed = multi_summary.failed_count

                    total = multi_summary.total_verifiers

                    if completed < quorum:

                        if completed == 0:

                            multi_status = "failed" if failed > 0 else "pending"

                        else:

                            multi_status = "insufficient_quorum"

                        multi_pred = None

                        multi_consensus = multi_summary.agreement_state

                    else:

                        multi_status = "completed"

                        multi_consensus = multi_summary.agreement_state

                        # Decision logic when quorum is satisfied:

                        if completed == 2:

                            if (

                                multi_summary.correct_count == 2

                                and multi_summary.incorrect_count == 0

                                and multi_summary.uncertain_count == 0

                            ):

                                multi_pred = Classification.RELIABLE

                            elif (

                                multi_summary.incorrect_count == 2

                                and multi_summary.correct_count == 0

                                and multi_summary.uncertain_count == 0

                            ):

                                multi_pred = Classification.HALLUCINATED

                            else:

                                # Disagreement, or uncertain response among the 2 -> Abstain

                                multi_pred = None

                        else:

                            # 3 or 4 valid responses: apply consensus logic with quorum enforcement

                            if (

                                multi_summary.incorrect_count > multi_summary.correct_count

                                and multi_summary.incorrect_count >= quorum

                            ):

                                multi_pred = Classification.HALLUCINATED

                            elif (

                                multi_summary.correct_count > multi_summary.incorrect_count

                                and multi_summary.correct_count >= quorum

                            ):

                                multi_pred = Classification.RELIABLE

                            else:

                                multi_pred = None

                    if total > 0:

                        multi_agreement = round(

                            max(multi_summary.correct_count, multi_summary.incorrect_count) / total,

                            4,

                        )

                except Exception as exc:

                    logger.warning("Multi-model evaluation error for question %s: %s", example.id, exc)

                    multi_status = "failed"

            # ── Component D: Combined Assessment ─────────────────────────────

            from app.services.verification_summary import (

                MetaqaSignal,

                OverallVerdict,

                WebSignal,

                compute_overall_assessment,

                metaqa_signal_from_run,

                web_signal_from_evidence,

            )

            metaqa_sig = metaqa_signal_from_run(

                status=RunStatus.COMPLETED,

                classification=metaqa_pred,

                score=metaqa_score,

            )

            web_sig = web_signal_from_evidence(web_result)

            overall_verdict, _, _, _, combined_risk, web_risk = compute_overall_assessment(

                metaqa_signal=metaqa_sig,

                metaqa_score=metaqa_score,

                web_signal=web_sig,

                web_evidence=web_result,

            )

            combined_pred = None

            if overall_verdict == OverallVerdict.POTENTIALLY_HALLUCINATED:

                combined_pred = Classification.HALLUCINATED

            elif overall_verdict == OverallVerdict.LIKELY_RELIABLE:

                combined_pred = Classification.RELIABLE

            # ── Outcome labels relative to ground truth ──────────────────────

            if actual_label is None:

                metaqa_outcome = "Needs Review"

                web_outcome = "Needs Review"

                multi_outcome = "Needs Review"

                combined_outcome = "Needs Review"

            else:

                metaqa_outcome = outcome_label(actual_label, metaqa_pred)

                web_outcome = outcome_label(actual_label, web_pred) if web_pred is not None else "Abstained"

                multi_outcome = outcome_label(actual_label, multi_pred) if multi_pred is not None else "Abstained"

                combined_outcome = outcome_label(actual_label, combined_pred) if combined_pred is not None else "Needs Review"

            # ── Trace persistence (if enabled) ───────────────────────────────

            detect_run_id = None

            if persist_traces:

                saved = persist_detection(db, detection)

                detect_run_id = saved.run_id

                if web_result is not None:

                    from app.services.run_service import persist_web_evidence_result

                    persist_web_evidence_result(db, detect_run_id, web_result)

                if ai_verdicts is not None:

                    from app.services.independent_verifiers import persist_independent_verdicts

                    persist_independent_verdicts(db, detect_run_id, ai_verdicts)

                run_row = db.get(Run, detect_run_id)

                if run_row:

                    run_row.combined_risk_score = combined_risk

                    run_row.overall_verdict = overall_verdict.value

            latency_ms = round((time.perf_counter() - start_example_time) * 1000, 2)

            # Detailed JSON structure for complete experiment reproducibility

            details_payload = {

                "metaqa": {

                    "score": metaqa_score,

                    "classification": metaqa_pred.value,

                    "mutations_count": len(detection.mutations),

                    "verified_count": detection.verified_count,

                    "expected_count": detection.expected_count,

                    "not_sure_rate": detection.not_sure_rate,

                    "completion": detection.metaqa_completion,

                },

                "web_evidence": {

                    "status": web_status,

                    "consistency_score": web_score,

                    "consistency_verdict": web_verdict,

                    "total_claims": web_result.total_claims if web_result else 0,

                    "supported_claims": web_result.supported_claims if web_result else 0,

                    "contradicted_claims": web_result.contradicted_claims if web_result else 0,

                    "insufficient_claims": web_result.insufficient_claims if web_result else 0,

                    "unassessed_claims": web_result.unassessed_claims if web_result else 0,

                    "claims": [c.to_dict() for c in web_result.claims] if web_result else [],

                },

                "multi_model": {

                    "status": multi_status,

                    "prediction": multi_pred.value if multi_pred is not None else None,

                    "agreement_state": multi_consensus,

                    "agreement_ratio": multi_agreement,

                    "total_verifiers": multi_summary.total_verifiers if multi_summary else 0,

                    "completed_verifiers": multi_summary.completed_verifiers if multi_summary else 0,

                    "failed_verifiers": multi_summary.failed_count if multi_summary else 0,

                    "required_quorum": quorum if run_multi else None,

                    "multi_model_abstained": multi_pred is None if run_multi else False,

                    "correct_count": multi_summary.correct_count if multi_summary else 0,

                    "incorrect_count": multi_summary.incorrect_count if multi_summary else 0,

                    "uncertain_count": multi_summary.uncertain_count if multi_summary else 0,

                    "failed_count": multi_summary.failed_count if multi_summary else 0,

                    "verdicts": [v.model_dump() for v in ai_verdicts] if ai_verdicts else [],

                },

                "combined": {

                    "combined_risk_score": combined_risk,

                    "overall_verdict": overall_verdict.value,

                    "metaqa_signal": metaqa_sig.value,

                    "web_signal": web_sig.value,

                },

                "gemini_judge": {

                    "status": judge_verdict.status if judge_verdict else "not_run",

                    "label": judge_verdict.label if judge_verdict else None,

                    "reasoning_summary": judge_verdict.reasoning_summary if judge_verdict else "",

                    "supported_claims": judge_verdict.supported_claims if judge_verdict else [],

                    "contradicted_claims": judge_verdict.contradicted_claims if judge_verdict else [],

                    "unsupported_claims": judge_verdict.unsupported_claims if judge_verdict else [],

                    "evidence_used": judge_verdict.evidence_used if judge_verdict else [],

                    "confidence": judge_verdict.confidence if judge_verdict else None,

                    "error": judge_verdict.error if judge_verdict else None,

                } if run_judge else None,

                "latency_ms": latency_ms,

            }

            row = EvaluationResult(

                evaluation_run_id=run.id,

                question_id=example.id,

                question=example.question,

                reference_answer=example.reference_answer,

                generated_answer=generated_text,

                actual_label=actual_value,

                predicted_label=metaqa_pred.value,

                hallucination_score=metaqa_score,

                category=example.category,

                outcome=metaqa_outcome,

                ground_truth_source=decision.source.value,

                run_id=detect_run_id,

                position=index,

                # Component fields

                metaqa_score=metaqa_score,

                metaqa_prediction=metaqa_pred.value,

                metaqa_outcome=metaqa_outcome,

                web_evidence_score=web_score,

                web_evidence_verdict=web_verdict,

                web_evidence_prediction=web_pred.value if web_pred is not None else None,

                web_evidence_status=web_status,

                web_evidence_outcome=web_outcome,

                multi_model_consensus=multi_consensus,

                multi_model_prediction=multi_pred.value if multi_pred is not None else None,

                multi_model_status=multi_status,

                multi_model_agreement=multi_agreement,

                multi_model_outcome=multi_outcome,

                combined_risk_score=combined_risk,

                combined_verdict=overall_verdict.value,

                combined_prediction=combined_pred.value if combined_pred is not None else None,

                combined_outcome=combined_outcome,

                component_details_json=json.dumps(details_payload),

                latency_ms=latency_ms,

                judge_label=judge_verdict.label if judge_verdict else None,

                judge_reasoning=judge_verdict.reasoning_summary if judge_verdict else None,

                judge_confidence=judge_verdict.confidence if judge_verdict else None,

                judge_status=judge_verdict.status if judge_verdict else "not_run",

                validation_status=(

                    "adjudicated" if decision.source == GroundTruthSource.ADJUDICATED

                    else ("validated" if decision.source == GroundTruthSource.VALIDATED

                    else ("preliminary_judge" if judge_verdict and judge_verdict.status == "completed"

                    else ("legacy_inferred" if decision.source == GroundTruthSource.LEGACY_INFERRED

                    else "unreviewed")))

                ),

            )

            run.results.append(row)

            scored_rows.append(

                {

                    "actual": actual_label,

                    "score": metaqa_score,

                    "predicted": metaqa_pred,

                    "category": example.category,

                    "outcome": metaqa_outcome,

                    "web_score": web_score,

                    "web_pred": web_pred,

                    "web_outcome": web_outcome,

                    "multi_pred": multi_pred,

                    "multi_outcome": multi_outcome,

                    "combined_pred": combined_pred,

                    "combined_outcome": combined_outcome,

                    "ground_truth_source": decision.source.value,

                    "judge_verdict": judge_verdict,

                }

            )

            db.flush()

            if settings.llm_mode == "live":

                db.commit()

        # ── Independent Metrics Computation for All Components ───────────────

        total_eval_examples = len(scored_rows)

        labeled = [item for item in scored_rows if item["actual"] is not None]

        total_labeled_count = len(labeled)

        # 1. MetaQA Metrics

        actuals_metaqa = [item["actual"] for item in labeled]

        scores_metaqa = [item["score"] for item in labeled]

        predictions_metaqa = [item["predicted"] for item in labeled]

        metaqa_primary = compute_metrics(confusion_counts(actuals_metaqa, predictions_metaqa)) if labeled else compute_metrics(confusion_counts([], []))

        sweep = sweep_thresholds(actuals_metaqa, scores_metaqa) if labeled else [(val, metaqa_primary) for val in DEFAULT_THRESHOLDS]

        best_threshold = best_threshold_by_f1(sweep)

        # 2. Web Evidence Metrics

        web_eval_items = [item for item in labeled if item["web_pred"] is not None]

        actuals_web = [item["actual"] for item in web_eval_items]

        predictions_web = [item["web_pred"] for item in web_eval_items]

        web_metrics = compute_metrics(confusion_counts(actuals_web, predictions_web)) if web_eval_items else compute_metrics(confusion_counts([], []))

        web_abstained = total_labeled_count - len(web_eval_items)

        web_coverage = round(len(web_eval_items) / total_labeled_count, 4) if total_labeled_count > 0 else 0.0

        # 3. Multi-model Metrics

        multi_eval_items = [item for item in labeled if item["multi_pred"] is not None]

        actuals_multi = [item["actual"] for item in multi_eval_items]

        predictions_multi = [item["multi_pred"] for item in multi_eval_items]

        multi_metrics = compute_metrics(confusion_counts(actuals_multi, predictions_multi)) if multi_eval_items else compute_metrics(confusion_counts([], []))

        multi_abstained = total_labeled_count - len(multi_eval_items)

        multi_coverage = round(len(multi_eval_items) / total_labeled_count, 4) if total_labeled_count > 0 else 0.0

        # 4. Combined VeriFact Metrics

        combined_eval_items = [item for item in labeled if item["combined_pred"] is not None]

        actuals_combined = [item["actual"] for item in combined_eval_items]

        predictions_combined = [item["combined_pred"] for item in combined_eval_items]

        combined_metrics = compute_metrics(confusion_counts(actuals_combined, predictions_combined)) if combined_eval_items else compute_metrics(confusion_counts([], []))

        combined_abstained = total_labeled_count - len(combined_eval_items)

        combined_coverage = round(len(combined_eval_items) / total_labeled_count, 4) if total_labeled_count > 0 else 0.0

        # Assemble summary metrics dictionary

        component_metrics_summary = {

            "metaqa": {

                **metaqa_primary.as_dict(),

                "total_examples": total_eval_examples,

                "coverage": 1.0,

                "abstained_examples": 0,

            },

            "web_evidence": {

                **web_metrics.as_dict(),

                "total_examples": total_eval_examples,

                "coverage": web_coverage,

                "abstained_examples": web_abstained,

                "status": "enabled" if run_web else "not_run",

            },

            "multi_model": {

                **multi_metrics.as_dict(),

                "total_examples": total_eval_examples,

                "coverage": multi_coverage,

                "abstained_examples": multi_abstained,

                "required_quorum": min_completed_verifiers or getattr(settings, "min_completed_verifiers", 2),

                "status": "enabled" if run_multi else "not_run",

            },

            "combined": {

                **combined_metrics.as_dict(),

                "total_examples": total_eval_examples,

                "coverage": combined_coverage,

                "abstained_examples": combined_abstained,

                "status": "computed",

            },

        }

        component_metrics_summary["research_protocol"] = {

            "benchmark_mode": benchmark_mode,

            "judge_evaluated": run_judge,

            "validated_examples_count": sum(1 for item in scored_rows if item.get("ground_truth_source") in {"manual", "validated", "adjudicated"}),

            "unreviewed_examples_count": sum(1 for item in scored_rows if item.get("ground_truth_source") in {"unvalidated", "legacy_inferred", "judge_preliminary"}),

            "review_examples_count": sum(1 for item in scored_rows if item.get("ground_truth_source") == "needs_review"),

        }

        config["best_threshold_by_f1"] = best_threshold

        config["call_stats"] = eval_llm.stats()

        config["component_metrics"] = component_metrics_summary

        config["benchmark_mode"] = benchmark_mode

        run.config_json = json.dumps(config)

        run.summary_metrics_json = json.dumps(component_metrics_summary)

        run.category_metrics_json = json.dumps(_category_breakdown(labeled))

        run.completed_examples = len(scored_rows)

        run.review_examples = sum(1 for item in scored_rows if item["outcome"] == "Needs Review")

        run.status = "completed"

        run.completed_at = utcnow()

        # Primary MetaQA metric row

        run.metrics.append(

            _metric_row(

                run.id,

                chosen_threshold,

                metaqa_primary,

                is_primary=True,

                component="metaqa",

                coverage=1.0,

                abstained_examples=0,

            )

        )

        # MetaQA threshold sweep

        for threshold_value, metrics in sweep:

            if abs(threshold_value - chosen_threshold) < 1e-9:

                continue

            run.metrics.append(

                _metric_row(

                    run.id,

                    threshold_value,

                    metrics,

                    is_primary=False,

                    component="metaqa",

                    coverage=1.0,

                    abstained_examples=0,

                )

            )

        # Component metric rows

        if run_web:

            run.metrics.append(

                _metric_row(

                    run.id,

                    chosen_threshold,

                    web_metrics,

                    is_primary=False,

                    component="web_evidence",

                    coverage=web_coverage,

                    abstained_examples=web_abstained,

                )

            )

        if run_multi:

            run.metrics.append(

                _metric_row(

                    run.id,

                    chosen_threshold,

                    multi_metrics,

                    is_primary=False,

                    component="multi_model",

                    coverage=multi_coverage,

                    abstained_examples=multi_abstained,

                )

            )

        run.metrics.append(

            _metric_row(

                run.id,

                chosen_threshold,

                combined_metrics,

                is_primary=False,

                component="combined",

                coverage=combined_coverage,

                abstained_examples=combined_abstained,

            )

        )

        db.flush()

        db.refresh(run)

        logger.info(

            "evaluation completed id=%s metaqa_f1=%.4f web_f1=%.4f multi_f1=%.4f combined_f1=%.4f",

            run.id,

            metaqa_primary.f1,

            web_metrics.f1,

            multi_metrics.f1,

            combined_metrics.f1,

        )

        return run

    except Exception:

        run.status = "failed"

        run.completed_at = utcnow()

        db.flush()

        logger.exception("evaluation failed id=%s", run.id)

        raise

def _metric_row(

    run_id: str,

    threshold: float,

    metrics: MetricSet,

    *,

    is_primary: bool,

    component: str = "metaqa",

    coverage: float = 1.0,

    abstained_examples: int = 0,

) -> EvaluationMetric:

    return EvaluationMetric(

        evaluation_run_id=run_id,

        component=component,

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

        coverage=coverage,

        abstained_examples=abstained_examples,

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

