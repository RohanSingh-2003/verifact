import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import db_dep, get_llm_client, settings_dep
from app.config import Settings, get_settings
from app.database.db import SessionLocal
from app.llm.base import LLMClient, LLMError, LLMTimeoutError
from app.llm.client import OpenAICompatibleClient
from app.llm.mock import MockLLMClient
from app.llm.ollama import OllamaClient
from app.metaqa.detector import BaseAnswer, generate_answer, run_metaqa_analysis
from app.schemas.detect import DetectRequest, DetectResponse, RunStatus
from app.services.run_service import (
    classify_analysis_failure,
    complete_run_analysis,
    create_answer_ready_run,
    fail_run_analysis,
    persist_pending_mutations,
    to_detect_response,
    update_mutation_verification,
    update_run_status,
)

logger = logging.getLogger("verifact.api.detect")

router = APIRouter(tags=["detect"])


def _new_llm_client(settings: Settings) -> LLMClient:
    """Fresh client for background MetaQA (avoid reusing request-scoped httpx loops)."""
    if settings.llm_mode == "mock":
        return MockLLMClient(
            scenario=settings.mock_scenario,
            scenarios_by_question={
                "What is the capital of Australia?": "hallucinated",
            },
        )
    if settings.llm_provider == "ollama":
        return OllamaClient(settings)
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleClient(settings)
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


async def _continue_metaqa_analysis(
    *,
    run_id: str,
    question: str,
    answer_text: str,
    generator_model: str,
    answer_ms: float,
    request_llm: LLMClient | None = None,
) -> None:
    """Background MetaQA continuation on the app event loop. Fresh DB session.

    Mock mode reuses the request LLM (deterministic / test overrides).
    Live providers get a fresh httpx client so background work never shares
    an AsyncClient across event-loop boundaries.
    """
    settings = get_settings()
    owns_client = False
    if settings.llm_mode == "mock" and request_llm is not None:
        llm = request_llm
    else:
        llm = _new_llm_client(settings)
        owns_client = True
    db = SessionLocal()
    current_stage = RunStatus.ANSWER_READY.value
    try:
        answer = BaseAnswer(text=answer_text, model=generator_model)

        def on_stage(stage: str) -> None:
            nonlocal current_stage
            try:
                status_value = RunStatus(stage)
            except ValueError:
                return
            current_stage = status_value.value
            stage_db = SessionLocal()
            try:
                update_run_status(stage_db, run_id, status_value)
                stage_db.commit()
            except Exception:
                stage_db.rollback()
                logger.exception("failed to update run status run_id=%s stage=%s", run_id, stage)
            finally:
                stage_db.close()

        def on_mutations_ready(mutations, mutation_ms: float) -> None:
            nonlocal current_stage
            stage_db = SessionLocal()
            try:
                persist_pending_mutations(
                    stage_db,
                    run_id,
                    mutations=mutations,
                    verifier_model=settings.verifier_model,
                    mutation_ms=mutation_ms,
                )
                stage_db.commit()
                current_stage = RunStatus.MUTATIONS_READY.value
            except Exception:
                stage_db.rollback()
                logger.exception("failed to persist pending mutations run_id=%s", run_id)
            finally:
                stage_db.close()

        def on_mutation_verified(position: int, scored) -> None:
            stage_db = SessionLocal()
            try:
                update_mutation_verification(stage_db, run_id, position, scored)
                stage_db.commit()
            except Exception:
                stage_db.rollback()
                logger.exception(
                    "failed to persist mutation verification run_id=%s position=%s",
                    run_id,
                    position,
                )
            finally:
                stage_db.close()

        result = await run_metaqa_analysis(
            llm,
            question=question,
            answer=answer,
            settings=settings,
            generator_model=generator_model,
            answer_ms=answer_ms,
            on_stage=on_stage,
            on_mutations_ready=on_mutations_ready,
            on_mutation_verified=on_mutation_verified,
        )
        complete_run_analysis(db, run_id, result)
        db.commit()
        logger.info("background metaqa completed run_id=%s", run_id)
    except Exception as exc:
        db.rollback()
        logger.exception("background metaqa failed run_id=%s", run_id)
        fail_status, fail_message = classify_analysis_failure(exc, stage=current_stage)
        fail_db = SessionLocal()
        try:
            # Preserve the already-persisted answer; only mark MetaQA analysis failed.
            fail_run_analysis(fail_db, run_id, fail_message, status=fail_status)
            fail_db.commit()
        except Exception:
            fail_db.rollback()
            logger.exception("failed to mark run failed run_id=%s", run_id)
        finally:
            fail_db.close()
    finally:
        db.close()
        if owns_client:
            close = getattr(llm, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    logger.exception("failed to close background llm client")


@router.post("/api/detect", response_model=DetectResponse)
async def detect(
    payload: DetectRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
    llm: LLMClient = Depends(get_llm_client),
) -> DetectResponse:
    question = payload.cleaned_question
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a factual question.")

    if settings.llm_mode == "live" and not settings.api_key_configured:
        detail = (
            "Live Ollama mode is not ready. Check OLLAMA_BASE_URL and that the model is configured."
            if settings.is_ollama
            else "Live LLM mode is not configured. Add the required provider credentials in the backend environment or switch to Demo / Mock Mode."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )

    try:
        generator = settings.require_model(settings.generator_model)
        answer_started = time.perf_counter()
        answer = await generate_answer(
            llm,
            question,
            generator,
            max_tokens=settings.llm_answer_max_tokens,
        )
        answer_ms = round((time.perf_counter() - answer_started) * 1000, 1)

        try:
            run = create_answer_ready_run(
                db,
                question=question,
                base_answer=answer.text,
                generator_model=answer.model,
                threshold=settings.threshold,
                llm_mode=settings.llm_mode,
                answer_ms=answer_ms,
            )
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("database write failure after answer generation")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Answer was generated but could not be saved.",
            ) from exc

        background_tasks.add_task(
            _continue_metaqa_analysis,
            run_id=run.id,
            question=question,
            answer_text=answer.text,
            generator_model=answer.model,
            answer_ms=answer_ms,
            request_llm=llm if settings.llm_mode == "mock" else None,
        )
        logger.info(
            "answer ready run_id=%s llm_mode=%s answer_ms=%.0f; metaqa scheduled",
            run.id,
            settings.llm_mode,
            answer_ms,
        )
        return to_detect_response(run)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMTimeoutError as exc:
        logger.exception("Detection timed out during answer generation")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The language model timed out. Try again.",
        ) from exc
    except LLMError as exc:
        logger.exception("Detection LLM failure during answer generation")
        if "API_KEY" in str(exc) or "not configured" in str(exc):
            detail_msg = "Live LLM mode is not configured. Add the required provider credentials in the backend environment or switch to Demo / Mock Mode."
        else:
            detail_msg = "Unable to generate an answer. Check backend configuration and try again."
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail_msg,
        ) from exc
    except Exception as exc:
        logger.exception("Detection failed during answer generation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate an answer because of a server error.",
        ) from exc
