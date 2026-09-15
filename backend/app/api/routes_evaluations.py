import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import db_dep, get_llm_client, settings_dep
from app.config import Settings
from app.evaluation.dataset_loader import DatasetError
from app.evaluation.evaluator import EvaluationConfigError, run_evaluation
from app.llm.base import LLMClient, LLMError, LLMTimeoutError
from app.schemas.evaluation import (
    EvaluationDetail,
    EvaluationListResponse,
    EvaluationRunRequest,
)
from app.services.evaluation_service import (
    export_csv,
    export_threshold_sweep_csv,
    get_evaluation,
    list_evaluations,
    to_detail,
)

logger = logging.getLogger("verifact.api.evaluation")

router = APIRouter(tags=["evaluations"])


@router.post("/api/evaluations/run", response_model=EvaluationDetail)
async def create_evaluation(
    payload: EvaluationRunRequest,
    db: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
    llm: LLMClient = Depends(get_llm_client),
) -> EvaluationDetail:
    try:
        run = await run_evaluation(
            llm=llm,
            db=db,
            settings=settings,
            dataset=payload.dataset,
            threshold=payload.threshold,
            name=payload.name,
            max_questions=payload.max_questions,
            confirm_live_run=payload.confirm_live_run,
            generator_model=payload.generator_model,
            verifier_model=payload.verifier_model,
        )
        db.refresh(run)
        loaded = get_evaluation(db, run.id)
        if loaded is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Evaluation did not persist.")
        return to_detail(loaded)
    except (DatasetError, EvaluationConfigError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The language model timed out during evaluation.",
        ) from exc
    except LLMError as exc:
        logger.exception("Evaluation LLM failure")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The language model request failed during evaluation.",
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Evaluation database failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Evaluation could not be saved.",
        ) from exc


@router.get("/api/evaluations", response_model=EvaluationListResponse)
def read_evaluations(db: Session = Depends(db_dep)) -> EvaluationListResponse:
    return list_evaluations(db)


@router.get("/api/evaluations/{evaluation_id}", response_model=EvaluationDetail)
def read_evaluation(evaluation_id: str, db: Session = Depends(db_dep)) -> EvaluationDetail:
    run = get_evaluation(db, evaluation_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found.")
    return to_detail(run)


@router.get("/api/evaluations/{evaluation_id}/export")
def export_evaluation(evaluation_id: str, db: Session = Depends(db_dep)) -> Response:
    run = get_evaluation(db, evaluation_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found.")
    body = export_csv(run)
    filename = f"verifact-evaluation-{run.dataset_name}-{evaluation_id[:8]}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/evaluations/{evaluation_id}/export/sweep")
def export_evaluation_sweep(evaluation_id: str, db: Session = Depends(db_dep)) -> Response:
    run = get_evaluation(db, evaluation_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found.")
    body = export_threshold_sweep_csv(run)
    filename = f"verifact-evaluation-sweep-{run.dataset_name}-{evaluation_id[:8]}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
