from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database.models import (
    Experiment,
    ExperimentCondition,
    ExperimentGeneration,
    ExperimentMutation,
    ExperimentVerification,
    utcnow,
)
from app.evaluation.dataset_loader import load_dataset
from app.evaluation.schemas import DatasetExample
from app.evaluation.metrics import sweep_thresholds
from app.experiment.analysis import (
    actual_label_for,
    category_analysis,
    group_condition_rows,
    key_finding_text,
    paired_rows,
    pair_type_for,
    research_summary,
    self_verification_block,
    summarize_condition,
)
from app.experiment.cost import estimate_experiment_calls
from app.llm.base import LLMClient, LLMError
from app.llm.instrumented import InstrumentedLLMClient
from app.llm.mock import DEFAULT_MUTATIONS, SCENARIO_VERDICTS, MockLLMClient
from app.llm.prompts import (
    ANSWER_PROMPT_VERSION,
    MUTATION_PROMPT_VERSION,
    PROMPT_BUNDLE_VERSION,
    VERIFY_PROMPT_VERSION,
)
from app.metaqa.detector import generate_answer, verify_mutations
from app.metaqa.mutation import generate_mutations, hash_mutation_set
from app.metaqa.scoring import aggregate_score, classify, not_sure_rate
from app.schemas.experiment import ExperimentConfigError, ExperimentIntegrityError, ExperimentRunRequest

logger = logging.getLogger("verifact.experiment")

MOCK_MODEL_A = "model-a"
MOCK_MODEL_B = "model-b"


def llm_for_experiment(
    base_llm: LLMClient,
    settings: Settings,
    examples: list[DatasetExample],
    generator_models: list[str],
) -> LLMClient:
    if settings.llm_mode != "mock":
        return base_llm
    answers_a = {
        item.question: item.mock_base_answer or f"Mock A answer: {item.question}"
        for item in examples
    }
    answers_b = {
        item.question: (
            f"Alternative statement: {item.mock_base_answer}"
            if item.mock_base_answer
            else f"Mock B answer: {item.question}"
        )
        for item in examples
    }
    gen_a, gen_b = generator_models
    answers_by_model = {gen_a: answers_a, gen_b: answers_b}
    verdicts_by_model = {
        gen_a: SCENARIO_VERDICTS["reliable"],
        gen_b: SCENARIO_VERDICTS["hallucinated"],
    }
    mutations_by_model = {
        gen_a: DEFAULT_MUTATIONS,
        gen_b: DEFAULT_MUTATIONS,
    }
    if isinstance(base_llm, MockLLMClient):
        base_llm.answers_by_model = {key: dict(value) for key, value in answers_by_model.items()}
        base_llm.verdicts_by_model = {key: list(value) for key, value in verdicts_by_model.items()}
        base_llm.mutations_by_model = {key: list(value) for key, value in mutations_by_model.items()}
        return base_llm
    return MockLLMClient(
        answers_by_model=answers_by_model,
        verdicts_by_model=verdicts_by_model,
        mutations_by_model=mutations_by_model,
    )


def validate_request(payload: ExperimentRunRequest, settings: Settings) -> None:
    if payload.synonym_count < 1 or payload.antonym_count < 1:
        raise ExperimentConfigError("Mutation counts must be at least 1.")
    if not 0.0 <= payload.threshold <= 1.0:
        raise ExperimentConfigError("Threshold must be between 0 and 1.")
    if settings.llm_mode == "live" and not settings.api_key_configured:
        raise ExperimentConfigError("Live experiments require a configured OPENAI_API_KEY.")
    if settings.llm_mode == "live":
        mock_ids = {"model-a", "model-b", "model_a", "model_b"}
        if any(item.lower() in mock_ids for item in [*payload.generator_models, *payload.verifier_models]):
            raise ExperimentConfigError(
                "Live experiments require provider model names (for example gpt-4o-mini), not mock ids."
            )
    for model in [*payload.generator_models, *payload.verifier_models]:
        try:
            settings.require_model(model)
        except ValueError as exc:
            raise ExperimentConfigError(str(exc)) from exc


