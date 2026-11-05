"""Reviewer-blinded annotation API endpoints.

These endpoints enforce strict blinding and submission isolation for the
human annotation workflow. Each reviewer sees only their own annotations
and can only submit/update their own fields. Neither reviewer can see
the other's labels, Gemini judge predictions, or VeriFact internal scores.

Authentication is handled via Bearer tokens mapped to reviewer roles.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_dep
from app.api.reviewer_auth import (
    ReviewerRole,
    require_adjudicator,
    require_reviewer,
)
from app.database.models import AnnotationAuditLog, HumanAnnotation
from app.schemas.annotation import AnnotationLabel

logger = logging.getLogger("verifact.api.blinded_annotations")

router = APIRouter(prefix="/api/review", tags=["blinded-annotations"])


# ─── Request / Response Schemas ───────────────────────────────────────────────


class ReviewerSubmission(BaseModel):
    """Payload for a reviewer to submit or update their annotation."""

    label: AnnotationLabel
    notes: str = ""
    evidence_url: str | None = None
    source_name: str | None = None
    source_publication_date: str | None = None
    fact_effective_date: str | None = None
    evidence_excerpt: str | None = None


class BlindedTaskOut(BaseModel):
    """A single annotation task visible to an authenticated reviewer.

    Deliberately excludes: other reviewer's data, judge predictions,
    MetaQA/web evidence/combined scores, and detector classifications.
    """

    annotation_id: str
    question_id: str
    question: str
    generated_answer: str
    reference_answer: str
    my_label: str | None = None
    my_notes: str | None = None
    my_evidence_url: str | None = None
    my_source_name: str | None = None
    my_source_publication_date: str | None = None
    my_fact_effective_date: str | None = None
    my_evidence_excerpt: str | None = None
    my_submitted_at: datetime | None = None
    validation_status: str


class AdjudicationTaskOut(BaseModel):
    """A disagreement task visible to the adjudicator.

    Shows both reviewers' labels and notes for resolution, but still
    excludes detector predictions, MetaQA scores, and web evidence scores.
    """

    annotation_id: str
    question_id: str
    question: str
    generated_answer: str
    reference_answer: str
    reviewer1_label: str | None
    reviewer1_notes: str | None
    reviewer2_label: str | None
    reviewer2_notes: str | None
    adjudicated_label: str | None
    adjudication_notes: str | None
    adjudication_evidence: str | None
    validation_status: str


class AdjudicationSubmission(BaseModel):
    """Payload for the adjudicator to submit a resolution."""

    label: AnnotationLabel
    notes: str = ""
    evidence: str = ""


class BlindedStatsOut(BaseModel):
    """Summary statistics visible to an authenticated reviewer."""

    total_assigned: int
    my_completed: int
    my_remaining: int


# ─── Helper Functions ─────────────────────────────────────────────────────────


def _my_label(row: HumanAnnotation, role: ReviewerRole) -> str | None:
    if role == ReviewerRole.REVIEWER1:
        return row.reviewer1_label
    return row.reviewer2_label


def _my_notes(row: HumanAnnotation, role: ReviewerRole) -> str | None:
    if role == ReviewerRole.REVIEWER1:
        return row.reviewer1_notes
    return row.reviewer2_notes


def _to_blinded_task(row: HumanAnnotation, role: ReviewerRole) -> BlindedTaskOut:
    """Convert a HumanAnnotation row to a blinded view for a specific reviewer."""
    return BlindedTaskOut(
        annotation_id=row.id,
        question_id=row.question_id,
        question=row.question,
        generated_answer=row.generated_answer,
        reference_answer=row.reference_answer,
        my_label=_my_label(row, role),
        my_notes=_my_notes(row, role),
        my_evidence_url=None,  # structured evidence fields added below when schema supports them
        my_source_name=None,
        my_source_publication_date=None,
        my_fact_effective_date=None,
        my_evidence_excerpt=None,
        my_submitted_at=row.updated_at if _my_label(row, role) else None,
        validation_status=row.validation_status,
    )


def _to_adjudication_task(row: HumanAnnotation) -> AdjudicationTaskOut:
    """Convert a HumanAnnotation row to an adjudication view."""
    return AdjudicationTaskOut(
        annotation_id=row.id,
        question_id=row.question_id,
        question=row.question,
        generated_answer=row.generated_answer,
        reference_answer=row.reference_answer,
        reviewer1_label=row.reviewer1_label,
        reviewer1_notes=row.reviewer1_notes,
        reviewer2_label=row.reviewer2_label,
        reviewer2_notes=row.reviewer2_notes,
        adjudicated_label=row.adjudicated_label,
        adjudication_notes=row.adjudication_notes,
        adjudication_evidence=row.adjudication_evidence,
        validation_status=row.validation_status,
    )


# ─── Reviewer Endpoints ──────────────────────────────────────────────────────


@router.get("/tasks", response_model=list[BlindedTaskOut])
def list_reviewer_tasks(
    role: ReviewerRole = Depends(require_reviewer),
    evaluation_run_id: str | None = Query(default=None),
    pending_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(db_dep),
) -> list[BlindedTaskOut]:
    """List annotation tasks for the authenticated reviewer, blinded."""
    stmt = select(HumanAnnotation)
    if evaluation_run_id:
        stmt = stmt.where(HumanAnnotation.evaluation_run_id == evaluation_run_id)

    if pending_only:
        if role == ReviewerRole.REVIEWER1:
            stmt = stmt.where(HumanAnnotation.reviewer1_label.is_(None))
        else:
            stmt = stmt.where(HumanAnnotation.reviewer2_label.is_(None))

    stmt = stmt.order_by(HumanAnnotation.created_at).limit(limit)
    rows = db.scalars(stmt).all()
    return [_to_blinded_task(r, role) for r in rows]


@router.get("/tasks/{annotation_id}", response_model=BlindedTaskOut)
def get_reviewer_task(
    annotation_id: str,
    role: ReviewerRole = Depends(require_reviewer),
    db: Session = Depends(db_dep),
) -> BlindedTaskOut:
    """Get a single annotation task, blinded for the authenticated reviewer."""
    row = db.get(HumanAnnotation, annotation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found.")
    return _to_blinded_task(row, role)


@router.post("/tasks/{annotation_id}/submit", response_model=BlindedTaskOut)
def submit_reviewer_annotation(
    annotation_id: str,
    payload: ReviewerSubmission,
    role: ReviewerRole = Depends(require_reviewer),
    db: Session = Depends(db_dep),
) -> BlindedTaskOut:
    """Submit or update the authenticated reviewer's annotation for a task.

    Enforces:
    - Reviewer 1 can only write reviewer1_* fields.
    - Reviewer 2 can only write reviewer2_* fields.
    - Neither can overwrite the other's data.
    - A previously submitted label triggers a correction audit trail.
    """
    row = db.get(HumanAnnotation, annotation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found.")

    if role == ReviewerRole.REVIEWER1:
        previous_label = row.reviewer1_label
        previous_notes = row.reviewer1_notes
        if previous_label is None:
            action = "initial_submission"
            row.reviewer1_notes = payload.notes
        elif previous_label != payload.label:
            action = "label_correction"
            correction_note = (
                f"[CORRECTION {datetime.now(UTC).isoformat()}] "
                f"Changed from '{previous_label}' to '{payload.label}'. "
                f"Previous notes: {previous_notes or '(none)'}. "
                f"New notes: {payload.notes}"
            )
            row.reviewer1_notes = correction_note
        elif previous_notes != payload.notes:
            action = "notes_correction"
            row.reviewer1_notes = payload.notes
        else:
            action = "resubmission"
            row.reviewer1_notes = payload.notes

        row.reviewer1_label = payload.label
        row.reviewer1_id = "reviewer1"
    else:
        previous_label = row.reviewer2_label
        previous_notes = row.reviewer2_notes
        if previous_label is None:
            action = "initial_submission"
            row.reviewer2_notes = payload.notes
        elif previous_label != payload.label:
            action = "label_correction"
            correction_note = (
                f"[CORRECTION {datetime.now(UTC).isoformat()}] "
                f"Changed from '{previous_label}' to '{payload.label}'. "
                f"Previous notes: {previous_notes or '(none)'}. "
                f"New notes: {payload.notes}"
            )
            row.reviewer2_notes = correction_note
        elif previous_notes != payload.notes:
            action = "notes_correction"
            row.reviewer2_notes = payload.notes
        else:
            action = "resubmission"
            row.reviewer2_notes = payload.notes

        row.reviewer2_label = payload.label
        row.reviewer2_id = "reviewer2"

    audit_entry = AnnotationAuditLog(
        annotation_id=row.id,
        question_id=row.question_id,
        actor_role=role.value,
        action=action,
        previous_label=previous_label,
        new_label=payload.label,
        previous_notes=previous_notes,
        new_notes=payload.notes,
    )
    db.add(audit_entry)

    # Recalculate disagreement and status
    if row.reviewer1_label and row.reviewer2_label:
        row.disagreement = row.reviewer1_label != row.reviewer2_label
        if row.adjudicated_label:
            row.validation_status = "adjudicated"
        else:
            row.validation_status = "reviewed"
    elif row.reviewer1_label or row.reviewer2_label:
        row.validation_status = "pending"

    db.commit()
    db.refresh(row)
    return _to_blinded_task(row, role)


@router.get("/stats", response_model=BlindedStatsOut)
def get_reviewer_stats(
    role: ReviewerRole = Depends(require_reviewer),
    evaluation_run_id: str | None = Query(default=None),
    db: Session = Depends(db_dep),
) -> BlindedStatsOut:
    """Get annotation progress statistics for the authenticated reviewer."""
    stmt = select(HumanAnnotation)
    if evaluation_run_id:
        stmt = stmt.where(HumanAnnotation.evaluation_run_id == evaluation_run_id)

    rows = db.scalars(stmt).all()
    total = len(rows)

    if role == ReviewerRole.REVIEWER1:
        completed = sum(1 for r in rows if r.reviewer1_label is not None)
    else:
        completed = sum(1 for r in rows if r.reviewer2_label is not None)

    return BlindedStatsOut(
        total_assigned=total,
        my_completed=completed,
        my_remaining=total - completed,
    )


# ─── Adjudicator Endpoints ───────────────────────────────────────────────────


@router.get("/adjudicate", response_model=list[AdjudicationTaskOut])
def list_adjudication_tasks(
    role: ReviewerRole = Depends(require_adjudicator),
    evaluation_run_id: str | None = Query(default=None),
    pending_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(db_dep),
) -> list[AdjudicationTaskOut]:
    """List disagreements requiring adjudication.

    Only returns tasks where both reviewers have submitted and they disagree.
    """
    stmt = select(HumanAnnotation).where(
        HumanAnnotation.reviewer1_label.is_not(None),
        HumanAnnotation.reviewer2_label.is_not(None),
        HumanAnnotation.disagreement.is_(True),
    )
    if evaluation_run_id:
        stmt = stmt.where(HumanAnnotation.evaluation_run_id == evaluation_run_id)
    if pending_only:
        stmt = stmt.where(HumanAnnotation.adjudicated_label.is_(None))

    stmt = stmt.order_by(HumanAnnotation.created_at).limit(limit)
    rows = db.scalars(stmt).all()
    return [_to_adjudication_task(r) for r in rows]


@router.post("/adjudicate/{annotation_id}", response_model=AdjudicationTaskOut)
def submit_adjudication(
    annotation_id: str,
    payload: AdjudicationSubmission,
    role: ReviewerRole = Depends(require_adjudicator),
    db: Session = Depends(db_dep),
) -> AdjudicationTaskOut:
    """Submit an adjudication decision for a disagreement.

    Enforces:
    - Both reviewers must have already submitted.
    - The adjudicator identity is distinct from both reviewers (enforced by token).
    - Original reviewer labels are preserved.
    """
    row = db.get(HumanAnnotation, annotation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found.")

    if not row.reviewer1_label or not row.reviewer2_label:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Both reviewers must submit annotations before adjudication.",
        )

    previous_label = row.adjudicated_label
    previous_notes = row.adjudication_notes
    action = "initial_adjudication" if previous_label is None else "adjudication_correction"

    row.adjudicated_label = payload.label
    row.adjudicator_id = "adjudicator"
    row.adjudication_notes = payload.notes
    row.adjudication_evidence = payload.evidence
    row.validation_status = "adjudicated"

    audit_entry = AnnotationAuditLog(
        annotation_id=row.id,
        question_id=row.question_id,
        actor_role=role.value,
        action=action,
        previous_label=previous_label,
        new_label=payload.label,
        previous_notes=previous_notes,
        new_notes=payload.notes,
    )
    db.add(audit_entry)

    db.commit()
    db.refresh(row)
    return _to_adjudication_task(row)

