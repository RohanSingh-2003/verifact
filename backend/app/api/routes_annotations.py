from __future__ import annotations

import csv
import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_dep
from app.database.models import HumanAnnotation
from app.evaluation.agreement import compute_cohens_kappa, compute_judge_human_agreement
from app.schemas.annotation import (
    AgreementStatsOut,
    AnnotationCreateRequest,
    AnnotationOut,
    AnnotationUpdateRequest,
)

logger = logging.getLogger("verifact.api.annotations")

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


def _to_annotation_out(row: HumanAnnotation) -> AnnotationOut:
    return AnnotationOut(
        id=row.id,
        evaluation_result_id=row.evaluation_result_id,
        evaluation_run_id=row.evaluation_run_id,
        question_id=row.question_id,
        question=row.question,
        generated_answer=row.generated_answer,
        reference_answer=row.reference_answer,
        judge_label=row.judge_label,
        judge_reasoning=row.judge_reasoning,
        judge_confidence=row.judge_confidence,
        reviewer1_id=row.reviewer1_id,
        reviewer1_label=row.reviewer1_label,
        reviewer1_notes=row.reviewer1_notes,
        reviewer2_id=row.reviewer2_id,
        reviewer2_label=row.reviewer2_label,
        reviewer2_notes=row.reviewer2_notes,
        disagreement=row.disagreement,
        adjudicated_label=row.adjudicated_label,
        adjudicator_id=row.adjudicator_id,
        adjudication_notes=row.adjudication_notes,
        adjudication_evidence=row.adjudication_evidence,
        validation_status=row.validation_status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("", response_model=AnnotationOut, status_code=status.HTTP_201_CREATED)
def create_annotation(
    payload: AnnotationCreateRequest,
    db: Session = Depends(db_dep),
) -> AnnotationOut:
    # Check if annotation already exists for this evaluation_result_id
    existing = db.scalar(
        select(HumanAnnotation).where(HumanAnnotation.evaluation_result_id == payload.evaluation_result_id)
    )
    if existing is not None:
        # Update existing
        if payload.reviewer1_label is not None:
            existing.reviewer1_label = payload.reviewer1_label
            existing.reviewer1_id = payload.reviewer1_id
            existing.reviewer1_notes = payload.reviewer1_notes
        if payload.reviewer2_label is not None:
            existing.reviewer2_label = payload.reviewer2_label
            existing.reviewer2_id = payload.reviewer2_id
            existing.reviewer2_notes = payload.reviewer2_notes
        if payload.adjudicated_label is not None:
            existing.adjudicated_label = payload.adjudicated_label
            existing.adjudicator_id = payload.adjudicator_id
            existing.adjudication_notes = payload.adjudication_notes
            existing.adjudication_evidence = payload.adjudication_evidence

        # Check disagreement
        if existing.reviewer1_label and existing.reviewer2_label:
            existing.disagreement = (existing.reviewer1_label != existing.reviewer2_label)

        if existing.adjudicated_label:
            existing.validation_status = "adjudicated"
        elif existing.reviewer1_label and existing.reviewer2_label:
            existing.validation_status = "reviewed"
        db.commit()
        db.refresh(existing)
        return _to_annotation_out(existing)

    disagreement = False
    if payload.reviewer1_label and payload.reviewer2_label:
        disagreement = (payload.reviewer1_label != payload.reviewer2_label)

    status_str = "pending"
    if payload.adjudicated_label:
        status_str = "adjudicated"
    elif payload.reviewer1_label and payload.reviewer2_label:
        status_str = "reviewed"

    row = HumanAnnotation(
        evaluation_result_id=payload.evaluation_result_id,
        evaluation_run_id=payload.evaluation_run_id,
        question_id=payload.question_id,
        question=payload.question,
        generated_answer=payload.generated_answer,
        reference_answer=payload.reference_answer,
        judge_label=payload.judge_label,
        judge_reasoning=payload.judge_reasoning,
        judge_confidence=payload.judge_confidence,
        reviewer1_id=payload.reviewer1_id,
        reviewer1_label=payload.reviewer1_label,
        reviewer1_notes=payload.reviewer1_notes,
        reviewer2_id=payload.reviewer2_id,
        reviewer2_label=payload.reviewer2_label,
        reviewer2_notes=payload.reviewer2_notes,
        disagreement=disagreement,
        adjudicated_label=payload.adjudicated_label,
        adjudicator_id=payload.adjudicator_id,
        adjudication_notes=payload.adjudication_notes,
        adjudication_evidence=payload.adjudication_evidence,
        validation_status=status_str,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_annotation_out(row)


@router.put("/{annotation_id}", response_model=AnnotationOut)
@router.patch("/{annotation_id}", response_model=AnnotationOut)
def update_annotation(
    annotation_id: str,
    payload: AnnotationUpdateRequest,
    db: Session = Depends(db_dep),
) -> AnnotationOut:
    row = db.get(HumanAnnotation, annotation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found.")

    if payload.reviewer1_label is not None:
        row.reviewer1_label = payload.reviewer1_label
        row.reviewer1_id = payload.reviewer1_id
        row.reviewer1_notes = payload.reviewer1_notes
    if payload.reviewer2_label is not None:
        row.reviewer2_label = payload.reviewer2_label
        row.reviewer2_id = payload.reviewer2_id
        row.reviewer2_notes = payload.reviewer2_notes
    if payload.adjudicated_label is not None:
        row.adjudicated_label = payload.adjudicated_label
        row.adjudicator_id = payload.adjudicator_id
        row.adjudication_notes = payload.adjudication_notes
        row.adjudication_evidence = payload.adjudication_evidence

    if row.reviewer1_label and row.reviewer2_label:
        row.disagreement = (row.reviewer1_label != row.reviewer2_label)

    if row.adjudicated_label:
        row.validation_status = "adjudicated"
    elif row.reviewer1_label and row.reviewer2_label:
        row.validation_status = "reviewed"

    db.commit()
    db.refresh(row)
    return _to_annotation_out(row)


@router.get("", response_model=list[AnnotationOut])
def list_annotations(
    evaluation_run_id: str | None = Query(default=None),
    validation_status: str | None = Query(default=None),
    disagreement_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(db_dep),
) -> list[AnnotationOut]:
    stmt = select(HumanAnnotation)
    if evaluation_run_id:
        stmt = stmt.where(HumanAnnotation.evaluation_run_id == evaluation_run_id)
    if validation_status:
        stmt = stmt.where(HumanAnnotation.validation_status == validation_status)
    if disagreement_only:
        stmt = stmt.where(HumanAnnotation.disagreement.is_(True))

    stmt = stmt.order_by(HumanAnnotation.created_at.desc()).limit(limit)
    rows = db.scalars(stmt).all()
    return [_to_annotation_out(r) for r in rows]


@router.get("/agreement", response_model=AgreementStatsOut)
def get_agreement_statistics(
    evaluation_run_id: str | None = Query(default=None),
    db: Session = Depends(db_dep),
) -> AgreementStatsOut:
    stmt = select(HumanAnnotation)
    if evaluation_run_id:
        stmt = stmt.where(HumanAnnotation.evaluation_run_id == evaluation_run_id)

    rows = db.scalars(stmt).all()
    total = len(rows)

    both_reviewed = [r for r in rows if r.reviewer1_label and r.reviewer2_label]
    both_count = len(both_reviewed)

    r1_list = [r.reviewer1_label for r in both_reviewed if r.reviewer1_label]
    r2_list = [r.reviewer2_label for r in both_reviewed if r.reviewer2_label]

    human_kappa = compute_cohens_kappa(r1_list, r2_list) if both_count >= 2 else None
    matches = sum(1 for r1, r2 in zip(r1_list, r2_list, strict=True) if r1 == r2)
    observed_agreement = round(matches / both_count, 4) if both_count > 0 else None

    disagreements = sum(1 for r in rows if r.disagreement)
    adjudicated = sum(1 for r in rows if r.adjudicated_label)

    # Judge vs Adjudicated human agreement
    judge_adj_pairs = [
        (r.judge_label, r.adjudicated_label)
        for r in rows
        if r.judge_label and r.adjudicated_label
    ]
    judge_stats = compute_judge_human_agreement(
        [j for j, _ in judge_adj_pairs if j],
        [a for _, a in judge_adj_pairs if a],
    )

    label_counts: dict[str, int] = {}
    for r in rows:
        effective = r.adjudicated_label or r.reviewer1_label or r.judge_label or "UNREVIEWED"
        label_counts[effective] = label_counts.get(effective, 0) + 1

    return AgreementStatsOut(
        total_annotated=total,
        both_reviewed_count=both_count,
        human_cohens_kappa=human_kappa,
        human_observed_agreement=observed_agreement,
        disagreements_count=disagreements,
        adjudicated_count=adjudicated,
        judge_human_observed_agreement=judge_stats.get("observed_agreement"),
        judge_human_cohens_kappa=judge_stats.get("cohens_kappa"),
        label_distribution=label_counts,
    )


@router.get("/export")
def export_annotations_csv(
    evaluation_run_id: str | None = Query(default=None),
    db: Session = Depends(db_dep),
) -> Response:
    stmt = select(HumanAnnotation)
    if evaluation_run_id:
        stmt = stmt.where(HumanAnnotation.evaluation_run_id == evaluation_run_id)

    rows = db.scalars(stmt).all()

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "id",
            "evaluation_result_id",
            "evaluation_run_id",
            "question_id",
            "question",
            "reference_answer",
            "generated_answer",
            "judge_label",
            "judge_confidence",
            "judge_reasoning",
            "reviewer1_id",
            "reviewer1_label",
            "reviewer1_notes",
            "reviewer2_id",
            "reviewer2_label",
            "reviewer2_notes",
            "disagreement",
            "adjudicated_label",
            "adjudicator_id",
            "adjudication_notes",
            "adjudication_evidence",
            "validation_status",
            "created_at",
            "updated_at",
        ],
    )
    writer.writeheader()
    for r in rows:
        writer.writerow(
            {
                "id": r.id,
                "evaluation_result_id": r.evaluation_result_id,
                "evaluation_run_id": r.evaluation_run_id or "",
                "question_id": r.question_id,
                "question": r.question,
                "reference_answer": r.reference_answer,
                "generated_answer": r.generated_answer,
                "judge_label": r.judge_label or "",
                "judge_confidence": r.judge_confidence if r.judge_confidence is not None else "",
                "judge_reasoning": r.judge_reasoning or "",
                "reviewer1_id": r.reviewer1_id or "",
                "reviewer1_label": r.reviewer1_label or "",
                "reviewer1_notes": r.reviewer1_notes or "",
                "reviewer2_id": r.reviewer2_id or "",
                "reviewer2_label": r.reviewer2_label or "",
                "reviewer2_notes": r.reviewer2_notes or "",
                "disagreement": r.disagreement,
                "adjudicated_label": r.adjudicated_label or "",
                "adjudicator_id": r.adjudicator_id or "",
                "adjudication_notes": r.adjudication_notes or "",
                "adjudication_evidence": r.adjudication_evidence or "",
                "validation_status": r.validation_status,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            }
        )

    filename = f"human_annotations_{evaluation_run_id or 'all'}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
