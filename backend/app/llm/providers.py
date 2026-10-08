from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
import json
import logging
import re
from typing import Any

import httpx

from app.config import Settings
from app.llm.base import (
    LLMClient,
    LLMConnectionError,
    LLMEmptyResponseError,
    LLMError,
    LLMMalformedResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.client import parse_json_object, strip_markdown_fences
from app.llm.prompts import ANSWER_SYSTEM, ANSWER_USER

logger = logging.getLogger("verifact.llm.providers")


class ModelClient(ABC):
    """Abstract interface for all multi-model cloud providers in VeriFact."""

    @abstractmethod
    async def generate_answer(
        self,
        question: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Generate a direct answer to the user's factual question."""

    @abstractmethod
    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Return plain text from the model."""

    @abstractmethod
    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Return parsed JSON object from the model."""

    async def aclose(self) -> None:
        """Release underlying HTTP client resources."""


class BaseOpenAICompatibleProviderClient(ModelClient):
    """Shared HTTP client for OpenAI-compatible cloud endpoints (NVIDIA, Groq, Mistral)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_name: str,
        provider_name: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self.model_name = model_name
        self.provider_name = provider_name
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def generate_answer(
        self,
        question: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        return await self.complete_text(
            system_prompt=ANSWER_SYSTEM,
            user_prompt=ANSWER_USER.format(question=question),
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        return await self._chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=False,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        content = await self._chat(
            system_prompt=system_prompt,
            user_prompt=f"{user_prompt}\n\nReturn a valid JSON object only. No commentary or markdown formatting outside JSON.",
            json_mode=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        parsed = parse_json_object(content)
        if parsed is None:
            logger.warning("Failed to parse JSON from %s (%s): %s", self.provider_name, self.model_name, content[:500])
            raise LLMMalformedResponseError(f"{self.provider_name} returned malformed JSON.")
        return parsed

    async def _chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        max_tokens: int | None,
        temperature: float,
    ) -> str:
        if not self._api_key or self._api_key.startswith("replace-with-"):
            raise LLMError(f"{self.provider_name} API key is not configured.")

        payload: dict[str, Any] = {
            "model": self.model_name,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.post(
                    "/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if response.status_code == 429:
                    last_error = LLMRateLimitError(f"{self.provider_name} rate-limited the request (HTTP 429).")
                    logger.warning("%s rate limit (attempt %s/%s)", self.provider_name, attempt + 1, self.max_retries + 1)
                    if attempt >= self.max_retries:
                        raise last_error
                    await asyncio.sleep(min(2**attempt, 15))
                    continue
                if response.status_code >= 500:
                    last_error = LLMError(f"{self.provider_name} returned HTTP {response.status_code}.")
                    logger.error("%s server error HTTP %s", self.provider_name, response.status_code)
                    if attempt >= self.max_retries:
                        raise last_error
                    await asyncio.sleep(min(2**attempt, 15))
                    continue
                if response.status_code >= 400:
                    logger.error("%s HTTP %s: %s", self.provider_name, response.status_code, response.text[:400])
                    raise LLMError(f"{self.provider_name} returned HTTP {response.status_code}.")

                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    raise LLMEmptyResponseError(f"{self.provider_name} returned no completion choices.")
                content = choices[0].get("message", {}).get("content")
                if not isinstance(content, str) or not content.strip():
                    raise LLMEmptyResponseError(f"{self.provider_name} returned an empty completion.")
                return content.strip()
            except httpx.TimeoutException as exc:
                last_error = LLMTimeoutError(f"{self.provider_name} request timed out.")
                if attempt >= self.max_retries:
                    raise last_error from exc
                await asyncio.sleep(min(2**attempt, 15))
            except LLMRateLimitError:
                raise
            except LLMError as exc:
                if "HTTP 4" in str(exc) and "HTTP 429" not in str(exc):
                    raise
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(min(2**attempt, 15))
            except httpx.ConnectError as exc:
                last_error = LLMConnectionError(f"Could not connect to {self.provider_name} at {self.base_url}.")
                if attempt >= self.max_retries:
                    raise last_error from exc
                await asyncio.sleep(min(2**attempt, 15))
            except Exception as exc:
                last_error = LLMError(f"{self.provider_name} request failed: {exc}")
                if attempt >= self.max_retries:
                    raise last_error from exc
                await asyncio.sleep(min(2**attempt, 15))

        raise last_error or LLMError(f"{self.provider_name} request failed.")


class OllamaCloudClient(ModelClient):
    """Client for Ollama Cloud API.

    CRITICAL: Never connects to localhost:11434. Uses official Ollama Cloud API.
    """

    def __init__(
        self,
        *,
        base_url: str = "https://ollama.com/api",
        api_key: str,
        model_name: str = "gemma4:26b",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        clean_url = base_url.strip().rstrip("/")
        if "localhost" in clean_url or "127.0.0.1" in clean_url:
            raise ValueError("OllamaCloudClient must NOT connect to localhost. Use official Ollama Cloud API.")
        self.base_url = clean_url
        self._api_key = api_key.strip()
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def generate_answer(
        self,
        question: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        return await self.complete_text(
            system_prompt=ANSWER_SYSTEM,
            user_prompt=ANSWER_USER.format(question=question),
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        return await self._chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=False,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        content = await self._chat(
            system_prompt=system_prompt,
            user_prompt=f"{user_prompt}\n\nReturn one JSON object only. No markdown fences. No commentary outside JSON.",
            json_mode=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        parsed = parse_json_object(content)
        if parsed is None:
            logger.warning("Failed to parse JSON from Ollama Cloud (%s): %s", self.model_name, content[:500])
            raise LLMMalformedResponseError("Ollama Cloud returned malformed JSON.")
        return parsed

    async def _chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        max_tokens: int | None,
        temperature: float,
    ) -> str:
        if not self._api_key or self._api_key.startswith("replace-with-"):
            raise LLMError("OLLAMA_API_KEY is not configured for Ollama Cloud.")

        payload: dict[str, Any] = {
            "model": self.model_name,
            "stream": False,
            "think": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature,
            },
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        if json_mode:
            payload["format"] = "json"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        # Ollama cloud native endpoint is /chat or /api/chat
        endpoint = "/chat" if self.base_url.endswith("/api") else "/api/chat"

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.post(endpoint, headers=headers, json=payload)
                if response.status_code == 429:
                    last_error = LLMRateLimitError("Ollama Cloud rate-limited the request (HTTP 429).")
                    if attempt >= self.max_retries:
                        raise last_error
                    await asyncio.sleep(min(2**attempt, 15))
                    continue
                if response.status_code >= 500:
                    last_error = LLMError(f"Ollama Cloud returned HTTP {response.status_code}.")
                    if attempt >= self.max_retries:
                        raise last_error
                    await asyncio.sleep(min(2**attempt, 15))
                    continue
                if response.status_code >= 400:
                    logger.error("Ollama Cloud HTTP %s: %s", response.status_code, response.text[:400])
                    raise LLMError(f"Ollama Cloud returned HTTP {response.status_code}.")

                data = response.json()
                message = data.get("message") or {}
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise LLMEmptyResponseError("Ollama Cloud returned an empty completion.")
                return content.strip()
            except httpx.TimeoutException as exc:
                last_error = LLMTimeoutError("Ollama Cloud request timed out.")
                if attempt >= self.max_retries:
                    raise last_error from exc
                await asyncio.sleep(min(2**attempt, 15))
            except LLMRateLimitError:
                raise
            except LLMError as exc:
                if "HTTP 4" in str(exc) and "HTTP 429" not in str(exc):
                    raise
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(min(2**attempt, 15))
            except httpx.ConnectError as exc:
                last_error = LLMConnectionError(f"Could not connect to Ollama Cloud at {self.base_url}.")
                if attempt >= self.max_retries:
                    raise last_error from exc
                await asyncio.sleep(min(2**attempt, 15))
            except Exception as exc:
                last_error = LLMError(f"Ollama Cloud call failed: {exc}")
                if attempt >= self.max_retries:
                    raise last_error from exc
                await asyncio.sleep(min(2**attempt, 15))

        raise last_error or LLMError("Ollama Cloud call failed.")


class NvidiaClient(BaseOpenAICompatibleProviderClient):
    """NVIDIA NIM API client for Nemotron."""

    def __init__(
        self,
        *,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        api_key: str,
        model_name: str = "nvidia/llama-3.1-nemotron-70b-instruct",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            provider_name="NVIDIA",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )


class GroqClient(BaseOpenAICompatibleProviderClient):
    """Groq API client for Qwen."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.groq.com/openai/v1",
        api_key: str,
        model_name: str = "qwen-2.5-32b",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            provider_name="Groq",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )


class MistralClient(BaseOpenAICompatibleProviderClient):
    """Mistral AI API client."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.mistral.ai/v1",
        api_key: str,
        model_name: str = "mistral-small-latest",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            provider_name="Mistral",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )


class GeminiClientAdapter(ModelClient):
    """Google Gemini API client adapter for both answer generation and verification."""

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = "gemini-3.8-flash",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        from app.llm.gemini import GeminiClient

        self._inner = GeminiClient(
            api_key=api_key,
            default_model=model_name,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.model_name = model_name

    async def generate_answer(
        self,
        question: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        return await self.complete_text(
            system_prompt=ANSWER_SYSTEM,
            user_prompt=ANSWER_USER.format(question=question),
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        return await self._inner.complete_text(
            model=self.model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        return await self._inner.complete_json(
            model=self.model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )


class MockModelClient(ModelClient):
    """Deterministic mock client for testing and demo mode."""

    def __init__(
        self,
        model_id: str,
        *,
        display_name: str,
        provider_display: str,
        scenario: str = "reliable",
    ) -> None:
        self.model_id = model_id
        self.display_name = display_name
        self.provider_display = provider_display
        self.scenario = scenario

    async def generate_answer(
        self,
        question: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        q_lower = question.lower()
        if "canberra" in q_lower or "australia" in q_lower:
            return "Canberra is the capital city of Australia."
        if "france" in q_lower or "paris" in q_lower:
            return "Paris is the capital of France."
        if "india" in q_lower or "delhi" in q_lower:
            return "New Delhi is the capital of India."
        return f"This is a factual answer generated by {self.display_name} via {self.provider_display} regarding: {question.strip()}"

    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        return f"Mock answer from {self.display_name}."

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        return {
            "verdict": "YES",
            "rationale": f"Verified by {self.display_name}.",
        }
