from abc import ABC, abstractmethod
from typing import Any


class LLMError(RuntimeError):
    """Raised when an LLM provider call fails."""


class LLMRateLimitError(LLMError):
    """Raised when the provider returns HTTP 429."""


class LLMTimeoutError(LLMError):
    """Raised when the provider request times out."""


class LLMConnectionError(LLMError):
    """Raised when connecting to the LLM host fails (e.g. daemon not running)."""


class LLMModelNotFoundError(LLMError):
    """Raised when the requested model is not found/installed on the provider."""


class LLMEmptyResponseError(LLMError):
    """Raised when the provider returns an empty response."""


class LLMMalformedResponseError(LLMError):
    """Raised when the provider response cannot be parsed or is malformed."""


class LLMClient(ABC):
    """Provider-agnostic language model client used by MetaQA."""

    @abstractmethod
    async def complete_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Return a parsed JSON object from the model."""

    @abstractmethod
    async def complete_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> str:
        """Return plain text from the model."""
