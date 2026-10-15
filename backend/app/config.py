from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(_ROOT_DIR / ".env"),
            str(_BACKEND_DIR / ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VeriFact"
    environment: Literal["development", "production", "test"] = "development"

    database_url: str = "sqlite:///./data/verifact.db"
    frontend_origin: str = "http://localhost:5173"

    llm_mode: Literal["mock", "live"] = "mock"
    mock_scenario: str = "reliable"

    # Multi-Model Cloud Providers
    # 1. Ollama Cloud (Gemma 4:26B) - official cloud endpoint ONLY, zero localhost inference
    ollama_api_key: str = ""
    ollama_cloud_base_url: str = "https://ollama.com/api"
    ollama_cloud_model: str = "gemma4:26b"

    # 2. Cloudflare Workers AI (GLM-4.7-Flash)
    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""
    cloudflare_base_url: str = "https://api.cloudflare.com/client/v4"
    cloudflare_model: str = "@cf/zai-org/glm-4.7-flash"

    # 3. Groq API (Qwen)
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "qwen-2.5-32b"

    # 4. OpenRouter API
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "liquid/lfm-2.5-2.6b:free"
    openrouter_max_retries: int = Field(default=3, ge=0, le=10)
    openrouter_max_retry_wait: float = Field(default=30.0, ge=1.0, le=120.0)
    openrouter_total_retry_timeout: float = Field(default=60.0, ge=5.0, le=300.0)
    openrouter_initial_retry_wait: float = Field(default=1.0, ge=0.1, le=10.0)
    openrouter_timeout_seconds: float = Field(default=60.0, ge=5.0, le=300.0)

    # 5. Google Gemini API (Gemini Flash 3.8)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_verifier_model: str = "gemini-3.8-flash"
    gemini_verify_concurrency: int = Field(default=3, ge=1, le=10)
    gemini_max_retries: int = Field(default=3, ge=0, le=10)
    gemini_initial_retry_delay: float = Field(default=1.0, ge=0.1, le=10.0)
    gemini_max_retry_delay: float = Field(default=10.0, ge=1.0, le=60.0)
    gemini_total_retry_timeout: float = Field(default=30.0, ge=5.0, le=120.0)
    gemini_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)

    # 5. Microsoft Phi-4 Reasoning (via OpenRouter)
    phi_model: str = "microsoft/phi-4-reasoning:free"

    # Provider & model parameters
    llm_provider: str = "cloud"
    generator_model: str = "gemma4:26b"
    verifier_model: str = "microsoft/phi-4-reasoning:free"
    mutation_model: str = ""

    synonym_count: int = Field(default=5, ge=1, le=20)
    antonym_count: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    verify_concurrency: int = Field(default=5, ge=1, le=20)
    llm_timeout_seconds: float = Field(default=60.0, ge=5.0, le=600.0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_output_tokens: int = Field(default=800, ge=64, le=4096)
    llm_answer_max_tokens: int = Field(default=350, ge=32, le=4096)
    llm_claim_max_tokens: int = Field(default=256, ge=64, le=1024)
    llm_mutation_max_tokens: int = Field(default=300, ge=64, le=4096)
    llm_verify_max_tokens: int = Field(default=256, ge=32, le=1024)

    # Web Evidence (Tavily) — independent of MetaQA; optional when key missing.
    tavily_api_key: str = ""
    tavily_base_url: str = "https://api.tavily.com"
    tavily_search_depth: Literal["basic", "advanced"] = "basic"
    tavily_timeout_seconds: float = Field(default=30.0, ge=5.0, le=120.0)
    web_evidence_enabled: bool = True
    web_max_claims: int = Field(default=6, ge=1, le=20)
    web_max_searches: int = Field(default=8, ge=1, le=30)
    web_results_per_claim: int = Field(default=4, ge=1, le=10)
    llm_web_claim_max_tokens: int = Field(default=400, ge=64, le=2048)
    llm_web_verify_max_tokens: int = Field(default=300, ge=32, le=2048)

    max_questions: int = Field(default=40, ge=1, le=500)
    live_unconfirmed_max_questions: int = Field(default=1, ge=1, le=50)
    frozen_experiment_id: str = "58baff20-fb86-4f43-b20e-895a086ceb6b"

    # Server Binding
    server_host: str = "127.0.0.1"
    server_port: int = Field(default=8000, ge=1, le=65535)

    # API Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_detect_per_minute: int = Field(default=10, ge=1, le=1000)
    rate_limit_batch_per_minute: int = Field(default=5, ge=1, le=1000)
    rate_limit_default_per_minute: int = Field(default=120, ge=1, le=10000)
    trusted_proxies: list[str] = Field(default_factory=list)

    @field_validator("trusted_proxies", mode="before")
    @classmethod
    def parse_trusted_proxies(cls, value: object) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("[") and stripped.endswith("]"):
                import json

                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [
                            str(item).strip()
                            for item in parsed
                            if str(item).strip()
                        ]
                except json.JSONDecodeError:
                    pass
            return [part.strip() for part in stripped.split(",") if part.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @field_validator("frontend_origin")
    @classmethod
    def origin_must_not_be_wildcard(cls, value: str) -> str:
        if value.strip() == "*":
            raise ValueError("FRONTEND_ORIGIN cannot be a wildcard.")
        return value.rstrip("/")

    @property
    def is_ollama(self) -> bool:
        return False

    @property
    def allowed_model_set(self) -> set[str]:
        from app.llm.registry import MODEL_REGISTRY
        allowed = set()
        for mid, mdef in MODEL_REGISTRY.items():
            allowed.add(mid.lower())
            allowed.add(mdef.default_model_name.lower())
            allowed.add(mdef.display_name.lower())
        return allowed

    @property
    def api_key_configured(self) -> bool:
        if self.llm_mode == "mock":
            return True
        return (
            self.ollama_cloud_configured
            or self.cloudflare_configured
            or self.groq_configured
            or self.openrouter_configured
            or self.gemini_configured
        )

    @property
    def effective_api_key(self) -> str:
        return self.ollama_api_key.strip()

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
    def cloudflare_configured(self) -> bool:
        if self.llm_mode == "mock":
            return True
        token = self.cloudflare_api_token.strip()
        account_id = self.cloudflare_account_id.strip()
        return (
            bool(token)
            and not token.startswith("replace-with-")
            and bool(account_id)
            and not account_id.startswith("replace-with-")
        )

    @property
    def groq_configured(self) -> bool:
        if self.llm_mode == "mock":
            return True
        key = self.groq_api_key.strip()
        return bool(key) and not key.startswith("replace-with-")

    @property
    def openrouter_configured(self) -> bool:
        if self.llm_mode == "mock":
            return True
        key = self.openrouter_api_key.strip()
        return bool(key) and not key.startswith("replace-with-")

    @property
    def phi_configured(self) -> bool:
        if self.llm_mode == "mock":
            return True
        key = self.openrouter_api_key.strip()
        return bool(key) and not key.startswith("replace-with-")

    @property
    def phi_verifier_ready(self) -> bool:
        return self.phi_configured

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
        """The model used for MetaQA mutation verification."""
        if self.gemini_configured and self.gemini_verifier_model and "gemini" in self.gemini_verifier_model:
            return self.gemini_verifier_model
        if self.llm_mode == "mock" and self.gemini_verifier_model and self.gemini_verifier_model != "gemini-3.8-flash":
            return self.gemini_verifier_model
        if self.verifier_model and self.verifier_model not in {"gemini-3.8-flash", "microsoft/phi-4-reasoning:free"}:
            return self.verifier_model
        return self.phi_model or self.verifier_model or "microsoft/phi-4-reasoning:free"

    def require_model(self, model: str) -> str:
        if self.llm_mode == "mock":
            return model
        cleaned = model.strip().lower()
        allowed = self.allowed_model_set
        if cleaned not in allowed and not any(cleaned in a for a in allowed):
            from app.llm.registry import MODEL_REGISTRY
            valid = ", ".join(m.display_name for m in MODEL_REGISTRY.values())
            raise ValueError(f"Model '{model}' is not a supported cloud model. Supported models are: {valid}")
        return model

    def experiment_models(self) -> tuple[list[str], list[str]]:
        from app.llm.registry import MODEL_REGISTRY
        keys = list(MODEL_REGISTRY.keys())
        return (keys[:2], keys[2:4])


@lru_cache
def get_settings() -> Settings:
    return Settings()
