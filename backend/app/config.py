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

    # Local Ollama endpoint (used when llm_provider=ollama).
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"
    ollama_allowed_models: str = "gemma4:26b"

    generator_model: str = "gemma4:26b"
    mutation_model: str = ""
    verifier_model: str = "gemma4:26b"
    generator_model_a: str = "gemma4:26b"
    generator_model_b: str = "gemma4:26b"
    verifier_model_a: str = "gemma4:26b"
    verifier_model_b: str = "gemma4:26b"
    allowed_models: str = "gemma4:26b,gpt-4o-mini,gpt-4o"

    synonym_count: int = Field(default=5, ge=1, le=20)
    antonym_count: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    verify_concurrency: int = Field(default=5, ge=1, le=20)
    ollama_max_concurrency: int = Field(default=1, ge=1, le=10)
    llm_timeout_seconds: float = Field(default=60.0, ge=5.0, le=600.0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_output_tokens: int = Field(default=800, ge=64, le=4096)
    # Stage-specific caps (interactive Detect path). Experiment payload still chooses mutation counts.
    llm_answer_max_tokens: int = Field(default=350, ge=32, le=4096)
    llm_claim_max_tokens: int = Field(default=256, ge=64, le=1024)
    llm_mutation_max_tokens: int = Field(default=300, ge=64, le=4096)
    llm_verify_max_tokens: int = Field(default=256, ge=32, le=1024)
    llm_provider: Literal["openai_compatible", "ollama"] = "ollama"
    ollama_keep_alive: str = "30m"

    # Gemini Verifier — cross-model MetaQA mutation verification.
    # Gemini is used for verifying mutations or answer generation.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_verifier_model: str = "gemini-3.8-flash"
    gemini_verify_concurrency: int = Field(default=3, ge=1, le=10)

    # Multi-Model Cloud Providers (Phase 1)
    # 1. Ollama Cloud (Gemma 4:26B) - official cloud endpoint, NOT localhost
    ollama_cloud_base_url: str = "https://ollama.com/api"
    ollama_cloud_model: str = "gemma4:26b"

    # 2. NVIDIA NIM API (Nemotron)
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/llama-3.1-nemotron-70b-instruct"

    # 3. Groq API (Qwen)
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "qwen-2.5-32b"

    # 4. Mistral AI API (Mistral)
    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai/v1"
    mistral_model: str = "mistral-small-latest"

    # Web Evidence (Tavily) — independent of MetaQA; optional when key missing.
    tavily_api_key: str = ""
    tavily_base_url: str = "https://api.tavily.com"
    tavily_search_depth: Literal["basic", "advanced"] = "basic"
    tavily_timeout_seconds: float = Field(default=30.0, ge=5.0, le=120.0)
    web_evidence_enabled: bool = True
    web_max_claims: int = Field(default=6, ge=1, le=20)
    web_max_searches: int = Field(default=6, ge=1, le=20)
    web_results_per_claim: int = Field(default=3, ge=1, le=10)
    llm_web_claim_max_tokens: int = Field(default=400, ge=64, le=2048)
    llm_web_verify_max_tokens: int = Field(default=160, ge=32, le=1024)

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

    @property
    def tavily_configured(self) -> bool:
        if self.llm_mode == "mock":
            return True
        key = self.tavily_api_key.strip()
        return bool(key) and not key.startswith("replace-with-")

    @property
    def web_evidence_ready(self) -> bool:
        """True when Web Evidence can run (needs Tavily key)."""
        if not self.web_evidence_enabled:
            return False
        return self.tavily_configured

    @property
    def gemini_configured(self) -> bool:
        """True when a Gemini API key is present for cross-model verification."""
        key = self.gemini_api_key.strip()
        return bool(key) and not key.startswith("replace-with-")

    @property
    def gemini_verifier_ready(self) -> bool:
        """True when Gemini can serve as the MetaQA mutation verifier."""
        if self.llm_mode == "mock":
            return True
        return self.gemini_configured

    @property
    def ollama_cloud_configured(self) -> bool:
        if self.llm_mode == "mock":
            return True
        key = self.ollama_api_key.strip()
        return bool(key) and not key.startswith("replace-with-") and key != "ollama"

    @property
    def nvidia_configured(self) -> bool:
        if self.llm_mode == "mock":
            return True
        key = self.nvidia_api_key.strip()
        return bool(key) and not key.startswith("replace-with-")

    @property
    def groq_configured(self) -> bool:
        if self.llm_mode == "mock":
            return True
        key = self.groq_api_key.strip()
        return bool(key) and not key.startswith("replace-with-")

    @property
    def mistral_configured(self) -> bool:
        if self.llm_mode == "mock":
            return True
        key = self.mistral_api_key.strip()
        return bool(key) and not key.startswith("replace-with-")

    @property
    def effective_mutation_model(self) -> str:
        """The model used for MetaQA mutation generation.

        Returns mutation_model if explicitly configured, otherwise falls back
        to generator_model.
        """
        if self.mutation_model and self.mutation_model.strip():
            return self.mutation_model.strip()
        return self.generator_model

    @property
    def effective_verifier_model(self) -> str:
        """The model used for MetaQA mutation verification.

        Returns the Gemini model when configured or in mock mode, otherwise falls back
        to the standard verifier_model (Ollama/OpenAI).
        """
        if self.llm_mode == "mock":
            return self.gemini_verifier_model
        if self.gemini_configured:
            return self.gemini_verifier_model
        return self.verifier_model

    def require_model(self, model: str) -> str:
        if self.llm_mode == "mock":
            return model
        if model == self.gemini_verifier_model or model.startswith("gemini"):
            return model
        if self.mutation_model and model == self.mutation_model.strip():
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
