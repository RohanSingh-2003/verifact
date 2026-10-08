from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from app.config import Settings
from app.llm.providers import (
    GeminiClientAdapter,
    GroqClient,
    MistralClient,
    MockModelClient,
    ModelClient,
    NvidiaClient,
    OllamaCloudClient,
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
    "nemotron": AnswerModelDefinition(
        id="nemotron",
        display_name="NVIDIA Nemotron",
        provider="nvidia",
        provider_display="NVIDIA",
        default_model_name="nvidia/llama-3.1-nemotron-70b-instruct",
        env_key_name="NVIDIA_API_KEY",
    ),
    "qwen": AnswerModelDefinition(
        id="qwen",
        display_name="Qwen",
        provider="groq",
        provider_display="Alibaba / Groq",
        default_model_name="qwen-2.5-32b",
        env_key_name="GROQ_API_KEY",
    ),
    "mistral": AnswerModelDefinition(
        id="mistral",
        display_name="Mistral",
        provider="mistral",
        provider_display="Mistral AI",
        default_model_name="mistral-small-latest",
        env_key_name="MISTRAL_API_KEY",
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
    if "nemotron" in cleaned or "nvidia" in cleaned:
        return "nemotron"
    if "qwen" in cleaned or "groq" in cleaned:
        return "qwen"
    if "mistral" in cleaned:
        return "mistral"
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
    """Return whether the provider for this model has credentials configured."""
    if settings.llm_mode == "mock":
        return True

    mid = resolve_model_id(model_id)
    if mid == "gemma":
        key = getattr(settings, "ollama_api_key", "").strip()
        return bool(key) and not key.startswith("replace-with-") and key != "ollama"
    if mid == "nemotron":
        key = getattr(settings, "nvidia_api_key", "").strip()
        return bool(key) and not key.startswith("replace-with-")
    if mid == "qwen":
        key = getattr(settings, "groq_api_key", "").strip()
        return bool(key) and not key.startswith("replace-with-")
    if mid == "mistral":
        key = getattr(settings, "mistral_api_key", "").strip()
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

    if canonical_id == "nemotron":
        return NvidiaClient(
            base_url=getattr(settings, "nvidia_base_url", "https://integrate.api.nvidia.com/v1"),
            api_key=getattr(settings, "nvidia_api_key", ""),
            model_name=getattr(settings, "nvidia_model", mdef.default_model_name),
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

    if canonical_id == "mistral":
        return MistralClient(
            base_url=getattr(settings, "mistral_base_url", "https://api.mistral.ai/v1"),
            api_key=getattr(settings, "mistral_api_key", ""),
            model_name=getattr(settings, "mistral_model", mdef.default_model_name),
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
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
