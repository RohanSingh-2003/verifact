from __future__ import annotations

import csv
import io
import json

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import EvaluationMetric, EvaluationRun
from app.schemas.evaluation import (
    CategoryMetricOut,
    ConfusionMatrixOut,
    EvaluationDetail,
    EvaluationListResponse,
    EvaluationResultOut,
    EvaluationSummary,
    MetricsOut,
)


def get_evaluation(db: Session, evaluation_id: str) -> EvaluationRun | None:
    statement = (
        select(EvaluationRun)
        .options(selectinload(EvaluationRun.results), selectinload(EvaluationRun.metrics))
        .where(EvaluationRun.id == evaluation_id)
    )
    return db.execute(statement).scalar_one_or_none()


def list_evaluations(db: Session) -> EvaluationListResponse:
    statement = select(EvaluationRun).options(selectinload(EvaluationRun.metrics)).order_by(desc(EvaluationRun.created_at))
    rows = db.execute(statement).scalars().all()
    return EvaluationListResponse(
        items=[to_summary(row) for row in rows],
        total=len(rows),
    )


def primary_metric(run: EvaluationRun) -> EvaluationMetric | None:
    for item in run.metrics:
        if item.is_primary:
            return item
    return run.metrics[0] if run.metrics else None


def to_summary(run: EvaluationRun) -> EvaluationSummary:
    primary = primary_metric(run)
    return EvaluationSummary(
        id=run.id,
        name=run.name,
        dataset_name=run.dataset_name,
        dataset_version=run.dataset_version,
        generator_model=run.generator_model,
        verifier_model=run.verifier_model,
        mutation_count=run.mutation_count,
        threshold=run.threshold,
        total_examples=run.total_examples,
        completed_examples=run.completed_examples,
        review_examples=run.review_examples,
        status=run.status,
        llm_mode=run.llm_mode,
        created_at=run.created_at,
        completed_at=run.completed_at,
        f1=primary.f1 if primary else None,
        accuracy=primary.accuracy if primary else None,
    )


def to_detail(run: EvaluationRun) -> EvaluationDetail:
    primary = primary_metric(run)
    if primary is None:
        primary = EvaluationMetric(threshold=run.threshold)
    config = json.loads(run.config_json or "{}")
    category_raw = json.loads(run.category_metrics_json or "[]")
    sweep = sorted(run.metrics, key=lambda item: item.threshold)
    if not any(item.is_primary for item in sweep):
        sweep = [primary, *sweep]
    return EvaluationDetail(
        evaluation_id=run.id,
        name=run.name,
        status=run.status,
        dataset_name=run.dataset_name,
        dataset_version=run.dataset_version,
        generator_model=run.generator_model,
        verifier_model=run.verifier_model,
        synonym_count=run.synonym_count,
        antonym_count=run.antonym_count,
        mutation_count=run.mutation_count,
        threshold=run.threshold,
        best_threshold_by_f1=config.get("best_threshold_by_f1"),
        total_examples=run.total_examples,
        completed_examples=run.completed_examples,
        review_examples=run.review_examples,
        llm_mode=run.llm_mode,
        demo_data=run.llm_mode == "mock",
        created_at=run.created_at,
        completed_at=run.completed_at,
        config=config,
        metrics=_metrics_out(primary),
        confusion_matrix=ConfusionMatrixOut(tn=primary.tn, fp=primary.fp, fn=primary.fn, tp=primary.tp),
        threshold_sweep=[_metrics_out(item) for item in sweep],
        category_metrics=[CategoryMetricOut.model_validate(item) for item in category_raw],
        results=[
            EvaluationResultOut(
                question_id=item.question_id,
                question=item.question,
                reference_answer=item.reference_answer,
                generated_answer=item.generated_answer,
                actual_label=item.actual_label,
                predicted_label=item.predicted_label,
                hallucination_score=item.hallucination_score,
                category=item.category,
                outcome=item.outcome,
                ground_truth_source=item.ground_truth_source,
                run_id=item.run_id,
            )
            for item in run.results
        ],
    )


def _metrics_out(item: EvaluationMetric) -> MetricsOut:
    return MetricsOut(
        threshold=item.threshold,
        tp=item.tp,
        tn=item.tn,
        fp=item.fp,
        fn=item.fn,
        accuracy=item.accuracy,
        precision=item.precision,
        recall=item.recall,
        f1=item.f1,
        specificity=item.specificity,
        fpr=item.fpr,
        fnr=item.fnr,
        included_examples=item.included_examples,
        is_primary=item.is_primary,
    )


def export_csv(run: EvaluationRun) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "question_id",
            "question",
            "reference_answer",
            "category",
            "actual_label",
            "predicted_label",
            "hallucination_score",
            "outcome",
            "generator_model",
            "verifier_model",
            "threshold",
        ],
    )
    writer.writeheader()
    for item in run.results:
        writer.writerow(
            {
                "question_id": item.question_id,
                "question": item.question,
                "reference_answer": item.reference_answer,
                "category": item.category,
                "actual_label": item.actual_label,
                "predicted_label": item.predicted_label,
                "hallucination_score": item.hallucination_score,
                "outcome": item.outcome,
                "generator_model": run.generator_model,
                "verifier_model": run.verifier_model,
                "threshold": run.threshold,
            }
        )
    return buffer.getvalue()


def export_threshold_sweep_csv(run: EvaluationRun) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "evaluation_id",
            "dataset_name",
            "threshold",
            "is_primary",
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
    for item in sorted(run.metrics, key=lambda row: row.threshold):
        writer.writerow(
            {
                "evaluation_id": run.id,
                "dataset_name": run.dataset_name,
                "threshold": item.threshold,
                "is_primary": item.is_primary,
                "precision": item.precision,
                "recall": item.recall,
                "f1": item.f1,
                "accuracy": item.accuracy,
                "tp": item.tp,
                "tn": item.tn,
                "fp": item.fp,
                "fn": item.fn,
                "included_examples": item.included_examples,
            }
        )
    return buffer.getvalue()