async def run_experiment(
    *,
    llm: LLMClient,
    db: Session,
    settings: Settings,
    payload: ExperimentRunRequest,
) -> Experiment:
    validate_request(payload, settings)
    bundle = load_dataset(payload.dataset)
    if not bundle.examples:
        raise ExperimentConfigError("Dataset cannot be empty.")
    limit = payload.max_questions or settings.max_questions
    examples = bundle.examples[:limit]
    generators = payload.generator_models
    verifiers = payload.verifier_models
    estimate = estimate_experiment_calls(
        questions=len(examples),
        generators=len(generators),
        verifiers=len(verifiers),
        mutations=payload.synonym_count + payload.antonym_count,
        trials=payload.trials,
    )
    if settings.llm_mode == "live" and len(examples) > settings.live_unconfirmed_max_questions and not payload.confirm_live_run:
        raise ExperimentConfigError(
            f"Live run of {len(examples)} questions is estimated at {estimate['total_calls']} LLM calls. "
            "Set confirm_live_run=true to proceed, or lower max_questions."
        )
    eval_llm = InstrumentedLLMClient(llm_for_experiment(llm, settings, examples, generators))
    examples_by_id = {item.id: item for item in examples}
    config = {
        "experiment_name": payload.name.strip() or "Verifier comparison",
        "dataset": bundle.name,
        "dataset_version": bundle.version,
        "question_count": len(examples),
        "dataset_available": len(bundle.examples),
        "max_questions": limit,
        "estimated_llm_calls": estimate,
        "generator_models": generators,
        "verifier_models": verifiers,
        "synonym_count": payload.synonym_count,
        "antonym_count": payload.antonym_count,
        "threshold": payload.threshold,
        "trials": payload.trials,
        "mode": settings.llm_mode,
        "llm_mode": settings.llm_mode,
        "llm": {
            "provider": settings.llm_provider,
            "temperature": settings.llm_temperature,
            "max_output_tokens": settings.llm_max_output_tokens,
            "timeout_seconds": settings.llm_timeout_seconds,
            "max_retries": settings.llm_max_retries,
            "verify_concurrency": settings.verify_concurrency,
            "prompt_bundle": PROMPT_BUNDLE_VERSION,
            "answer_prompt": ANSWER_PROMPT_VERSION,
            "mutation_prompt": MUTATION_PROMPT_VERSION,
            "verify_prompt": VERIFY_PROMPT_VERSION,
            "reproducibility_note": (
                "Live hosted LLM APIs are not bit-reproducible even at temperature 0. "
                "Mock mode is deterministic."
            ),
        },
        "research_question": (
            "Does using the same LLM as both answer generator and mutation verifier "
            "produce systematically different hallucination scores compared with using "
            "a different LLM as verifier, after controlling for verifier calibration?"
        ),
    }
    exclusions: list[dict] = []
    if payload.resume_experiment_id:
        existing = get_experiment(db, payload.resume_experiment_id)
        if existing is None:
            raise ExperimentConfigError("Resume experiment id was not found.")
        if existing.status == "completed":
            raise ExperimentConfigError("That experiment already completed.")
        experiment = existing
        experiment.status = "running"
        try:
            prior = json.loads(experiment.summary_stats_json or "{}")
        except json.JSONDecodeError:
            prior = {}
        exclusions = list(prior.get("exclusions") or [])
        logger.info("experiment resume id=%s", experiment.id)
    else:
        experiment = Experiment(
            name=payload.name.strip() or "Verifier comparison",
            dataset_ref=bundle.name,
            dataset_version=bundle.version,
            generator_models_json=json.dumps(generators),
            verifier_models_json=json.dumps(verifiers),
            synonym_count=payload.synonym_count,
            antonym_count=payload.antonym_count,
            threshold=payload.threshold,
            trials=payload.trials,
            llm_mode=settings.llm_mode,
            config_json=json.dumps(config),
            status="running",
        )
        db.add(experiment)
        db.flush()
    logger.info(
        "experiment started id=%s dataset=%s questions=%s llm_mode=%s",
        experiment.id,
        bundle.name,
        len(examples),
        settings.llm_mode,
    )

    try:
        for trial in range(1, payload.trials + 1):
            for example in examples:
                for generator in generators:
                    if _cell_complete(experiment, example.id, generator, trial):
                        continue
                    reason = await _run_generator_cell(
                        llm=eval_llm,
                        db=db,
                        settings=settings,
                        experiment=experiment,
                        example=example,
                        generator=generator,
                        verifiers=verifiers,
                        trial=trial,
                        synonym_count=payload.synonym_count,
                        antonym_count=payload.antonym_count,
                        threshold=payload.threshold,
                    )
                    if reason:
                        exclusions.append(
                            {
                                "question_id": example.id,
                                "generator_model": generator,
                                "trial_num": trial,
                                "reason": reason,
                                "excluded_by": "experiment_runner",
                                "timestamp": utcnow().isoformat(),
                            }
                        )
                    _persist_progress(db, settings)
        for generation in experiment.generations:
            if len(generation.conditions) != 2:
                continue
            if not _generation_reuse_ok(generation):
                generation.integrity_ok = False
                if not generation.error_message:
                    generation.error_message = "Mutation reuse check failed for this item."
                if not any(
                    item.get("question_id") == generation.question_id
                    and item.get("generator_model") == generation.generator_model
                    and item.get("trial_num") == generation.trial_num
                    and "mutation" in str(item.get("reason", "")).lower()
                    for item in exclusions
                ):
                    exclusions.append(
                        {
                            "question_id": generation.question_id,
                            "generator_model": generation.generator_model,
                            "trial_num": generation.trial_num,
                            "reason": "mutation_reuse_mismatch",
                            "excluded_by": "integrity_check",
                            "timestamp": utcnow().isoformat(),
                        }
                    )
        incomplete = _incomplete_cells(experiment, examples, generators, payload.trials)
        summary = build_summary(
            experiment,
            examples_by_id,
            exclusions=exclusions,
            incomplete=incomplete,
            call_stats=eval_llm.stats(),
        )
        experiment.summary_stats_json = json.dumps(summary)
        experiment.status = "completed"
        experiment.completed_at = utcnow()
        db.flush()
        try:
            from app.experiment.artifacts import write_experiment_artifacts

            write_experiment_artifacts(experiment)
        except Exception:
            logger.exception("experiment artifact export failed id=%s", experiment.id)
        db.refresh(experiment)
        logger.info("experiment completed id=%s conditions=%s", experiment.id, len(experiment.conditions))
        return experiment
    except Exception:
        experiment.status = "failed"
        experiment.completed_at = utcnow()
        try:
            failed_summary = json.loads(experiment.summary_stats_json or "{}")
        except json.JSONDecodeError:
            failed_summary = {}
        failed_summary["exclusions"] = exclusions
        failed_summary["incomplete"] = _incomplete_cells(experiment, examples, generators, payload.trials)
        failed_summary["call_stats"] = eval_llm.stats()
        experiment.summary_stats_json = json.dumps(failed_summary)
        db.flush()
        logger.exception("experiment failed id=%s", experiment.id)
        raise


