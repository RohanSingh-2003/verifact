from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import settings_dep
from app.config import Settings


router = APIRouter(tags=["settings"])


class PublicSettings(BaseModel):
    llm_mode: str
    live_ready: bool
    api_key_configured: bool
    llm_provider: str
    generator_model: str
    verifier_model: str
    generator_model_a: str
    generator_model_b: str
    verifier_model_a: str
    verifier_model_b: str
    allowed_models: list[str]
    synonym_count: int
    antonym_count: int
    threshold: float
    max_questions: int
    live_unconfirmed_max_questions: int
    llm_temperature: float
    llm_max_output_tokens: int
    frozen_experiment_id: str
    prompt_bundle: str = Field(default="metaqa-v1")


@router.get("/api/settings", response_model=PublicSettings)
def read_settings(settings: Settings = Depends(settings_dep)) -> PublicSettings:
    return PublicSettings(
        llm_mode=settings.llm_mode,
        live_ready=settings.live_ready,
        api_key_configured=settings.api_key_configured,
        llm_provider=settings.llm_provider,
        generator_model=settings.generator_model,
        verifier_model=settings.verifier_model,
        generator_model_a=settings.generator_model_a,
        generator_model_b=settings.generator_model_b,
        verifier_model_a=settings.verifier_model_a,
        verifier_model_b=settings.verifier_model_b,
        allowed_models=sorted(settings.allowed_model_set),
        synonym_count=settings.synonym_count,
        antonym_count=settings.antonym_count,
        threshold=settings.threshold,
        max_questions=settings.max_questions,
        live_unconfirmed_max_questions=settings.live_unconfirmed_max_questions,
        llm_temperature=settings.llm_temperature,
        llm_max_output_tokens=settings.llm_max_output_tokens,
        frozen_experiment_id=settings.frozen_experiment_id,
    )
