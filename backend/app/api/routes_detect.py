import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import db_dep, get_gemini_verifier_client, get_llm_client, settings_dep
from app.config import Settings, get_settings
from app.database.db import SessionLocal
from app.llm.base import LLMClient, LLMError, LLMTimeoutError
from app.llm.mock import MockLLMClient
from app.llm.providers import ModelClientLLMAdapter
from app.metaqa.detector import BaseAnswer, generate_answer, run_metaqa_analysis
from app.metaqa.detector import MetaqaVerificationUnavailable
from app.schemas.detect import DetectRequest, DetectResponse, RunStatus
from app.services.run_service import (
    classify_analysis_failure,
    complete_run_analysis,
    create_answer_ready_run,
    fail_run_analysis,
    persist_pending_mutations,
    persist_web_evidence_result,
    to_detect_response,
    update_mutation_verification,
    update_run_status,
    update_web_evidence_status,
)
from app.web_evidence.pipeline import build_web_search_client, run_web_evidence, unavailable_result
from app.web_evidence.types import WebEvidenceResult, WebEvidenceStatus

logger = logging.getLogger("verifact.api.detect")

router = APIRouter(tags=["detect"])





def _new_verifier_for_pool(
    settings: Settings,
    *,
    selected_answer_model: str,
) -> tuple[LLMClient | None, str]:
    """Select a verifier client and model identifier from the verifier pool.

    The selected answer model is ALWAYS excluded from the verifier pool.
    """
    from app.llm.registry import MODEL_REGISTRY, get_model_client, is_model_configured

    if selected_answer_model != "gemini" and settings.gemini_configured:
        from app.llm.gemini import GeminiClient
        client = GeminiClient(
            api_key=settings.gemini_api_key,
            default_model=settings.gemini_verifier_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            temperature=settings.llm_temperature,
        )
        return client, settings.gemini_verifier_model

    # If Gemini is the answer model, or not configured, pick another configured candidate
    for candidate_id in ("gemma", "glm", "qwen", "openrouter"):
        if candidate_id == selected_answer_model:
            continue
        if is_model_configured(candidate_id, settings):
            model_client = get_model_client(candidate_id, settings)
            mdef = MODEL_REGISTRY[candidate_id]
            return ModelClientLLMAdapter(model_client), mdef.default_model_name

    return None, ""


def _new_gemini_verifier(settings: Settings) -> LLMClient | None:
    """Fresh Gemini verifier client for background MetaQA verification."""
    if settings.gemini_configured:
        from app.llm.gemini import GeminiClient
        return GeminiClient(
            api_key=settings.gemini_api_key,
            default_model=settings.gemini_verifier_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            temperature=settings.llm_temperature,
        )
    return None


async def _continue_metaqa_analysis(
    *,
    run_id: str,
    question: str,
    answer_text: str,
    generator_model: str,
    answer_ms: float,
    selected_answer_model: str = "gemma",
    request_llm: LLMClient | None = None,
    request_verifier_llm: LLMClient | None = None,
) -> None:
    """Background MetaQA continuation on the app event loop. Fresh DB session.

    RESEARCH ARCHITECTURE:
    1. Selected model generates answer + mutations.
    2. ALL OTHER AVAILABLE MODELS in MODEL_REGISTRY independently verify every mutation.
    3. Selected model is NEVER included as a verifier.
    """
    settings = get_settings()
    owns_client = False
    is_test_mock = isinstance(request_llm, MockLLMClient)
    if is_test_mock and request_llm is not None:
        llm = request_llm
    else:
        from app.llm.registry import get_model_client
        model_client = get_model_client(selected_answer_model, settings)
        llm = ModelClientLLMAdapter(model_client)
        owns_client = True

    from app.llm.registry import MODEL_REGISTRY, is_model_configured
    verifier_model_ids = [m for m in MODEL_REGISTRY.keys() if m != selected_answer_model]

    if settings.llm_mode == "live" and not any(is_model_configured(m, settings) for m in verifier_model_ids):
        db = SessionLocal()
        try:
            fail_run_analysis(
                db,
                run_id,
                f"No independent verifiers available in verifier pool (answer model: {selected_answer_model}). Configure cloud provider credentials.",
                status=RunStatus.VERIFICATION_FAILED,
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("failed to mark verifier unavailable run_id=%s", run_id)
        finally:
            db.close()
        return

    verifier_summary_label = ", ".join(MODEL_REGISTRY[m].display_name for m in verifier_model_ids if m in MODEL_REGISTRY)
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
                    verifier_model=verifier_summary_label,
                    verifier_models=verifier_model_ids,
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
            verifier_model=verifier_summary_label,
            verifier_models=verifier_model_ids,
            verifier_llm=request_verifier_llm if is_test_mock else None,
            answer_ms=answer_ms,
            on_stage=on_stage,
            on_mutations_ready=on_mutations_ready,
            on_mutation_verified=on_mutation_verified,
        )
        complete_run_analysis(db, run_id, result)
        db.commit()
        logger.info(
            "background metaqa completed run_id=%s completion=%s verified=%s/%s",
            run_id,
            result.metaqa_completion,
            result.verified_count,
            result.expected_count,
        )
    except MetaqaVerificationUnavailable as exc:
        db.rollback()
        logger.warning("background metaqa unavailable run_id=%s: %s", run_id, exc)
        fail_status, fail_message = classify_analysis_failure(exc, stage="verifying_mutations")
        fail_db = SessionLocal()
        try:
            fail_run_analysis(
                fail_db,
                run_id,
                fail_message,
                status=fail_status,
            )
            fail_db.commit()
        except Exception:
            fail_db.rollback()
            logger.exception("failed to mark metaqa unavailable run_id=%s", run_id)
        finally:
            fail_db.close()
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