async def _run_generator_cell(
    *,
    llm: LLMClient,
    db: Session,
    settings: Settings,
    experiment: Experiment,
    example: DatasetExample,
    generator: str,
    verifiers: list[str],
    trial: int,
    synonym_count: int,
    antonym_count: int,
    threshold: float,
) -> str | None:
    generation: ExperimentGeneration | None = None
    try:
        answer = await generate_answer(llm, example.question, generator)
        mutations = await generate_mutations(
            llm,
            model=generator,
            question=example.question,
            answer=answer.text,
            synonym_count=synonym_count,
            antonym_count=antonym_count,
        )
        generation = ExperimentGeneration(
            experiment_id=experiment.id,
            question_id=example.id,
            question=example.question,
            reference_answer=example.reference_answer,
            category=example.category,
            generator_model=generator,
            trial_num=trial,
            base_answer=answer.text,
            integrity_ok=True,
            mutation_set_hash=hash_mutation_set(mutations),
        )
        for index, mutation in enumerate(mutations):
            generation.mutations.append(
                ExperimentMutation(
                    position=index,
                    type=mutation.type.value,
                    original_text=mutation.original_text,
                    mutated_text=mutation.mutated_text,
                )
            )
        experiment.generations.append(generation)
        db.flush()
        stored_texts = [item.mutated_text for item in generation.mutations]
        if len(stored_texts) != len(mutations):
            raise ExperimentIntegrityError("Stored mutation count does not match generated mutations.")

        for verifier in verifiers:
            scored = await verify_mutations(
                llm,
                question=example.question,
                answer=answer.text,
                mutations=mutations,
                verifier_model=verifier,
                concurrency=settings.verify_concurrency,
            )
            verified_texts = [item.mutation.mutated_text for item in scored]
            if verified_texts != stored_texts:
                raise ExperimentIntegrityError(
                    f"Verifier {verifier} did not receive the fixed mutation set for {generator}/{example.id}."
                )
            contributions = [item.contribution for item in scored]
            verdicts = [item.verdict for item in scored]
            score = aggregate_score(contributions)
            classification = classify(score, threshold)
            condition = ExperimentCondition(
                experiment_id=experiment.id,
                generation_id=generation.id,
                generator_model=generator,
                verifier_model=verifier,
                pair_type=pair_type_for(generator, verifier),
                question_id=example.id,
                trial_num=trial,
                hallucination_score=score,
                classification=classification.value,
                not_sure_rate=not_sure_rate(verdicts),
            )
            for index, (scored_item, stored) in enumerate(zip(scored, generation.mutations, strict=True)):
                if scored_item.mutation.mutated_text != stored.mutated_text:
                    raise ExperimentIntegrityError("Mutation text mismatch between verifier conditions.")
                condition.verifications.append(
                    ExperimentVerification(
                        mutation_id=stored.id,
                        position=index,
                        verdict=scored_item.verdict.value,
                        expected_verdict=scored_item.expected.value,
                        contribution=scored_item.contribution,
                        rationale=scored_item.rationale,
                        parse_failed=scored_item.parse_failed,
                    )
                )
            generation.conditions.append(condition)
            experiment.conditions.append(condition)
            db.flush()
        generation.integrity_ok = _generation_reuse_ok(generation)
        if not generation.integrity_ok:
            generation.error_message = "Mutation IDs or texts differ across verifiers."
            return "mutation_reuse_mismatch"
        return None
    except ExperimentIntegrityError as exc:
        logger.exception(
            "stopping experiment item question_id=%s generator=%s",
            example.id,
            generator,
        )
        if generation is not None:
            generation.integrity_ok = False
            generation.error_message = str(exc)
        return f"mutation_reuse_mismatch: {exc}"
    except LLMError as exc:
        logger.exception(
            "LLM failure on experiment item question_id=%s generator=%s",
            example.id,
            generator,
        )
        if generation is not None:
            generation.integrity_ok = False
            generation.error_message = str(exc)
        else:
            failed = ExperimentGeneration(
                experiment_id=experiment.id,
                question_id=example.id,
                question=example.question,
                reference_answer=example.reference_answer,
                category=example.category,
                generator_model=generator,
                trial_num=trial,
                base_answer="",
                integrity_ok=False,
                error_message=str(exc),
            )
            experiment.generations.append(failed)
        return f"llm_failure: {exc}"


def _persist_progress(db: Session, settings: Settings) -> None:
    db.flush()
    if settings.llm_mode == "live":
        db.commit()


def _cell_complete(experiment: Experiment, question_id: str, generator: str, trial: int) -> bool:
    for generation in experiment.generations:
        if (
            generation.question_id == question_id
            and generation.generator_model == generator
            and generation.trial_num == trial
            and generation.integrity_ok
            and len(generation.conditions) == 2
        ):
            return True
    return False


def _incomplete_cells(
    experiment: Experiment,
    examples: list[DatasetExample],
    generators: list[str],
    trials: int,
) -> list[dict]:
    complete = {
        (item.question_id, item.generator_model, item.trial_num)
        for item in experiment.generations
        if item.integrity_ok and len(item.conditions) == 2
    }
    missing: list[dict] = []
    for trial in range(1, trials + 1):
        for example in examples:
            for generator in generators:
                if (example.id, generator, trial) not in complete:
                    missing.append(
                        {
                            "question_id": example.id,
                            "generator_model": generator,
                            "trial_num": trial,
                        }
                    )
    return missing


def _generation_reuse_ok(generation: ExperimentGeneration) -> bool:
    if len(generation.conditions) != 2:
        return False
    mutation_ids = [item.id for item in generation.mutations]
    texts = [item.mutated_text for item in generation.mutations]
    by_id = {item.id: item.mutated_text for item in generation.mutations}
    if not texts or len(set(texts)) != len(texts):
        return False
    for condition in generation.conditions:
        cond_ids = [item.mutation_id for item in condition.verifications]
        if cond_ids != mutation_ids:
            return False
        cond_texts = [by_id.get(item.mutation_id) for item in condition.verifications]
        if any(text is None for text in cond_texts) or cond_texts != texts:
            return False
    return True


def build_summary(
    experiment: Experiment,
    examples: dict[str, DatasetExample],
    *,
    exclusions: list[dict] | None = None,
    incomplete: list[dict] | None = None,
    call_stats: dict | None = None,
) -> dict:
    generators = json.loads(experiment.generator_models_json)
    verifiers = json.loads(experiment.verifier_models_json)
    demo = experiment.llm_mode == "mock"
    exclusions = exclusions or []
    incomplete = incomplete or []
    rows: list[dict] = []
    included_generations = [
        item for item in experiment.generations if item.integrity_ok and len(item.conditions) == 2
    ]
    included_ids = {item.id for item in included_generations}
    mutation_reuse_valid = all(
        _generation_reuse_ok(item) for item in experiment.generations if len(item.conditions) == 2
    ) and not any("mutation_reuse" in str(item.get("reason", "")) for item in exclusions)
    for condition in experiment.conditions:
        generation = condition.generation
        if generation is None or generation.id not in included_ids:
            continue
        example = examples.get(condition.question_id)
        actual = actual_label_for(generation.base_answer, example)
        rows.append(
            {
                "question_id": condition.question_id,
                "question": generation.question,
                "category": generation.category,
                "generator_model": condition.generator_model,
                "verifier_model": condition.verifier_model,
                "pair_type": condition.pair_type,
                "generation_id": condition.generation_id,
                "hallucination_score": condition.hallucination_score,
                "classification": condition.classification,
                "not_sure_rate": condition.not_sure_rate,
                "trial_num": condition.trial_num,
                "actual": actual,
            }
        )
    grouped = group_condition_rows(rows)
    condition_summaries = []
    for generator in generators:
        for verifier in verifiers:
            items = grouped.get((generator, verifier), [])
            labeled = [item for item in items if item["actual"] is not None]
            g_letter = "A" if generator == generators[0] else "B"
            v_letter = "A" if verifier == verifiers[0] else "B"
            condition_summaries.append(
                asdict(
                    summarize_condition(
                        generator_model=generator,
                        verifier_model=verifier,
                        scores=[item["hallucination_score"] for item in items],
                        classifications=[item["classification"] for item in items],
                        not_sure_rates=[item["not_sure_rate"] for item in items],
                        actuals=[item["actual"] for item in labeled] or None,
                        labeled_classifications=[item["classification"] for item in labeled] or None,
                        label=f"{g_letter} → {v_letter}",
                    )
                )
            )

    self_blocks = []
    all_paired: list[dict] = []
    for generator in generators:
        same = [item for item in rows if item["generator_model"] == generator and item["pair_type"] == "same"]
        cross = [item for item in rows if item["generator_model"] == generator and item["pair_type"] == "cross"]
        paired = paired_rows(same, cross)
        all_paired.extend(paired)
        self_blocks.append(self_verification_block(paired, generator))

    overall_flip = round(
        sum(1 for item in all_paired if item["classification_flip"]) / len(all_paired),
        4,
    ) if all_paired else 0.0

    question_count = len({item["question_id"] for item in rows})
    threshold_sweep: list[dict] = []
    for generator in generators:
        for verifier in verifiers:
            items = grouped.get((generator, verifier), [])
            labeled = [item for item in items if item["actual"] is not None]
            if not labeled:
                continue
            for threshold_value, metrics in sweep_thresholds(
                [item["actual"] for item in labeled],
                [item["hallucination_score"] for item in labeled],
            ):
                threshold_sweep.append(
                    {
                        "generator_model": generator,
                        "verifier_model": verifier,
                        "label": f"{generator} / {verifier}",
                        "threshold": threshold_value,
                        **metrics.as_dict(),
                    }
                )

    category_rows = category_analysis(all_paired, rows)
    summary_text = key_finding_text(self_blocks, demo=demo, dataset=experiment.dataset_ref)
    return {
        "demo_data": demo,
        "dataset": experiment.dataset_ref,
        "dataset_version": experiment.dataset_version,
        "generator_models": generators,
        "verifier_models": verifiers,
        "synonym_count": experiment.synonym_count,
        "antonym_count": experiment.antonym_count,
        "threshold": experiment.threshold,
        "trials": experiment.trials,
        "question_count": question_count,
        "completed_questions": question_count,
        "condition_summaries": condition_summaries,
        "self_verification": self_blocks,
        "classification_flip_rate": overall_flip,
        "paired_comparisons": all_paired,
        "threshold_sweep": threshold_sweep,
        "category_analysis": category_rows,
        "exclusions": exclusions,
        "incomplete": incomplete,
        "mutation_reuse_valid": mutation_reuse_valid,
        "call_stats": call_stats or {},
        "research_summary": research_summary(
            blocks=self_blocks,
            condition_summaries=condition_summaries,
            question_count=question_count,
            classification_flip_rate=overall_flip,
            demo=demo,
            dataset=experiment.dataset_ref,
        ),
        "key_finding": summary_text,
        "chart": [
            {
                "label": item["label"],
                "generatorId": item["generator_model"],
                "verifierId": item["verifier_model"],
                "meanScore": item["mean_score"],
                "pairType": item["pair_type"],
                "precision": item["precision"] or 0,
                "recall": item["recall"] or 0,
                "f1": item["f1"] or 0,
                "flipRate": 0,
            }
            for item in condition_summaries
        ],
    }


