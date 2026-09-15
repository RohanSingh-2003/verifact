from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import db_dep
from app.schemas.detect import DetectResponse, RunListResponse
from app.services.run_service import get_run, list_runs, to_detect_response

router = APIRouter(tags=["runs"])


@router.get("/api/runs", response_model=RunListResponse)
def read_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(db_dep),
) -> RunListResponse:
    try:
        return list_runs(db, limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load run history.",
        ) from exc


@router.get("/api/runs/{run_id}", response_model=DetectResponse)
def read_run(run_id: str, db: Session = Depends(db_dep)) -> DetectResponse:
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return to_detect_response(run)
