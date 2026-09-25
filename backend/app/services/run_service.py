from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import Mutation, Run, new_id
from app.metaqa.detector import DetectionResult, ScoredMutation
from app.metaqa.mutation import GeneratedMutation
from app.metaqa.scoring import Classification, expected_verdict
from app.schemas.detect import (
    BaseAnswerOut,
    DetectResponse,
    DetectTiming,
    MutationOut,
    RunListResponse,
    RunStatus,
    RunSummary,
)


INCOMPLETE_CLASSIFICATION = "Incomplete"
PENDING_VERDICT = ""

MUTATION_GENERATION_ERROR = (
    "Hallucination analysis could not be completed because the mutation generator "
    "did not return the required mutation set. The generated answer is still available above."
)
CLAIM_EXTRACTION_ERROR = (
    "Hallucination analysis could not be completed because core claim extraction failed. "
    "The generated answer is still available above."
)
VERIFICATION_ERROR = (
    "Hallucination analysis could not be completed because mutation verification failed. "
    "The generated answer and any mutations above are still available."
)
SCORING_ERROR = (
    "Hallucination analysis could not be completed while calculating the score. "
    "The generated answer and any mutations above are still available."
)
GENERIC_ANALYSIS_ERROR = (
    "Hallucination analysis could not be completed. The generated answer is still available above."
)


def classify_analysis_failure(
    exc: BaseException,
    *,
    stage: str | None = None,
) -> tuple[RunStatus, str]:
    """Map a MetaQA-stage exception to a failure status and user-facing message.

    Never treats mutation/verification failures as answer-generation failures.
    """
    message = str(exc) or ""
    lower = message.casefold()
    stage_value = (stage or "").casefold()

    if "claim extractor" in lower or "claim extraction" in lower:
        return RunStatus.MUTATION_GENERATION_FAILED, CLAIM_EXTRACTION_ERROR
    if "mutation generator" in lower or "required mutation set" in lower:
        return RunStatus.MUTATION_GENERATION_FAILED, MUTATION_GENERATION_ERROR
    if "mock mutation failure" in lower:
        return RunStatus.MUTATION_GENERATION_FAILED, MUTATION_GENERATION_ERROR
    if "verif" in lower or stage_value == RunStatus.VERIFYING_MUTATIONS.value:
        return RunStatus.VERIFICATION_FAILED, VERIFICATION_ERROR
    if "score" in lower or stage_value == RunStatus.CALCULATING_SCORE.value:
        return RunStatus.SCORING_FAILED, SCORING_ERROR
    if stage_value in {
        RunStatus.GENERATING_MUTATIONS.value,
        RunStatus.ANSWER_READY.value,
        RunStatus.MUTATIONS_READY.value,
        "",
    }:
        return RunStatus.MUTATION_GENERATION_FAILED, MUTATION_GENERATION_ERROR
    return RunStatus.FAILED, GENERIC_ANALYSIS_ERROR



def persist_detection(db: Session, result: DetectionResult) -> DetectResponse:
    """Persist a fully completed detection (used by experiments / sync paths)."""
    run = Run(
        id=new_id(),
        question=result.question,
        generator_model=result.generator_model,
        base_answer=result.base_answer.text,
        hallucination_score=result.hallucination_score,
        threshold=result.threshold,
        classification=result.classification.value,
        not_sure_rate=result.not_sure_rate,
        llm_mode=result.llm_mode,
        status=RunStatus.COMPLETED.value,
        analysis_error="",
    )
    if result.timing is not None:
        run.answer_ms = result.timing.answer_ms
        run.mutation_ms = result.timing.mutation_ms
        run.verify_ms = result.timing.verify_ms
        run.total_ms = result.timing.total_ms
    for index, item in enumerate(result.mutations):
        run.mutations.append(
            Mutation(
                id=new_id(),
                type=item.mutation.type.value,
                original_text=item.mutation.original_text,
                mutated_text=item.mutation.mutated_text,
                verifier_model=result.verifier_model,
                verdict=item.verdict.value,
                expected_verdict=item.expected.value,
                contribution=item.contribution,
                rationale=item.rationale,
                parse_failed=item.parse_failed,
                verified=True,
                position=index,
            )
        )
    db.add(run)
    db.flush()
    db.refresh(run)
    return to_detect_response(run)


