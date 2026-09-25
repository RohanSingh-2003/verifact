from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import settings_dep
from app.config import Settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    llm_mode: str
    llm_provider: str
    live_ready: bool
    generator_model: str
    verifier_model: str


@router.get("/api/health", response_model=HealthResponse)
def health(settings: Settings = Depends(settings_dep)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_mode=settings.llm_mode,
        llm_provider=settings.llm_provider,
        live_ready=settings.live_ready,
        generator_model=settings.generator_model,
        verifier_model=settings.verifier_model,
    )
