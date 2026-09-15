import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import db_dep, get_llm_client, settings_dep
from app.config import Settings
from app.llm.base import LLMClient, LLMError, LLMTimeoutError
from app.metaqa.detector import run_detection
from app.schemas.detect import DetectRequest, DetectResponse
from app.services.run_service import persist_detection

logger = logging.getLogger("verifact.api.detect")

router = APIRouter(tags=["detect"])


@router.post("/api/detect", response_model=DetectResponse)
async def detect(
    payload: DetectRequest,
    db: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
    llm: LLMClient = Depends(get_llm_client),
) -> DetectResponse:
    question = payload.cleaned_question
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a factual question.")

    if settings.llm_mode == "live" and not settings.api_key_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live LLM mode is not configured. Add the required provider credentials in the backend environment or switch to Demo / Mock Mode.",
        )

    try:
        result = await run_detection(llm, question=question, settings=settings)
        try:
            saved = persist_detection(db, result)
        except SQLAlchemyError as exc:
            logger.exception("database write failure")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Detection completed but could not be saved.",
            ) from exc
        logger.info("run persisted run_id=%s llm_mode=%s", saved.run_id, saved.llm_mode)
        return saved
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMTimeoutError as exc:
        logger.exception("Detection timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The language model timed out. Try again.",
        ) from exc
    except LLMError as exc:
        logger.exception("Detection LLM failure")
        if "API_KEY" in str(exc) or "not configured" in str(exc):
            detail_msg = "Live LLM mode is not configured. Add the required provider credentials in the backend environment or switch to Demo / Mock Mode."
        else:
            detail_msg = "The language model request failed. Check backend configuration and try again."
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail_msg,
        ) from exc
    except Exception as exc:
        logger.exception("Detection failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detection failed because of a server error.",
        ) from exc