def create_answer_ready_run(
    db: Session,
    *,
    question: str,
    base_answer: str,
    generator_model: str,
    threshold: float,
    llm_mode: str,
    answer_ms: float | None = None,
) -> Run:
    run = Run(
        id=new_id(),
        question=question,
        generator_model=generator_model,
        base_answer=base_answer,
        hallucination_score=0.0,
        threshold=threshold,
        classification=INCOMPLETE_CLASSIFICATION,
        not_sure_rate=0.0,
        llm_mode=llm_mode,
        status=RunStatus.ANSWER_READY.value,
        analysis_error="",
        answer_ms=answer_ms,
    )
    db.add(run)
    db.flush()
    db.refresh(run)
    return run


def update_run_status(db: Session, run_id: str, status: RunStatus) -> None:
    run = db.get(Run, run_id)
    if run is None:
        return
    run.status = status.value
    db.flush()


def persist_pending_mutations(
    db: Session,
    run_id: str,
    *,
    mutations: list[GeneratedMutation],
    verifier_model: str,
    mutation_ms: float | None = None,
) -> None:
    """Persist generated mutations before verification so the API can show them."""
    run = db.execute(
        select(Run).options(selectinload(Run.mutations)).where(Run.id == run_id)
    ).scalar_one_or_none()
    if run is None:
        return

    run.mutations.clear()
    for index, item in enumerate(mutations):
        run.mutations.append(
            Mutation(
                id=new_id(),
                type=item.type.value,
                original_text=item.original_text,
                mutated_text=item.mutated_text,
                verifier_model=verifier_model,
                verdict=PENDING_VERDICT,
                expected_verdict=expected_verdict(item.type).value,
                contribution=0.0,
                rationale="",
                parse_failed=False,
                verified=False,
                position=index,
            )
        )
    run.status = RunStatus.MUTATIONS_READY.value
    if mutation_ms is not None:
        run.mutation_ms = mutation_ms
    db.flush()


def update_mutation_verification(
    db: Session,
    run_id: str,
    position: int,
    scored: ScoredMutation,
) -> None:
    run = db.execute(
        select(Run).options(selectinload(Run.mutations)).where(Run.id == run_id)
    ).scalar_one_or_none()
    if run is None:
        return
    for item in run.mutations:
        if item.position == position:
            item.verdict = scored.verdict.value
            item.expected_verdict = scored.expected.value
            item.contribution = scored.contribution
            item.rationale = scored.rationale
            item.parse_failed = scored.parse_failed
            item.verified = True
            break
    db.flush()


def complete_run_analysis(
    db: Session,
    run_id: str,
    result: DetectionResult,
) -> Run | None:
    run = db.execute(
        select(Run).options(selectinload(Run.mutations)).where(Run.id == run_id)
    ).scalar_one_or_none()
    if run is None:
        return None

    run.hallucination_score = result.hallucination_score
    run.threshold = result.threshold
    run.classification = result.classification.value
    run.not_sure_rate = result.not_sure_rate
    run.status = RunStatus.COMPLETED.value
    run.analysis_error = ""
    if result.timing is not None:
        run.answer_ms = result.timing.answer_ms
        run.mutation_ms = result.timing.mutation_ms
        run.verify_ms = result.timing.verify_ms
        run.total_ms = result.timing.total_ms

    # Ensure mutation rows match final scored results (stable positions).
    by_position = {item.position: item for item in run.mutations}
    for index, scored in enumerate(result.mutations):
        existing = by_position.get(index)
        if existing is None:
            run.mutations.append(
                Mutation(
                    id=new_id(),
                    type=scored.mutation.type.value,
                    original_text=scored.mutation.original_text,
                    mutated_text=scored.mutation.mutated_text,
                    verifier_model=result.verifier_model,
                    verdict=scored.verdict.value,
                    expected_verdict=scored.expected.value,
                    contribution=scored.contribution,
                    rationale=scored.rationale,
                    parse_failed=scored.parse_failed,
                    verified=True,
                    position=index,
                )
            )
        else:
            existing.type = scored.mutation.type.value
            existing.original_text = scored.mutation.original_text
            existing.mutated_text = scored.mutation.mutated_text
            existing.verifier_model = result.verifier_model
            existing.verdict = scored.verdict.value
            existing.expected_verdict = scored.expected.value
            existing.contribution = scored.contribution
            existing.rationale = scored.rationale
            existing.parse_failed = scored.parse_failed
            existing.verified = True
    db.flush()
    db.refresh(run)
    return run


