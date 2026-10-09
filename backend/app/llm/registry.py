from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from app.config import Settings
from app.llm.cloudflare import CloudflareClient
from app.llm.providers import (
    GeminiClientAdapter,
    GroqClient,
    MockModelClient,
    ModelClient,
    ModelClientLLMAdapter,
    OllamaCloudClient,
    OpenRouterClient,
)

logger = logging.getLogger("verifact.llm.registry")


@dataclass(frozen=True)
class AnswerModelDefinition:
    id: str
    display_name: str
    provider: str
    provider_display: str
    default_model_name: str
    env_key_name: str
    capabilities: tuple[str, ...] = ("generate", "verify")


MODEL_REGISTRY: dict[str, AnswerModelDefinition] = {
    "gemma": AnswerModelDefinition(
        id="gemma",
        display_name="Gemma 4:26B",
        provider="ollama",
        provider_display="Ollama Cloud",
        default_model_name="gemma4:26b",
        env_key_name="OLLAMA_API_KEY",
    ),
    "glm": AnswerModelDefinition(
        id="glm",
        display_name="GLM-4.7-Flash",
        provider="cloudflare",
        provider_display="Cloudflare Workers AI",
        default_model_name="@cf/zai-org/glm-4.7-flash",
        env_key_name="CLOUDFLARE_API_TOKEN",
    ),
    "qwen": AnswerModelDefinition(
        id="qwen",
        display_name="Qwen",
        provider="groq",
        provider_display="Alibaba / Groq",
        default_model_name="qwen-2.5-32b",
        env_key_name="GROQ_API_KEY",
    ),
    "openrouter": AnswerModelDefinition(
        id="openrouter",
        display_name="OpenRouter",
        provider="openrouter",
        provider_display="OpenRouter",
        default_model_name="liquid/lfm-2.5-2.6b:free",
        env_key_name="OPENROUTER_API_KEY",
    ),
    "gemini": AnswerModelDefinition(
        id="gemini",
        display_name="Gemini Flash 3.8",
        provider="gemini",
        provider_display="Google",
        default_model_name="gemini-3.8-flash",
        env_key_name="GEMINI_API_KEY",
    ),
}

DEFAULT_MODEL_ID = "gemma"


def resolve_model_id(identifier: str) -> str:
    """Map any model string, display name, or model ID to the canonical model registry key."""
    cleaned = (identifier or "").strip().lower()
    if not cleaned:
        return DEFAULT_MODEL_ID
    if cleaned in MODEL_REGISTRY:
        return cleaned

    for mid, mdef in MODEL_REGISTRY.items():
        if cleaned in {
            mdef.display_name.lower(),
            mdef.default_model_name.lower(),
            mdef.provider.lower(),
            mdef.provider_display.lower(),
        }:
            return mid

    # Partial matches
    if "gemma" in cleaned:
        return "gemma"
    if "glm" in cleaned or "zhipu" in cleaned or "cloudflare" in cleaned:
        return "glm"
    if "qwen" in cleaned or "groq" in cleaned:
        return "qwen"
    if "openrouter" in cleaned or "liquid" in cleaned:
        return "openrouter"
    if "gemini" in cleaned:
        return "gemini"

    return ""


def validate_answer_model(raw_model: str | None) -> str:
    """Validate and normalize requested answer model id. Defaults to 'gemma' when None or empty."""
    if raw_model is None or not raw_model.strip():
        return DEFAULT_MODEL_ID
    cleaned = raw_model.strip().lower()
    if cleaned in MODEL_REGISTRY:
        return cleaned
    resolved = resolve_model_id(cleaned)
    if resolved and resolved in MODEL_REGISTRY:
        return resolved
    allowed = ", ".join(MODEL_REGISTRY.keys())
    raise ValueError(f"Unknown answer_model '{raw_model}'. Allowed models are: {allowed}")


