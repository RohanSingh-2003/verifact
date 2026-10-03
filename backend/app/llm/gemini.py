"""Google Gemini API provider for MetaQA mutation verification.

This module implements the LLMClient interface using the official google-genai SDK.
It is used ONLY for MetaQA mutation verification — not for answer generation,
mutation generation, or Web Evidence. This enables cross-model verification:
Ollama/Gemma generates, Gemini verifies.

Security: The GEMINI_API_KEY is read from backend environment configuration only.
It is never logged, never returned in API responses, and never sent to the frontend.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.llm.mock import MockLLMClient

from app.llm.base import (
    LLMClient,
    LLMConnectionError,
    LLMEmptyResponseError,
    LLMError,
    LLMMalformedResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.client import parse_json_object

logger = logging.getLogger("verifact.llm.gemini")


def _parse_retry_delay(exc: Exception) -> float | None:
    """Extract recommended retry delay in seconds from Gemini API errors if present."""
    try:
        details = getattr(exc, "details", None)
        if isinstance(details, list):
            for d in details:
                if isinstance(d, dict) and "retryDelay" in d:
                    return float(str(d["retryDelay"]).rstrip("s"))
    except (TypeError, ValueError, AttributeError, KeyError):
        logger.debug("Failed parsing details retryDelay")
    try:
        msg = str(exc)
        match = re.search(r"retry(?:\s+in\s+|Delay['\":\s]+)([0-9.]+)\s*s?", msg, re.IGNORECASE)
        if match:
            return float(match.group(1))
    except (TypeError, ValueError):
        logger.debug("Failed regex retryDelay")
    return None



class GeminiVerifierPayload(BaseModel):
    verdict: Literal["YES", "NO", "NOT SURE"]
    rationale: str = ""


class GeminiVerifierError(LLMError):
    """Raised when Gemini verification fails. Never silently falls back to Ollama."""


class GeminiClient(LLMClient):
    """Google Gemini API client for MetaQA mutation verification.

    Uses the official google-genai SDK with structured JSON output.
    This client is purpose-built for short verification requests and should
    NOT be used for answer generation or mutation generation.
    """

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str = "gemini-3.8-flash",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        temperature: float = 0.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise GeminiVerifierError(
                "GEMINI_API_KEY is not configured. Cross-model verification requires "
                "a valid Gemini API key in the backend environment."
            )
        self._api_key = api_key.strip()
        self._default_model = default_model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._temperature = temperature
        self._client = None  # Lazy-initialized

    def _get_client(self):
        """Lazy-initialize the genai Client to avoid import failures when not configured."""
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except ImportError as exc:
                raise GeminiVerifierError(
                    "google-genai SDK is not installed. "
                    "Install it with: pip install google-genai"
                ) from exc
            except Exception as exc:
                raise GeminiConnectionError(
                    f"Failed to initialize Gemini client: {exc}"
                ) from exc
        return self._client

    async def complete_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        response_schema: Any | None = None,
    ) -> dict[str, Any]:
        """Send a JSON-mode request to Gemini and parse the response."""
        content = await self._generate(
            model=model or self._default_model,
            system_prompt=system_prompt,
            user_prompt=(
                f"{user_prompt}\n\n"
                "Return one JSON object only. No markdown fences. No commentary outside JSON."
            ),
            json_mode=True,
            max_tokens=max_tokens,
            response_schema=response_schema or GeminiVerifierPayload,
        )
        parsed = parse_json_object(content)
        if parsed is None:
            logger.warning(
                "Failed to parse JSON from Gemini model %s: %s",
                model,
                content[:500],
            )
            raise LLMMalformedResponseError("Gemini returned malformed or incomplete JSON.")
        return parsed

    async def complete_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> str:
        """Send a plain text request to Gemini."""
        return await self._generate(
            model=model or self._default_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=False,
            max_tokens=max_tokens,
        )

    async def _generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        max_tokens: int | None,
        response_schema: Any | None = None,
    ) -> str:
        """Core generation method with retries and error handling."""
        from google.genai import types

        client = self._get_client()
        effective_model = model or self._default_model

        config_kwargs: dict[str, Any] = {
            "temperature": self._temperature,
        }
        if max_tokens is not None:
            config_kwargs["max_output_tokens"] = max_tokens
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
            if response_schema is not None:
                config_kwargs["response_schema"] = response_schema
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        # Gemini 3.x uses thinking_level="low" (numeric thinking_budget=0 is deprecated in 3.x)
        try:
            if hasattr(types, "ThinkingConfig"):
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="low")
        except (TypeError, ValueError, AttributeError) as exc:
            logger.debug("ThinkingConfig not initialized: %s", exc)

        config = types.GenerateContentConfig(**config_kwargs)

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            gen_start = time.perf_counter()
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=effective_model,
                        contents=user_prompt,
                        config=config,
                    ),
                    timeout=self._timeout_seconds,
                )
                elapsed_ms = (time.perf_counter() - gen_start) * 1000

                # Extract text from response
                if response is None:
                    raise LLMEmptyResponseError("Gemini returned no response.")

                text = getattr(response, "text", None)
                if not text or not text.strip():
                    # Check for safety blocks or other issues
                    candidates = getattr(response, "candidates", None)
                    if candidates and len(candidates) > 0:
                        candidate = candidates[0]
                        finish_reason = getattr(candidate, "finish_reason", None)
                        if finish_reason and str(finish_reason).upper() == "SAFETY":
                            raise LLMError(
                                "Gemini blocked the response due to safety filters."
                            )
                    raise LLMEmptyResponseError("Gemini returned an empty response.")

                logger.info(
                    "Gemini API request succeeded model=%s elapsed_ms=%.1f json_mode=%s tokens_max=%s",
                    effective_model,
                    elapsed_ms,
                    json_mode,
                    max_tokens,
                )
                return text.strip()

            except asyncio.TimeoutError:
                last_error = LLMTimeoutError(
                    f"Gemini request timed out after {self._timeout_seconds}s."
                )
                logger.warning(
                    "Gemini timeout for model %s (attempt %s/%s)",
                    effective_model,
                    attempt + 1,
                    self._max_retries + 1,
                )
                if attempt >= self._max_retries:
                    raise last_error

            except LLMError:
                raise

            except Exception as exc:
                exc_str = str(exc)
                lower_exc = exc_str.lower()
                status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)

                # Check for 429 Rate Limit / Quota Exceeded
                if "429" in lower_exc or "rate" in lower_exc or "quota" in lower_exc or status_code == 429:
                    last_error = LLMRateLimitError(
                        f"Gemini API returned HTTP 429 (rate limit): {exc_str}"
                    )
                    logger.warning(
                        "Gemini rate-limited for model %s (attempt %s/%s): %s",
                        effective_model,
                        attempt + 1,
                        self._max_retries + 1,
                        exc_str[:200],
                    )
                    # If daily quota on 3.8 is reached, fallback to gemini-3.5-flash
                    if (
                        "gemini-3.8-flash" in effective_model
                        and ("generaterequestsperday" in lower_exc or attempt >= 1)
                        and attempt < self._max_retries
                    ):
                        logger.warning(
                            "Gemini model %s rate/quota limit encountered, retrying with gemini-3.5-flash",
                            effective_model,
                        )
                        effective_model = "gemini-3.5-flash"
                        continue

                    if attempt >= self._max_retries:
                        raise last_error from exc

                    delay = _parse_retry_delay(exc)
                    backoff = (2 ** (attempt + 1)) + random.uniform(0.5, 2.0)
                    sleep_secs = min(max(delay + 0.5, backoff) if delay else backoff, 60.0)
                    await asyncio.sleep(sleep_secs)
                    continue

                # Check for 503 High Demand / Service Unavailable
                elif "503" in lower_exc or "unavailable" in lower_exc or "high demand" in lower_exc or status_code == 503:
                    last_error = GeminiVerifierError(
                        f"Gemini API returned HTTP 503 (service unavailable): {exc_str}"
                    )
                    logger.warning(
                        "Gemini 503 unavailable for model %s (attempt %s/%s): %s",
                        effective_model,
                        attempt + 1,
                        self._max_retries + 1,
                        exc_str[:200],
                    )
                    if (
                        "gemini-3.8-flash" in effective_model
                        and attempt >= 1
                        and attempt < self._max_retries
                    ):
                        logger.warning(
                            "Gemini 3.8-flash persistent 503 high demand, falling back to gemini-3.5-flash"
                        )
                        effective_model = "gemini-3.5-flash"
                        continue

                    if attempt >= self._max_retries:
                        raise last_error from exc

                    delay = _parse_retry_delay(exc)
                    backoff = (2 ** (attempt + 1)) + random.uniform(0.5, 2.0)
                    sleep_secs = min(max(delay + 0.5, backoff) if delay else backoff, 30.0)
                    await asyncio.sleep(sleep_secs)
                    continue

                # Check for 404 Model Not Found (e.g. retired 2.5-flash)
                elif "not found" in lower_exc or "404" in lower_exc or status_code == 404:
                    if "gemini-2.5-flash" in effective_model and attempt < self._max_retries:
                        logger.warning(
                            "Gemini model %s retired/404, retrying with gemini-3.8-flash",
                            effective_model,
                        )
                        effective_model = "gemini-3.8-flash"
                        continue
                    raise GeminiVerifierError(
                        f"Gemini API returned HTTP 404: model '{effective_model}' not found. "
                        f"Check GEMINI_VERIFIER_MODEL configuration."
                    ) from exc

                # Check for 401/403 Unauthorized
                elif "api key" in lower_exc or "401" in lower_exc or "403" in lower_exc or status_code in (401, 403):
                    raise GeminiVerifierError(
                        "Gemini API returned HTTP 401/403 (unauthorized). "
                        "Check GEMINI_API_KEY configuration."
                    ) from exc

                else:
                    last_error = GeminiVerifierError(
                        f"Gemini verification request failed: {exc_str}"
                    )
                    logger.warning(
                        "Gemini request failed for model %s (attempt %s/%s): %s",
                        effective_model,
                        attempt + 1,
                        self._max_retries + 1,
                        exc_str[:200],
                    )
                    if attempt >= self._max_retries:
                        raise last_error from exc
                    backoff = (2 ** (attempt + 1)) + random.uniform(0.5, 2.0)
                    await asyncio.sleep(min(backoff, 20.0))
                    continue

            # Exponential backoff between generic retries
            backoff = (2 ** (attempt + 1)) + random.uniform(0.5, 2.0)
            await asyncio.sleep(min(backoff, 15.0))

        raise last_error or GeminiVerifierError("Gemini request failed after retries.")


class GeminiConnectionError(GeminiVerifierError, LLMConnectionError):
    """Raised when connecting to Gemini API fails."""


class MockGeminiClient(LLMClient):
    """Mock Gemini verifier for tests and LLM_MODE=mock.

    Implements the same LLMClient interface as GeminiClient but returns
    deterministic responses without requiring a Gemini API key.
    This ensures tests can run without external API calls.
    """

    def __init__(
        self,
        *,
        scenario: str = "reliable",
        inner: MockLLMClient | None = None,
    ) -> None:
        from app.llm.mock import MockLLMClient

        if inner is not None:
            self._inner = inner
        else:
            self._inner = MockLLMClient(scenario=scenario)

    async def complete_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        response_schema: Any | None = None,
    ) -> dict[str, Any]:
        return await self._inner.complete_json(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )

    async def complete_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> str:
        return await self._inner.complete_text(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )
