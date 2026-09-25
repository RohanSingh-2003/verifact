from abc import ABC, abstractmethod
from typing import Any


class LLMError(RuntimeError):
    """Raised when an LLM provider call fails."""


class LLMRateLimitError(LLMError):
    """Raised when the provider returns HTTP 429."""


class LLMTimeoutError(LLMError):
    """Raised when the provider request times out."""


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