def is_model_configured(model_id: str, settings: Settings) -> bool:
    """Return whether the cloud provider for this model has credentials configured."""
    if settings.llm_mode == "mock":
        return True

    mid = resolve_model_id(model_id)
    if mid == "gemma":
        key = getattr(settings, "ollama_api_key", "").strip()
        return bool(key) and not key.startswith("replace-with-") and key != "ollama"
    if mid == "glm":
        token = getattr(settings, "cloudflare_api_token", "").strip()
        account_id = getattr(settings, "cloudflare_account_id", "").strip()
        return (
            bool(token)
            and not token.startswith("replace-with-")
            and bool(account_id)
            and not account_id.startswith("replace-with-")
        )
    if mid == "qwen":
        key = getattr(settings, "groq_api_key", "").strip()
        return bool(key) and not key.startswith("replace-with-")
    if mid == "openrouter":
        key = getattr(settings, "openrouter_api_key", "").strip()
        return bool(key) and not key.startswith("replace-with-")
    if mid == "gemini":
        key = getattr(settings, "gemini_api_key", "").strip()
        return bool(key) and not key.startswith("replace-with-")
    return False


def get_model_client(model_id: str, settings: Settings) -> ModelClient:
    """Instantiate the appropriate ModelClient for the given model ID."""
    canonical_id = validate_answer_model(model_id)
    mdef = MODEL_REGISTRY[canonical_id]

    if settings.llm_mode == "mock":
        return MockModelClient(
            model_id=canonical_id,
            display_name=mdef.display_name,
            provider_display=mdef.provider_display,
            scenario=settings.mock_scenario,
        )

    if canonical_id == "gemma":
        return OllamaCloudClient(
            base_url=getattr(settings, "ollama_cloud_base_url", "https://ollama.com/api"),
            api_key=getattr(settings, "ollama_api_key", ""),
            model_name=getattr(settings, "ollama_cloud_model", mdef.default_model_name),
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    if canonical_id == "glm":
        return CloudflareClient(
            base_url=getattr(settings, "cloudflare_base_url", "https://api.cloudflare.com/client/v4"),
            api_token=getattr(settings, "cloudflare_api_token", ""),
            account_id=getattr(settings, "cloudflare_account_id", ""),
            model_name=getattr(settings, "cloudflare_model", mdef.default_model_name),
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    if canonical_id == "qwen":
        return GroqClient(
            base_url=getattr(settings, "groq_base_url", "https://api.groq.com/openai/v1"),
            api_key=getattr(settings, "groq_api_key", ""),
            model_name=getattr(settings, "groq_model", mdef.default_model_name),
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    if canonical_id == "openrouter":
        return OpenRouterClient(
            base_url=getattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1"),
            api_key=getattr(settings, "openrouter_api_key", ""),
            model_name=(getattr(settings, "openrouter_model", "") or "").strip() or mdef.default_model_name,
            timeout_seconds=getattr(settings, "openrouter_timeout_seconds", settings.llm_timeout_seconds),
            max_retries=getattr(settings, "openrouter_max_retries", settings.llm_max_retries),
            initial_retry_wait=getattr(settings, "openrouter_initial_retry_wait", 1.0),
            max_retry_wait=getattr(settings, "openrouter_max_retry_wait", 30.0),
            total_retry_timeout=getattr(settings, "openrouter_total_retry_timeout", 60.0),
        )

    if canonical_id == "gemini":
        return GeminiClientAdapter(
            api_key=getattr(settings, "gemini_api_key", ""),
            model_name=getattr(settings, "gemini_model", mdef.default_model_name),
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    raise ValueError(f"No client implementation for model '{canonical_id}'.")


def get_verifier_pool(selected_answer_model_id: str, settings: Settings) -> list[dict[str, Any]]:
    """Dynamically construct the verifier pool by excluding the selected answer model.

    The selected answer model is NEVER included as its own verifier.
    """
    canonical_selected = validate_answer_model(selected_answer_model_id)
    verifiers: list[dict[str, Any]] = []

    for mid, mdef in MODEL_REGISTRY.items():
        if mid == canonical_selected:
            continue
        configured = is_model_configured(mid, settings)
        verifiers.append(
            {
                "id": mid,
                "name": mdef.display_name,
                "provider": mdef.provider_display,
                "status": "ready" if configured else "unconfigured",
            }
        )
    return verifiers


def list_available_models(settings: Settings) -> list[dict[str, Any]]:
    """List all available models with configuration status for UI selection."""
    models: list[dict[str, Any]] = []
    for mid, mdef in MODEL_REGISTRY.items():
        configured = is_model_configured(mid, settings)
        models.append(
            {
                "id": mid,
                "name": mdef.display_name,
                "provider": mdef.provider,
                "provider_display": mdef.provider_display,
                "model_name": mdef.default_model_name,
                "configured": configured,
                "is_default": mid == DEFAULT_MODEL_ID,
            }
        )
    return models
