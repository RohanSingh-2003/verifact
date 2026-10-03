from pathlib import Path
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_detect import router as detect_router
from app.api.routes_evaluations import router as evaluation_router
from app.api.routes_experiments import router as experiment_router
from app.api.routes_health import router as health_router
from app.api.routes_runs import router as runs_router
from app.api.routes_settings import router as settings_router
from app.config import get_settings
from app.database.db import init_db

settings = get_settings()
logger = logging.getLogger("verifact")


def _configure_logging() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app() -> FastAPI:
    _configure_logging()
    Path("data").mkdir(exist_ok=True)
    init_db()
    logger.info(
        "starting VeriFact llm_provider=%s generator=%s verifier=%s gemini_verifier=%s tavily=%s",
        settings.llm_provider,
        settings.generator_model,
        settings.effective_verifier_model,
        settings.gemini_verifier_ready,
        settings.web_evidence_ready,
    )

    application = FastAPI(
        title="VeriFact",
        description=(
            "VeriFact implements the MetaQA metamorphic hallucination-detection methodology. "
            "The core detector does not use external retrieval or fact databases."
        ),
        version="0.1.0",
    )
    cors_origins = {
        settings.frontend_origin.rstrip("/"),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    }
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(settings_router)
    application.include_router(detect_router)
    application.include_router(runs_router)
    application.include_router(experiment_router)
    application.include_router(evaluation_router)
    return application


app = create_app()