def _experiment_load_options() -> tuple:
    return (
        selectinload(Experiment.conditions).selectinload(ExperimentCondition.generation),
        selectinload(Experiment.conditions)
        .selectinload(ExperimentCondition.verifications)
        .selectinload(ExperimentVerification.mutation),
        selectinload(Experiment.generations).selectinload(ExperimentGeneration.mutations),
        selectinload(Experiment.generations).selectinload(ExperimentGeneration.conditions),
    )


def get_experiment(db: Session, experiment_id: str) -> Experiment | None:
    statement = select(Experiment).options(*_experiment_load_options()).where(Experiment.id == experiment_id)
    return db.execute(statement).scalar_one_or_none()


def get_latest_experiment(db: Session) -> Experiment | None:
    settings = get_settings()
    frozen_id = (settings.frozen_experiment_id or "").strip()
    if frozen_id:
        frozen = get_experiment(db, frozen_id)
        if frozen is not None:
            return frozen
    statement = (
        select(Experiment)
        .options(*_experiment_load_options())
        .order_by(desc(Experiment.created_at))
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()


def to_experiment_out(experiment: Experiment) -> dict:
    try:
        summary = json.loads(experiment.summary_stats_json)
    except json.JSONDecodeError:
        summary = {}
    created = experiment.created_at.isoformat() if isinstance(experiment.created_at, datetime) else experiment.created_at
    generators = json.loads(experiment.generator_models_json or "[]")
    verifiers = json.loads(experiment.verifier_models_json or "[]")
    return {
        "id": experiment.id,
        "experiment_id": experiment.id,
        "name": experiment.name,
        "dataset_ref": experiment.dataset_ref,
        "dataset_name": experiment.dataset_ref,
        "dataset_version": experiment.dataset_version,
        "status": experiment.status,
        "created_at": created,
        "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
        "summary_stats": summary if isinstance(summary, dict) else {},
        "condition_count": len(experiment.conditions),
        "demo_data": experiment.llm_mode == "mock",
        "llm_mode": experiment.llm_mode,
        "generator_models": generators,
        "verifier_models": verifiers,
        "synonym_count": experiment.synonym_count,
        "antonym_count": experiment.antonym_count,
        "threshold": experiment.threshold,
        "trials": experiment.trials,
        "config": json.loads(experiment.config_json or "{}"),
        "condition_summaries": summary.get("condition_summaries", []) if isinstance(summary, dict) else [],
        "self_verification": summary.get("self_verification", []) if isinstance(summary, dict) else [],
        "classification_flip_rate": summary.get("classification_flip_rate", 0) if isinstance(summary, dict) else 0,
        "paired_comparisons": summary.get("paired_comparisons", []) if isinstance(summary, dict) else [],
        "threshold_sweep": summary.get("threshold_sweep", []) if isinstance(summary, dict) else [],
        "research_summary": summary.get("research_summary", {}) if isinstance(summary, dict) else {},
        "key_finding": summary.get("key_finding", "") if isinstance(summary, dict) else "",
        "chart": summary.get("chart", []) if isinstance(summary, dict) else [],
        "question_count": summary.get("question_count", 0) if isinstance(summary, dict) else 0,
        "mutation_reuse_valid": summary.get("mutation_reuse_valid") if isinstance(summary, dict) else None,
        "exclusions": summary.get("exclusions", []) if isinstance(summary, dict) else [],
        "incomplete": summary.get("incomplete", []) if isinstance(summary, dict) else [],
        "call_stats": summary.get("call_stats", {}) if isinstance(summary, dict) else {},
        "category_analysis": summary.get("category_analysis", []) if isinstance(summary, dict) else [],
        "research_log": experiment_research_log(experiment),
    }


def generation_trace(experiment: Experiment, generation_id: str) -> dict | None:
    generation = next((item for item in experiment.generations if item.id == generation_id), None)
    if generation is None:
        return None
    conditions = []
    for condition in generation.conditions:
        mutations = []
        for verification in condition.verifications:
            mutation = verification.mutation
            mutations.append(
                {
                    "id": mutation.id,
                    "type": mutation.type,
                    "original_text": mutation.original_text,
                    "mutated_text": mutation.mutated_text,
                    "verdict": verification.verdict,
                    "expected_verdict": verification.expected_verdict,
                    "contribution": verification.contribution,
                    "rationale": verification.rationale,
                }
            )
        conditions.append(
            {
                "verifier_model": condition.verifier_model,
                "pair_type": condition.pair_type,
                "hallucination_score": condition.hallucination_score,
                "classification": condition.classification,
                "not_sure_rate": condition.not_sure_rate,
                "mutations": mutations,
            }
        )
    return {
        "generation_id": generation.id,
        "question_id": generation.question_id,
        "question": generation.question,
        "generator_model": generation.generator_model,
        "base_answer": generation.base_answer,
        "mutation_set_hash": generation.mutation_set_hash,
        "conditions": conditions,
    }


def export_conditions_csv(experiment: Experiment) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "experiment_id",
            "question_id",
            "question",
            "category",
            "generator_model",
            "verifier_model",
            "pair_type",
            "trial_num",
            "base_answer",
            "mutation_set_hash",
            "hallucination_score",
            "classification",
            "not_sure_rate",
            "threshold",
        ],
    )
    writer.writeheader()
    for condition in experiment.conditions:
        generation = condition.generation
        writer.writerow(
            {
                "experiment_id": experiment.id,
                "question_id": condition.question_id,
                "question": generation.question if generation else "",
                "category": generation.category if generation else "",
                "generator_model": condition.generator_model,
                "verifier_model": condition.verifier_model,
                "pair_type": condition.pair_type,
                "trial_num": condition.trial_num,
                "base_answer": generation.base_answer if generation else "",
                "mutation_set_hash": generation.mutation_set_hash if generation else "",
                "hallucination_score": condition.hallucination_score,
                "classification": condition.classification,
                "not_sure_rate": condition.not_sure_rate,
                "threshold": experiment.threshold,
            }
        )
    return buffer.getvalue()


