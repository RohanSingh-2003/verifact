from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import settings_dep
from app.config import Settings

router = APIRouter(tags=["health"])


class ProviderStatus(BaseModel):
    name: str
    ready: bool


class HealthResponse(BaseModel):
    status: str
    llm_mode: str = "live"
    llm_provider: str
    live_ready: bool
    generator_model: str
    verifier_model: str
    web_evidence_ready: bool = False
    web_evidence_enabled: bool = True
    # Gemini cross-model verifier status
    gemini_verifier_enabled: bool = False
    gemini_verifier_ready: bool = False
    gemini_verifier_model: str = ""
    database_connected: bool = True
    providers: dict[str, ProviderStatus] = {}


@router.get("/api/health", response_model=HealthResponse)
def health(settings: Settings = Depends(settings_dep)) -> HealthResponse:
    db_connected = True
    try:
        from sqlalchemy import text
        from sqlalchemy.exc import SQLAlchemyError
        from app.database.db import SessionLocal
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        db_connected = False

    from app.llm.registry import is_model_configured

    provider_statuses = {
        "ollama": ProviderStatus(name="Ollama Cloud", ready=is_model_configured("gemma", settings)),
        "cloudflare": ProviderStatus(name="Cloudflare Workers AI", ready=is_model_configured("glm", settings)),
        "groq": ProviderStatus(name="Alibaba / Groq", ready=is_model_configured("qwen", settings)),
        "openrouter": ProviderStatus(name="OpenRouter", ready=is_model_configured("openrouter", settings)),
        "gemini": ProviderStatus(name="Google Gemini", ready=is_model_configured("gemini", settings)),
    }

    return HealthResponse(
        status="ok",
        llm_mode=settings.llm_mode,
        llm_provider=settings.llm_provider,
        live_ready=settings.live_ready,
        generator_model=settings.generator_model,
        verifier_model=settings.effective_verifier_model,
        web_evidence_ready=settings.web_evidence_ready,
        web_evidence_enabled=settings.web_evidence_enabled,
        gemini_verifier_enabled=settings.gemini_configured,
        gemini_verifier_ready=settings.gemini_verifier_ready,
        gemini_verifier_model=settings.gemini_verifier_model,
        database_connected=db_connected,
        providers=provider_statuses,
    )
