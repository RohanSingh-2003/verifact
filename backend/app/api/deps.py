from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.db import get_db
from app.llm.base import LLMClient
from app.llm.client import OpenAICompatibleClient
from app.llm.ollama import OllamaClient


@lru_cache
def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_mode == "mock":
        from app.llm.mock import MockLLMClient
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


@lru_cache
def get_gemini_verifier_client() -> LLMClient | None:
    """Create the Gemini verifier client for cross-model MetaQA verification.

    Returns None if Gemini is not configured (no API key).
    """
    settings = get_settings()
    if settings.llm_mode == "mock":
        from app.llm.gemini import MockGeminiClient
        return MockGeminiClient(scenario=settings.mock_scenario)
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


def settings_dep() -> Settings:
    return get_settings()


def db_dep(db: Session = Depends(get_db)) -> Session:
    return db
