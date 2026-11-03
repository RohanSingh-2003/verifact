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


def _extract_mm_field(item: Any, field_name: str, default: Any = None) -> Any:
    if getattr(item, "component_details_json", None):
        try:
            parsed = json.loads(item.component_details_json)
            mm = parsed.get("multi_model", {})
            return mm.get(field_name, default)
        except Exception:
            pass
    return default


def to_detail(run: EvaluationRun) -> EvaluationDetail:
    primary = primary_metric(run)
    if primary is None:
        primary = EvaluationMetric(threshold=run.threshold)
    config = json.loads(run.config_json or "{}")
    category_raw = json.loads(run.category_metrics_json or "[]")
    component_metrics_data = config.get("component_metrics")
    if not component_metrics_data and getattr(run, "summary_metrics_json", None):
        try:
            component_metrics_data = json.loads(run.summary_metrics_json)
        except Exception:
            component_metrics_data = None
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
        component_metrics=component_metrics_data,
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
                metaqa_score=getattr(item, "metaqa_score", None),
                metaqa_prediction=getattr(item, "metaqa_prediction", None),
                metaqa_outcome=getattr(item, "metaqa_outcome", None),
                web_evidence_score=getattr(item, "web_evidence_score", None),
                web_evidence_verdict=getattr(item, "web_evidence_verdict", None),
                web_evidence_prediction=getattr(item, "web_evidence_prediction", None),
                web_evidence_status=getattr(item, "web_evidence_status", None),
                web_evidence_outcome=getattr(item, "web_evidence_outcome", None),
                multi_model_consensus=getattr(item, "multi_model_consensus", None),
                multi_model_prediction=getattr(item, "multi_model_prediction", None),
                multi_model_status=getattr(item, "multi_model_status", None),
                multi_model_agreement=getattr(item, "multi_model_agreement", None),
                multi_model_outcome=getattr(item, "multi_model_outcome", None),
                combined_risk_score=getattr(item, "combined_risk_score", None),
                combined_verdict=getattr(item, "combined_verdict", None),
                combined_prediction=getattr(item, "combined_prediction", None),
                combined_outcome=getattr(item, "combined_outcome", None),
                latency_ms=getattr(item, "latency_ms", None),
                required_quorum=_extract_mm_field(item, "required_quorum"),
                completed_verifiers=_extract_mm_field(item, "completed_verifiers"),
                total_verifiers=_extract_mm_field(item, "total_verifiers"),
                failed_verifiers=_extract_mm_field(item, "failed_verifiers"),
                multi_model_abstained=_extract_mm_field(item, "multi_model_abstained", item.multi_model_prediction is None),
                judge_label=getattr(item, "judge_label", None),
                judge_reasoning=getattr(item, "judge_reasoning", None),
                judge_confidence=getattr(item, "judge_confidence", None),
                judge_status=getattr(item, "judge_status", None),
                reviewer1_label=getattr(item, "reviewer1_label", None),
                reviewer2_label=getattr(item, "reviewer2_label", None),
                adjudicated_label=getattr(item, "adjudicated_label", None),
                validation_status=getattr(item, "validation_status", None),
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
        component=getattr(item, "component", "metaqa") or "metaqa",
        coverage=getattr(item, "coverage", 1.0) if getattr(item, "coverage", None) is not None else 1.0,
        abstained_examples=getattr(item, "abstained_examples", 0) if getattr(item, "abstained_examples", None) is not None else 0,
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
            "metaqa_score",
            "metaqa_prediction",
            "metaqa_outcome",
            "web_evidence_score",
            "web_evidence_verdict",
            "web_evidence_prediction",
            "web_evidence_outcome",
            "multi_model_status",
            "multi_model_consensus",
            "multi_model_prediction",
            "multi_model_outcome",
            "judge_label",
            "judge_status",
            "judge_confidence",
            "judge_reasoning",
            "validation_status",
            "adjudicated_label",
            "combined_risk_score",
            "combined_verdict",
            "combined_prediction",
            "combined_outcome",
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
                "metaqa_score": getattr(item, "metaqa_score", ""),
                "metaqa_prediction": getattr(item, "metaqa_prediction", ""),
                "metaqa_outcome": getattr(item, "metaqa_outcome", ""),
                "web_evidence_score": getattr(item, "web_evidence_score", ""),
                "web_evidence_verdict": getattr(item, "web_evidence_verdict", ""),
                "web_evidence_prediction": getattr(item, "web_evidence_prediction", ""),
                "web_evidence_outcome": getattr(item, "web_evidence_outcome", ""),
                "multi_model_status": getattr(item, "multi_model_status", ""),
                "multi_model_consensus": getattr(item, "multi_model_consensus", ""),
                "multi_model_prediction": getattr(item, "multi_model_prediction", ""),
                "multi_model_outcome": getattr(item, "multi_model_outcome", ""),
                "judge_label": getattr(item, "judge_label", ""),
                "judge_status": getattr(item, "judge_status", ""),
                "judge_confidence": getattr(item, "judge_confidence", "") if getattr(item, "judge_confidence", None) is not None else "",
                "judge_reasoning": getattr(item, "judge_reasoning", ""),
                "validation_status": getattr(item, "validation_status", ""),
                "adjudicated_label": getattr(item, "adjudicated_label", ""),
                "combined_risk_score": getattr(item, "combined_risk_score", ""),
                "combined_verdict": getattr(item, "combined_verdict", ""),
                "combined_prediction": getattr(item, "combined_prediction", ""),
                "combined_outcome": getattr(item, "combined_outcome", ""),
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