def export_paired_csv(experiment: Experiment) -> str:
    summary = json.loads(experiment.summary_stats_json or "{}")
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "question_id",
            "generator_model",
            "same_model_score",
            "cross_model_score",
            "difference",
            "same_label",
            "cross_label",
            "classification_flip",
            "trial_num",
        ],
    )
    writer.writeheader()
    for row in summary.get("paired_comparisons", []):
        writer.writerow(
            {
                "question_id": row.get("question_id"),
                "generator_model": row.get("generator_model"),
                "same_model_score": row.get("same_model_score"),
                "cross_model_score": row.get("cross_model_score"),
                "difference": row.get("difference"),
                "same_label": row.get("same_label"),
                "cross_label": row.get("cross_label"),
                "classification_flip": row.get("classification_flip"),
                "trial_num": row.get("trial_num", 1),
            }
        )
    return buffer.getvalue()


def export_condition_summary_csv(experiment: Experiment) -> str:
    summary = json.loads(experiment.summary_stats_json or "{}")
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "generator_model",
            "verifier_model",
            "pair_type",
            "label",
            "n",
            "mean_score",
            "median_score",
            "stdev",
            "ci95_low",
            "ci95_high",
            "reliable_count",
            "hallucinated_count",
            "reliable_rate",
            "hallucinated_rate",
            "not_sure_rate",
            "precision",
            "recall",
            "f1",
            "accuracy",
        ],
    )
    writer.writeheader()
    for row in summary.get("condition_summaries", []):
        writer.writerow({key: row.get(key) for key in writer.fieldnames})
    return buffer.getvalue()