async def _continue_web_evidence(
    *,
    run_id: str,
    question: str,
    answer_text: str,
    selected_answer_model: str = "gemma",
    request_llm: LLMClient | None = None,
) -> None:
    """Background Web Evidence pipeline — independent of MetaQA status/fields."""
    settings = get_settings()
    owns_client = False
    if isinstance(request_llm, MockLLMClient) and request_llm is not None:
        llm = request_llm
    else:
        from app.llm.registry import get_model_client
        model_client = get_model_client(selected_answer_model, settings)
        llm = ModelClientLLMAdapter(model_client)
        owns_client = True

    def on_stage(stage: str) -> None:
        try:
            status_value = WebEvidenceStatus(stage)
        except ValueError:
            return
        stage_db = SessionLocal()
        try:
            update_web_evidence_status(stage_db, run_id, status_value)
            stage_db.commit()
        except Exception:
            stage_db.rollback()
            logger.exception("failed to update web evidence status run_id=%s stage=%s", run_id, stage)
        finally:
            stage_db.close()

    try:
        search = build_web_search_client(settings)
        if search is None:
            result = unavailable_result(
                "Web Evidence is unavailable. Configure TAVILY_API_KEY to enable external evidence checks."
            )
            db = SessionLocal()
            try:
                persist_web_evidence_result(db, run_id, result)
                db.commit()
            finally:
                db.close()
            logger.info("web evidence unavailable run_id=%s", run_id)
            return

        result = await run_web_evidence(
            llm,
            search,
            question=question,
            answer=answer_text,
            settings=settings,
            on_stage=on_stage,
        )
        db = SessionLocal()
        try:
            persist_web_evidence_result(db, run_id, result)
            db.commit()
        finally:
            db.close()
        logger.info(
            "web evidence finished run_id=%s status=%s claims=%s",
            run_id,
            result.status.value,
            result.total_claims,
        )
    except Exception as exc:
        logger.exception("background web evidence failed run_id=%s", run_id)
        fail_result = WebEvidenceResult(
            status=WebEvidenceStatus.FAILED,
            error=f"Web Evidence could not be completed: {str(exc)[:200]}",
        )
        fail_db = SessionLocal()
        try:
            persist_web_evidence_result(fail_db, run_id, fail_result)
            fail_db.commit()
        except Exception:
            fail_db.rollback()
            logger.exception("failed to persist web evidence failure run_id=%s", run_id)
        finally:
            fail_db.close()
    finally:
        if owns_client:
            close = getattr(llm, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    logger.exception("failed to close web evidence llm client")


async def _continue_independent_verdicts(
    *,
    run_id: str,
    question: str,
    answer_text: str,
    selected_answer_model: str = "gemma",
    request_llm: LLMClient | None = None,
) -> None:
    """Background evaluation of the generated answer by all other models in MODEL_REGISTRY.

    The selected answer model is NEVER included as a verifier.
    """
    settings = get_settings()
    try:
        from app.services.independent_verifiers import (
            evaluate_all_independent_verifiers,
            persist_independent_verdicts,
        )

        verdicts = await evaluate_all_independent_verifiers(
            question=question,
            answer=answer_text,
            selected_answer_model_id=selected_answer_model,
            settings=settings,
            test_llm=request_llm,
        )
        db = SessionLocal()
        try:
            persist_independent_verdicts(db, run_id, verdicts)
            db.commit()
            logger.info("independent ai verdicts saved run_id=%s count=%d", run_id, len(verdicts))
        except Exception:
            db.rollback()
            logger.exception("failed to persist independent verdicts run_id=%s", run_id)
        finally:
            db.close()
    except Exception:
        logger.exception("background independent verdicts evaluation crashed run_id=%s", run_id)


@router.get("/api/models")
def get_models(settings: Settings = Depends(settings_dep)) -> dict[str, Any]:
    """Return available answer models and their cloud provider readiness status."""
    from app.llm.registry import DEFAULT_MODEL_ID, list_available_models
    return {
        "models": list_available_models(settings),
        "default_model": DEFAULT_MODEL_ID,
    }


@router.post("/api/detect", response_model=DetectResponse)
async def detect(
    payload: DetectRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
    llm: LLMClient = Depends(get_llm_client),
    verifier_llm: LLMClient | None = Depends(get_gemini_verifier_client),
) -> DetectResponse:
    question = payload.cleaned_question
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a factual question.")

    from app.llm.registry import (
        MODEL_REGISTRY,
        get_model_client,
        is_model_configured,
        validate_answer_model,
    )

    try:
        canonical_model_id = validate_answer_model(payload.answer_model)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    model_def = MODEL_REGISTRY[canonical_model_id]

    if settings.llm_mode == "live":
        if not is_model_configured(canonical_model_id, settings) or not settings.api_key_configured:
            detail = (
                f"Selected answer model '{model_def.display_name}' ({model_def.provider_display}) is not configured. "
                f"Live LLM mode is not configured. Add the required provider credentials in the backend environment or switch to Demo / Mock Mode."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=detail,
            )

    try:
        answer_started = time.perf_counter()
        is_test_mock = isinstance(llm, MockLLMClient) or settings.llm_mode == "mock"
        if is_test_mock:
            # Deterministic test mock or mock mode
            base_ans = await generate_answer(
                llm,
                question,
                model_def.default_model_name,
                max_tokens=settings.llm_answer_max_tokens,
            )
            answer = BaseAnswer(text=base_ans.text, model=model_def.display_name)
        else:
            model_client = get_model_client(canonical_model_id, settings)
            text = await model_client.generate_answer(
                question,
                max_tokens=settings.llm_answer_max_tokens,
            )
            answer = BaseAnswer(text=text.strip(), model=model_def.display_name)

        answer_ms = round((time.perf_counter() - answer_started) * 1000, 1)

        ai_verdicts_json = ""

        try:
            run = create_answer_ready_run(
                db,
                question=question,
                base_answer=answer.text,
                generator_model=answer.model,
                threshold=settings.threshold,
                llm_mode=settings.llm_mode,
                answer_ms=answer_ms,
                ai_verdicts_json=ai_verdicts_json,
            )
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("database write failure after answer generation")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Answer was generated but could not be saved.",
            ) from exc

        # Schedule MetaQA, Web Evidence, and Independent AI Verification independently and concurrently.
        # Dynamic verifier pool automatically excludes the selected answer model.
        if is_test_mock and isinstance(llm, MockLLMClient):
            from app.llm.gemini import MockGeminiClient
            verifier_llm = MockGeminiClient(inner=llm)

        async def _run_parallel_verification() -> None:
            outcomes = await asyncio.gather(
                _continue_metaqa_analysis(
                    run_id=run.id,
                    question=question,
                    answer_text=answer.text,
                    generator_model=answer.model,
                    answer_ms=answer_ms,
                    selected_answer_model=canonical_model_id,
                    request_llm=llm if is_test_mock else None,
                    request_verifier_llm=verifier_llm if is_test_mock else None,
                ),
                _continue_web_evidence(
                    run_id=run.id,
                    question=question,
                    answer_text=answer.text,
                    selected_answer_model=canonical_model_id,
                    request_llm=llm if is_test_mock else None,
                ),
                return_exceptions=True,
            )
            labels = ("metaqa", "web_evidence")
            for label, outcome in zip(labels, outcomes, strict=True):
                if isinstance(outcome, Exception):
                    logger.exception(
                        "parallel verification branch crashed run_id=%s branch=%s",
                        run.id,
                        label,
                        exc_info=outcome,
                    )

            tot_elapsed = round((time.perf_counter() - answer_started) * 1000, 1)
            logger.info(
                "parallel verification completed run_id=%s total_analysis_ms=%.0f",
                run.id,
                tot_elapsed,
            )

        background_tasks.add_task(_run_parallel_verification)
        logger.info(
            "answer ready run_id=%s answer_ms=%.0f; metaqa+web_evidence scheduled in parallel (model=%s)",
            run.id,
            answer_ms,
            canonical_model_id,
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
