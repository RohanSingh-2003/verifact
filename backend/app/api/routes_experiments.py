import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import db_dep, get_llm_client, settings_dep
from app.config import Settings
from app.evaluation.dataset_loader import DatasetError
from app.llm.base import LLMClient, LLMError, LLMTimeoutError
from app.schemas.experiment import ExperimentConfigError, ExperimentIntegrityError, ExperimentRunRequest
from app.services.experiment_service import (
    estimate_from_request,
    export_condition_summary_csv,
    export_conditions_csv,
    export_flip_csv,
    export_paired_csv,
    export_research_log_json,
    export_threshold_sweep_csv,
    generation_trace,
    get_experiment,
    get_latest_experiment,
    run_experiment,
    to_experiment_out,
)

logger = logging.getLogger("verifact.api.experiments")

router = APIRouter(tags=["experiments"])


@router.post("/api/experiments/estimate")
def estimate_experiment(
    payload: ExperimentRunRequest | None = None,
    settings: Settings = Depends(settings_dep),
) -> dict:
    request = payload or ExperimentRunRequest()
    try:
        return estimate_from_request(request, settings)
    except (ExperimentConfigError, DatasetError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/api/experiments/run")
async def create_experiment(
    payload: ExperimentRunRequest | None = None,
    db: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
    llm: LLMClient = Depends(get_llm_client),
) -> dict:
    request = payload or ExperimentRunRequest()
    try:
        experiment = await run_experiment(llm=llm, db=db, settings=settings, payload=request)
        loaded = get_experiment(db, experiment.id)
        if loaded is None:
            raise HTTPException(status_code=500, detail="Experiment did not persist.")
        return to_experiment_out(loaded)
    except (ExperimentConfigError, DatasetError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ExperimentIntegrityError as exc:
        logger.exception("Experiment integrity failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Experiment failed an integrity check on fixed mutation reuse.",
        ) from exc
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The language model timed out during the experiment.",
        ) from exc
    except LLMError as exc:
        logger.exception("Experiment LLM failure")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The language model request failed during the experiment.",
        ) from exc


@router.get("/api/experiments/latest")
def read_latest_experiment(db: Session = Depends(db_dep)) -> dict:
    experiment = get_latest_experiment(db)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No experiment has been created yet.")
    return to_experiment_out(experiment)


@router.get("/api/experiments/{experiment_id}")
def read_experiment(experiment_id: str, db: Session = Depends(db_dep)) -> dict:
    experiment = get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found.")
    return to_experiment_out(experiment)


@router.get("/api/experiments/{experiment_id}/traces/{generation_id}")
def read_generation_trace(experiment_id: str, generation_id: str, db: Session = Depends(db_dep)) -> dict:
    experiment = get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found.")
    trace = generation_trace(experiment, generation_id)
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation trace not found.")
    return trace


@router.get("/api/experiments/{experiment_id}/export")
def export_experiment(experiment_id: str, db: Session = Depends(db_dep)) -> Response:
    experiment = get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found.")
    body = export_conditions_csv(experiment)
    filename = f"verifact-experiment-{experiment_id[:8]}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/experiments/{experiment_id}/export/paired")
def export_experiment_paired(experiment_id: str, db: Session = Depends(db_dep)) -> Response:
    experiment = get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found.")
    body = export_paired_csv(experiment)
    filename = f"verifact-experiment-paired-{experiment_id[:8]}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/experiments/{experiment_id}/export/summary")
def export_experiment_summary(experiment_id: str, db: Session = Depends(db_dep)) -> Response:
    experiment = get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found.")
    body = export_condition_summary_csv(experiment)
    filename = f"verifact-experiment-summary-{experiment_id[:8]}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/experiments/{experiment_id}/export/flips")
def export_experiment_flips(experiment_id: str, db: Session = Depends(db_dep)) -> Response:
    experiment = get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found.")
    body = export_flip_csv(experiment)
    filename = f"verifact-experiment-flips-{experiment_id[:8]}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/experiments/{experiment_id}/export/sweep")
def export_experiment_sweep(experiment_id: str, db: Session = Depends(db_dep)) -> Response:
    experiment = get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found.")
    body = export_threshold_sweep_csv(experiment)
    filename = f"verifact-experiment-sweep-{experiment_id[:8]}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/experiments/{experiment_id}/export/config")
def export_experiment_config(experiment_id: str, db: Session = Depends(db_dep)) -> Response:
    experiment = get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found.")
    body = export_research_log_json(experiment)
    filename = f"verifact-experiment-config-{experiment_id[:8]}.json"
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