def fail_run_analysis(
    db: Session,
    run_id: str,
    message: str,
    *,
    status: RunStatus = RunStatus.FAILED,
) -> None:
    """Record a MetaQA-stage failure without clearing the persisted answer.

    Earlier-stage data (base_answer, mutations, partial verifier results) is kept.
    Score/classification are not finalized — callers must not invent results.
    """
    run = db.get(Run, run_id)
    if run is None:
        return
    # Preserve base_answer and any mutations already stored on the run.
    run.status = status.value if RunStatus.is_failure(status) else RunStatus.FAILED.value
    run.analysis_error = message.strip() or GENERIC_ANALYSIS_ERROR
    # Do not publish a fake completed score/classification.
    run.classification = INCOMPLETE_CLASSIFICATION
    db.flush()


def get_run(db: Session, run_id: str) -> Run | None:
    statement = select(Run).options(selectinload(Run.mutations)).where(Run.id == run_id)
    return db.execute(statement).scalar_one_or_none()


def list_runs(db: Session, *, limit: int, offset: int) -> RunListResponse:
    total = db.execute(select(func.count()).select_from(Run)).scalar_one()
    statement = (
        select(Run)
        .order_by(desc(Run.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = db.execute(statement).scalars().all()
    return RunListResponse(
        items=[_to_run_summary(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def _is_complete(run: Run) -> bool:
    return run.status == RunStatus.COMPLETED.value


def _parse_run_status(value: str) -> RunStatus:
    if value in RunStatus._value2member_map_:
        return RunStatus(value)
    return RunStatus.COMPLETED


def _to_run_summary(run: Run) -> RunSummary:
    status = _parse_run_status(run.status)
    if not _is_complete(run):
        return RunSummary(
            id=run.id,
            question=run.question,
            generator_model=run.generator_model,
            hallucination_score=None,
            classification=None,
            status=status,
            created_at=run.created_at,
        )
    return RunSummary(
        id=run.id,
        question=run.question,
        generator_model=run.generator_model,
        hallucination_score=run.hallucination_score,
        classification=(
            Classification(run.classification)
            if run.classification in Classification._value2member_map_
            else None
        ),
        status=status,
        created_at=run.created_at,
    )


def _mutation_out(item: Mutation) -> MutationOut:
    from app.metaqa.scoring import Verdict as VerdictEnum

    verified = bool(getattr(item, "verified", True)) and bool(item.verdict)
    verdict = None
    contribution: float | None = None
    if verified:
        try:
            verdict = VerdictEnum(item.verdict)
            contribution = float(item.contribution)
        except ValueError:
            verified = False
    expected = (
        VerdictEnum(item.expected_verdict)
        if item.expected_verdict in VerdictEnum._value2member_map_
        else VerdictEnum.YES
    )
    return MutationOut(
        id=item.id,
        type=item.type,
        original_text=item.original_text,
        mutated_text=item.mutated_text,
        verdict=verdict,
        expected_verdict=expected,
        contribution=contribution,
        rationale=item.rationale if verified else "",
        parse_failed=bool(item.parse_failed) if verified else False,
        verified=verified,
    )


def to_detect_response(run: Run) -> DetectResponse:
    status = _parse_run_status(run.status)
    complete = status == RunStatus.COMPLETED
    # Expose mutations as soon as they exist (pending or verified), including after failures.
    include_mutations = status in {
        RunStatus.MUTATIONS_READY,
        RunStatus.VERIFYING_MUTATIONS,
        RunStatus.CALCULATING_SCORE,
        RunStatus.COMPLETED,
        RunStatus.MUTATION_GENERATION_FAILED,
        RunStatus.VERIFICATION_FAILED,
        RunStatus.SCORING_FAILED,
        RunStatus.FAILED,
    } or bool(run.mutations)
    timing = DetectTiming(
        answer_ms=run.answer_ms,
        mutation_ms=run.mutation_ms,
        verify_ms=run.verify_ms if complete else None,
        total_ms=run.total_ms if complete else None,
        time_to_answer_ms=run.answer_ms,
    )
    return DetectResponse(
        run_id=run.id,
        question=run.question,
        base_answer=BaseAnswerOut(text=run.base_answer, model=run.generator_model),
        mutations=[_mutation_out(item) for item in run.mutations] if include_mutations else [],
        # Never invent a score/classification when analysis did not complete.
        hallucination_score=run.hallucination_score if complete else None,
        threshold=run.threshold,
        classification=(
            Classification(run.classification)
            if complete and run.classification in Classification._value2member_map_
            else None
        ),
        not_sure_rate=run.not_sure_rate if complete else None,
        llm_mode=run.llm_mode or "live",
        status=status,
        analysis_error=run.analysis_error or None,
        created_at=run.created_at,
        timing=timing,
    )
