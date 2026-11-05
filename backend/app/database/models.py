from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    generator_model: Mapped[str] = mapped_column(String(128), nullable=False)
    mutation_generator_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mutation_verifier_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    base_answer: Mapped[str] = mapped_column(Text, nullable=False)
    # Placeholder values until MetaQA completes; API maps Incomplete → null.
    hallucination_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False, default="Incomplete")
    not_sure_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="live")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    analysis_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Web Evidence (independent parallel pipeline; JSON payload for Phase 1).
    web_evidence_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    web_evidence_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    web_evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_verdicts_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    combined_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_verdict: Mapped[str | None] = mapped_column(String(64), nullable=True)
    answer_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    mutation_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    verify_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    mutations: Mapped[list["Mutation"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="Mutation.position",
    )


class Mutation(Base):
    __tablename__ = "mutations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    mutated_text: Mapped[str] = mapped_column(Text, nullable=False)
    verifier_model: Mapped[str] = mapped_column(String(128), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    contribution: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parse_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verdicts_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[Run] = relationship(back_populates="mutations")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_ref: Mapped[str] = mapped_column(String(255), nullable=False, default="hallucination_benchmark_frozen")
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1.0")
    generator_models_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    verifier_models_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    synonym_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    antonym_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    trials: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    llm_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="live")
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    summary_stats_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    generations: Mapped[list["ExperimentGeneration"]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    conditions: Mapped[list["ExperimentCondition"]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
    )


class ExperimentGeneration(Base):
    __tablename__ = "experiment_generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general_fact")
    generator_model: Mapped[str] = mapped_column(String(128), nullable=False)
    trial_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    base_answer: Mapped[str] = mapped_column(Text, nullable=False)
    integrity_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mutation_set_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    experiment: Mapped[Experiment] = relationship(back_populates="generations")
    mutations: Mapped[list["ExperimentMutation"]] = relationship(
        back_populates="generation",
        cascade="all, delete-orphan",
        order_by="ExperimentMutation.position",
    )
    conditions: Mapped[list["ExperimentCondition"]] = relationship(
        back_populates="generation",
        cascade="all, delete-orphan",
    )


class ExperimentMutation(Base):
    __tablename__ = "experiment_mutations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    generation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("experiment_generations.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    mutated_text: Mapped[str] = mapped_column(Text, nullable=False)

    generation: Mapped[ExperimentGeneration] = relationship(back_populates="mutations")
    verifications: Mapped[list["ExperimentVerification"]] = relationship(
        back_populates="mutation",
        cascade="all, delete-orphan",
    )


class ExperimentCondition(Base):
    __tablename__ = "experiment_conditions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    generation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("experiment_generations.id", ondelete="CASCADE"),
        nullable=True,
    )
    generator_model: Mapped[str] = mapped_column(String(128), nullable=False)
    verifier_model: Mapped[str] = mapped_column(String(128), nullable=False)
    pair_type: Mapped[str] = mapped_column(String(16), nullable=False, default="cross")
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trial_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hallucination_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    classification: Mapped[str] = mapped_column(String(32), nullable=False, default="Reliable")
    not_sure_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    experiment: Mapped[Experiment] = relationship(back_populates="conditions")
    generation: Mapped[ExperimentGeneration | None] = relationship(back_populates="conditions")
    verifications: Mapped[list["ExperimentVerification"]] = relationship(
        back_populates="condition",
        cascade="all, delete-orphan",
        order_by="ExperimentVerification.position",
    )


class ExperimentVerification(Base):
    __tablename__ = "experiment_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    condition_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("experiment_conditions.id", ondelete="CASCADE"),
        nullable=False,
    )
    mutation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("experiment_mutations.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    contribution: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parse_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    condition: Mapped[ExperimentCondition] = relationship(back_populates="verifications")
    mutation: Mapped[ExperimentMutation] = relationship(back_populates="verifications")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1.0")
    generator_model: Mapped[str] = mapped_column(String(128), nullable=False)
    verifier_model: Mapped[str] = mapped_column(String(128), nullable=False)
    synonym_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    antonym_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    mutation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    total_examples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_examples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_examples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    llm_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="live")
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    category_metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    summary_metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    results: Mapped[list["EvaluationResult"]] = relationship(
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
        order_by="EvaluationResult.position",
    )
    metrics: Mapped[list["EvaluationMetric"]] = relationship(
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
        order_by="EvaluationMetric.threshold",
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    evaluation_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)
    generated_answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actual_label: Mapped[str] = mapped_column(String(32), nullable=False)
    predicted_label: Mapped[str] = mapped_column(String(32), nullable=False)
    hallucination_score: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general_fact")
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    ground_truth_source: Mapped[str] = mapped_column(String(32), nullable=False, default="reference_match")
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Component-level scores and predictions
    metaqa_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metaqa_prediction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metaqa_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)

    web_evidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    web_evidence_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    web_evidence_prediction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    web_evidence_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_run")
    web_evidence_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)

    multi_model_consensus: Mapped[str | None] = mapped_column(String(32), nullable=True)
    multi_model_prediction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    multi_model_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_run")
    multi_model_agreement: Mapped[float | None] = mapped_column(Float, nullable=True)
    multi_model_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)

    combined_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    combined_verdict: Mapped[str | None] = mapped_column(String(64), nullable=True)
    combined_prediction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    combined_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)

    component_details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Independent Research Judge (Gemini) & Human Annotation telemetry
    judge_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    judge_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_status: Mapped[str | None] = mapped_column(String(32), nullable=True, default='not_run')
    reviewer1_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer2_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    adjudicated_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default='legacy_inferred')

    evaluation_run: Mapped[EvaluationRun] = relationship(back_populates="results")


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    evaluation_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    component: Mapped[str] = mapped_column(String(32), nullable=False, default="metaqa")
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    tp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    precision: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recall: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    f1: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    specificity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fpr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fnr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    included_examples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    abstained_examples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    evaluation_run: Mapped[EvaluationRun] = relationship(back_populates="metrics")


class HumanAnnotation(Base):
    __tablename__ = "human_annotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    evaluation_result_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_results.id", ondelete="CASCADE"), nullable=False)
    evaluation_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_answer: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)
    judge_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    judge_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewer1_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer1_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer1_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer2_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer2_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer2_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    disagreement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    adjudicated_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    adjudicator_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    adjudication_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjudication_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    audit_logs: Mapped[list["AnnotationAuditLog"]] = relationship(
        back_populates="annotation",
        cascade="all, delete-orphan",
        order_by="AnnotationAuditLog.created_at",
    )


class AnnotationAuditLog(Base):
    __tablename__ = "annotation_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    annotation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("human_annotations.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    previous_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    annotation: Mapped[HumanAnnotation] = relationship(back_populates="audit_logs")

