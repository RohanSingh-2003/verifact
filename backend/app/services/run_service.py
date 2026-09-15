from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import Mutation, Run, new_id
from app.metaqa.detector import DetectionResult
from app.schemas.detect import (
    BaseAnswerOut,
    DetectResponse,
    MutationOut,
    RunListResponse,
    RunSummary,
)


def persist_detection(db: Session, result: DetectionResult) -> DetectResponse:
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
    )
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
                position=index,
            )
        )
    db.add(run)
    db.flush()
    db.refresh(run)
    return to_detect_response(run)


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
        items=[
            RunSummary(
                id=row.id,
                question=row.question,
                generator_model=row.generator_model,
                hallucination_score=row.hallucination_score,
                classification=row.classification,
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def to_detect_response(run: Run) -> DetectResponse:
    return DetectResponse(
        run_id=run.id,
        question=run.question,
        base_answer=BaseAnswerOut(text=run.base_answer, model=run.generator_model),
        mutations=[
            MutationOut(
                id=item.id,
                type=item.type,
                original_text=item.original_text,
                mutated_text=item.mutated_text,
                verdict=item.verdict,
                expected_verdict=item.expected_verdict,
                contribution=item.contribution,
                rationale=item.rationale,
                parse_failed=bool(item.parse_failed),
            )
            for item in run.mutations
        ],
        hallucination_score=run.hallucination_score,
        threshold=run.threshold,
        classification=run.classification,
        not_sure_rate=run.not_sure_rate,
        llm_mode=run.llm_mode or "live",
        created_at=run.created_at,
    )
