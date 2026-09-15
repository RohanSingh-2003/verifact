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
    llm_timeout_seconds: float = Field(default=60.0, ge=5.0, le=180.0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_output_tokens: int = Field(default=800, ge=64, le=4096)
    llm_provider: str = "openai_compatible"

    max_questions: int = Field(default=40, ge=1, le=500)
    live_unconfirmed_max_questions: int = Field(default=1, ge=1, le=50)
    frozen_experiment_id: str = "58baff20-fb86-4f43-b20e-895a086ceb6b"

    @field_validator("frontend_origin")
    @classmethod
    def origin_must_not_be_wildcard(cls, value: str) -> str:
        if value.strip() == "*":
            raise ValueError("FRONTEND_ORIGIN cannot be a wildcard.")
        return value.rstrip("/")

    @property
    def allowed_model_set(self) -> set[str]:
        return {item.strip() for item in self.allowed_models.split(",") if item.strip()}

    @property
    def api_key_configured(self) -> bool:
        key = self.openai_api_key.strip()
        return bool(key) and not key.startswith("replace-with-")

    @property
    def live_ready(self) -> bool:
        return self.llm_mode == "live" and self.api_key_configured

    def require_model(self, model: str) -> str:
        if self.llm_mode == "mock":
            return model
        allowed = self.allowed_model_set
        if allowed and model not in allowed:
            raise ValueError(f"Model '{model}' is not in ALLOWED_MODELS.")
        return model

    def experiment_models(self) -> tuple[list[str], list[str]]:
        return (
            [self.generator_model_a, self.generator_model_b],
            [self.verifier_model_a, self.verifier_model_b],
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
