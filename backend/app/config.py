from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VeriFact"
    environment: Literal["development", "production", "test"] = "development"

    database_url: str = "sqlite:///./data/verifact.db"

    frontend_origin: str = "http://localhost:5173"

    llm_mode: Literal["mock", "live"] = "mock"
    mock_scenario: str = "reliable"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # Local Ollama OpenAI-compatible endpoint (used when llm_provider=ollama).
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"
    ollama_allowed_models: str = "gemma4:26b"

    generator_model: str = "gpt-4o-mini"
    verifier_model: str = "gpt-4o-mini"
    generator_model_a: str = "gpt-4o-mini"
    generator_model_b: str = "gpt-4o"
    verifier_model_a: str = "gpt-4o-mini"
    verifier_model_b: str = "gpt-4o"
    allowed_models: str = "gpt-4o-mini,gpt-4o,gpt-4.1-mini,gpt-4.1"

    synonym_count: int = Field(default=5, ge=1, le=20)
    antonym_count: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    verify_concurrency: int = Field(default=5, ge=1, le=20)
    llm_timeout_seconds: float = Field(default=60.0, ge=5.0, le=600.0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_output_tokens: int = Field(default=800, ge=64, le=4096)
    # Stage-specific caps (interactive Detect path). Experiment payload still chooses mutation counts.
    llm_answer_max_tokens: int = Field(default=350, ge=32, le=4096)
    llm_claim_max_tokens: int = Field(default=256, ge=64, le=1024)
    llm_mutation_max_tokens: int = Field(default=700, ge=64, le=4096)
    llm_verify_max_tokens: int = Field(default=96, ge=32, le=1024)
    llm_provider: Literal["openai_compatible", "ollama"] = "openai_compatible"
    ollama_keep_alive: str = "30m"

    max_questions: int = Field(default=40, ge=1, le=500)
    live_unconfirmed_max_questions: int = Field(default=1, ge=1, le=50)
    frozen_experiment_id: str = "58baff20-fb86-4f43-b20e-895a086ceb6b"

    @field_validator("frontend_origin")
    @classmethod
    def origin_must_not_be_wildcard(cls, value: str) -> str:
        if value.strip() == "*":
            raise ValueError("FRONTEND_ORIGIN cannot be a wildcard.")
        return value.rstrip("/")

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @property
    def is_ollama(self) -> bool:
        return self.llm_provider == "ollama"

    @property
    def chat_base_url(self) -> str:
        if self.is_ollama:
            return self.ollama_base_url.rstrip("/")
        return self.openai_base_url.rstrip("/")

    @property
    def allowed_model_set(self) -> set[str]:
        # Provider-specific allowlists: do not mix OpenAI and Ollama model IDs.
        raw = self.ollama_allowed_models if self.is_ollama else self.allowed_models
        return {item.strip() for item in raw.split(",") if item.strip()}

    @property
    def api_key_configured(self) -> bool:
        if self.is_ollama:
            # Ollama's OpenAI-compatible API accepts a placeholder bearer token.
            return True
        key = self.openai_api_key.strip()
        return bool(key) and not key.startswith("replace-with-")

    @property
    def effective_api_key(self) -> str:
        if self.is_ollama:
            key = self.ollama_api_key.strip() or self.openai_api_key.strip()
            return key if key and not key.startswith("replace-with-") else "ollama"
        return self.openai_api_key.strip()

    @property
    def live_ready(self) -> bool:
        return self.llm_mode == "live" and self.api_key_configured

    def require_model(self, model: str) -> str:
        if self.llm_mode == "mock":
            return model
        allowed = self.allowed_model_set
        if allowed and model not in allowed:
            label = "OLLAMA_ALLOWED_MODELS" if self.is_ollama else "ALLOWED_MODELS"
            raise ValueError(f"Model '{model}' is not in {label}.")
        return model

    def experiment_models(self) -> tuple[list[str], list[str]]:
        return (
            [self.generator_model_a, self.generator_model_b],
            [self.verifier_model_a, self.verifier_model_b],
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
