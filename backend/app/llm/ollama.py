"""Ollama integration for VeriFact.

VeriFact uses a STRICT CLOUD-API-ONLY inference architecture.
Local Ollama inference (http://localhost:11434) is completely removed.
Ollama is accessed exclusively via Ollama Cloud API (https://ollama.com/api)
through OllamaCloudClient.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.llm.base import LLMClient, LLMError
from app.llm.providers import OllamaCloudClient

__all__ = [
    "OllamaClient",
    "OllamaCloudClient",
    "OllamaConcurrencyLimiter",
    "get_ollama_semaphore",
    "get_ollama_call_count",
    "reset_ollama_call_count",
]

_OLLAMA_CALL_COUNTER: int = 0
_SEMAPHORE: asyncio.Semaphore | None = None
_SEMAPHORE_LIMIT: int = 1


def get_ollama_call_count() -> int:
    return _OLLAMA_CALL_COUNTER


def reset_ollama_call_count() -> None:
    global _OLLAMA_CALL_COUNTER
    _OLLAMA_CALL_COUNTER = 0


def increment_ollama_call_count() -> int:
    global _OLLAMA_CALL_COUNTER
    _OLLAMA_CALL_COUNTER += 1
    return _OLLAMA_CALL_COUNTER


def get_ollama_semaphore(limit: int = 1) -> asyncio.Semaphore:
    global _SEMAPHORE, _SEMAPHORE_LIMIT
    safe_limit = max(1, limit)
    if _SEMAPHORE is None or _SEMAPHORE_LIMIT != safe_limit:
        _SEMAPHORE = asyncio.Semaphore(safe_limit)
        _SEMAPHORE_LIMIT = safe_limit
    return _SEMAPHORE


class OllamaConcurrencyLimiter:
    @staticmethod
    def get_semaphore(limit: int = 1) -> asyncio.Semaphore:
        return get_ollama_semaphore(limit)


class OllamaClient(OllamaCloudClient):
    """Ollama Cloud client for Gemma 4:26B.
    
    Local Ollama inference has been removed. All Ollama inference routes
    strictly through Ollama Cloud (https://ollama.com/api).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if args and hasattr(args[0], "ollama_api_key"):
            settings = args[0]
            super().__init__(
                base_url=getattr(settings, "ollama_cloud_base_url", "https://ollama.com/api"),
                api_key=getattr(settings, "ollama_api_key", ""),
                model_name=getattr(settings, "ollama_cloud_model", "gemma4:26b"),
                timeout_seconds=getattr(settings, "llm_timeout_seconds", 60.0),
                max_retries=getattr(settings, "llm_max_retries", 2),
            )
        else:
            super().__init__(*args, **kwargs)
