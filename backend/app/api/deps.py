from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.db import get_db
from app.llm.base import LLMClient
from app.llm.client import OpenAICompatibleClient
from app.llm.mock import MockLLMClient
from app.llm.ollama import OllamaClient


@lru_cache
def get_llm_client() -> LLMClient:
    settings = get_settings()
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


def settings_dep() -> Settings:
    return get_settings()


def db_dep(db: Session = Depends(get_db)) -> Session:
    return db