def export_flip_csv(experiment: Experiment) -> str:
    summary = json.loads(experiment.summary_stats_json or "{}")
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "question_id",
            "question",
            "generator_model",
            "trial_num",
            "same_label",
            "cross_label",
            "classification_flip",
            "same_model_score",
            "cross_model_score",
        ],
    )
    writer.writeheader()
    for row in summary.get("paired_comparisons", []):
        writer.writerow(
            {
                "question_id": row.get("question_id"),
                "question": row.get("question"),
                "generator_model": row.get("generator_model"),
                "trial_num": row.get("trial_num", 1),
                "same_label": row.get("same_label"),
                "cross_label": row.get("cross_label"),
                "classification_flip": row.get("classification_flip"),
                "same_model_score": row.get("same_model_score"),
                "cross_model_score": row.get("cross_model_score"),
            }
        )
    return buffer.getvalue()


def export_threshold_sweep_csv(experiment: Experiment) -> str:
    summary = json.loads(experiment.summary_stats_json or "{}")
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "generator_model",
            "verifier_model",
            "threshold",
            "precision",
            "recall",
            "f1",
            "accuracy",
            "tp",
            "tn",
            "fp",
            "fn",
            "included_examples",
        ],
    )
    writer.writeheader()
    for row in summary.get("threshold_sweep", []):
        writer.writerow({key: row.get(key) for key in writer.fieldnames})
    return buffer.getvalue()


def experiment_research_log(experiment: Experiment) -> dict:
    created = experiment.created_at.isoformat() if isinstance(experiment.created_at, datetime) else experiment.created_at
    try:
        config = json.loads(experiment.config_json or "{}")
    except json.JSONDecodeError:
        config = {}
    log = {
        "experiment_id": experiment.id,
        "experiment_name": experiment.name,
        "dataset": experiment.dataset_ref,
        "dataset_version": experiment.dataset_version,
        "generator_models": json.loads(experiment.generator_models_json or "[]"),
        "verifier_models": json.loads(experiment.verifier_models_json or "[]"),
        "synonym_count": experiment.synonym_count,
        "antonym_count": experiment.antonym_count,
        "threshold": experiment.threshold,
        "trials": experiment.trials,
        "timestamp": created,
        "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
        "mode": experiment.llm_mode,
        "status": experiment.status,
    }
    if isinstance(config, dict):
        if "llm" in config:
            log["llm"] = config["llm"]
        if "research_question" in config:
            log["research_question"] = config["research_question"]
    return log


def export_research_log_json(experiment: Experiment) -> str:
    return json.dumps(experiment_research_log(experiment), indent=2)


def estimate_from_request(payload: ExperimentRunRequest, settings: Settings) -> dict:
    bundle = load_dataset(payload.dataset)
    if not bundle.examples:
        raise ExperimentConfigError("Dataset cannot be empty.")
    limit = payload.max_questions or settings.max_questions
    questions = min(len(bundle.examples), limit)
    estimate = estimate_experiment_calls(
        questions=questions,
        generators=len(payload.generator_models),
        verifiers=len(payload.verifier_models),
        mutations=payload.synonym_count + payload.antonym_count,
        trials=payload.trials,
    )
    estimate["dataset"] = bundle.name
    estimate["dataset_version"] = bundle.version
    estimate["dataset_available"] = len(bundle.examples)
    estimate["max_questions"] = limit
    estimate["llm_mode"] = settings.llm_mode
    estimate["live_ready"] = settings.live_ready
    estimate["live_confirm_required"] = (
        settings.llm_mode == "live" and questions > settings.live_unconfirmed_max_questions
    )
    return estimate
