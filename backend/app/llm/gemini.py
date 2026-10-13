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
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.llm.client import parse_json_object

logger = logging.getLogger("verifact.llm.gemini")


def _sanitize_error_message(msg: str, api_key: str | None = None) -> str:
    """Mask any API keys or credentials from error strings."""
    if not msg:
        return ""
    sanitized = str(msg)
    if api_key and api_key.strip():
        sanitized = sanitized.replace(api_key.strip(), "[MASKED_API_KEY]")
    # Mask standard Google API key patterns (AIza...) and key=... query params
    sanitized = re.sub(r"AIza[0-9A-Za-z\-_]{35}", "[MASKED_API_KEY]", sanitized)
    sanitized = re.sub(r"key=([0-9A-Za-z\-_]+)", "key=[MASKED]", sanitized)
    return sanitized


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
    """Raised when Gemini verification fails. Never silently falls back to Ollama or substitutes models."""


class GeminiUnavailableError(GeminiVerifierError, LLMUnavailableError):
    """Raised when Gemini is temporarily unavailable (HTTP 503 / high demand)."""


class GeminiRateLimitError(GeminiVerifierError, LLMRateLimitError):
    """Raised when Gemini rate limit or quota is exceeded (HTTP 429)."""


class GeminiAuthError(GeminiVerifierError):
    """Raised on authentication failure (HTTP 401 - invalid or unauthenticated API key). Non-retryable."""


class GeminiPermissionError(GeminiVerifierError):
    """Raised on authorization failure (HTTP 403 - permission denied / API not enabled). Non-retryable."""


class GeminiModelNotFoundError(GeminiVerifierError, LLMModelNotFoundError):
    """Raised when the specified Gemini model is not found (HTTP 404). Non-retryable."""


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
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        temperature: float = 0.0,
        initial_retry_delay: float = 1.0,
        max_retry_delay: float = 10.0,
        total_retry_timeout: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: float = 0.5,
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
        self._initial_retry_delay = initial_retry_delay
        self._max_retry_delay = max_retry_delay
        self._total_retry_timeout = total_retry_timeout
        self._backoff_factor = backoff_factor
        self._jitter = jitter
        self._client = None  # Lazy-initialized

    def _get_client(self):
        """Lazy-initialize the genai Client to avoid import failures when not configured."""
        if self._client is None:
            try:
                from google import genai
                from google.genai import types

                # Explicitly disable SDK-level retries so the outer loop in GeminiClient
                # has full bounded control and does not multiply attempts across layers.
                http_options = types.HttpOptions(
                    retry_options=types.HttpRetryOptions(attempts=1),
                )
                self._client = genai.Client(api_key=self._api_key, http_options=http_options)
            except ImportError as exc:
                raise GeminiVerifierError(
                    "google-genai SDK is not installed. "
                    "Install it with: pip install google-genai"
                ) from exc
            except Exception as exc:
                raise GeminiConnectionError(
                    f"Failed to initialize Gemini client: {_sanitize_error_message(str(exc), self._api_key)}"
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
        """Core generation method with bounded exponential-backoff retries and error isolation."""
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

        min_attempt_budget = min(1.0, max(0.01, self._total_retry_timeout / (self._max_retries + 1) * 0.2))
        start_overall = time.perf_counter()
        last_error: Exception | None = None
        timeout_count = 0
        attempts_made = 0

        for attempt in range(self._max_retries + 1):
            elapsed_overall = time.perf_counter() - start_overall
            remaining_total_budget = self._total_retry_timeout - elapsed_overall
            if remaining_total_budget < min_attempt_budget:
                logger.warning(
                    "Gemini total retry time budget (%.1fs) exhausted for model %s after %d attempts (remaining=%.2fs)",
                    self._total_retry_timeout,
                    effective_model,
                    attempt,
                    remaining_total_budget,
                )
                break

            attempts_made += 1
            retries_left = self._max_retries - attempt
            if retries_left > 0:
                # Ensure an individual attempt cannot consume the entire retry budget when retries are still available.
                # Reserve safe budget for subsequent attempts and backoff.
                reserved_for_retries = min(
                    remaining_total_budget * 0.5,
                    retries_left * (min_attempt_budget + min(self._initial_retry_delay, 1.0)),
                )
                max_for_attempt = max(min_attempt_budget, remaining_total_budget - reserved_for_retries)
                call_timeout = min(self._timeout_seconds, max_for_attempt)
            else:
                call_timeout = min(self._timeout_seconds, remaining_total_budget)

            call_timeout = max(min_attempt_budget, call_timeout)

            # Synchronize SDK-level HTTP timeout with per-attempt call_timeout
            try:
                if hasattr(types, "HttpOptions"):
                    config.http_options = types.HttpOptions(
                        timeout=max(1000, int(call_timeout * 1000)),
                        retry_options=types.HttpRetryOptions(attempts=1),
                    )
            except (TypeError, ValueError, AttributeError) as exc:
                logger.debug("HttpOptions on GenerateContentConfig not set: %s", exc)

            gen_start = time.perf_counter()
            last_raw_exc: Exception | None = None
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=effective_model,
                        contents=user_prompt,
                        config=config,
                    ),
                    timeout=call_timeout,
                )
                elapsed_ms = (time.perf_counter() - gen_start) * 1000

                # Extract text from response
                if response is None:
                    raise LLMEmptyResponseError("Gemini returned no response.")

                text = getattr(response, "text", None)
                if not text or not text.strip():
                    candidates = getattr(response, "candidates", None)
                    if candidates and len(candidates) > 0:
                        candidate = candidates[0]
                        finish_reason = getattr(candidate, "finish_reason", None)
                        if finish_reason and str(finish_reason).upper() == "SAFETY":
                            raise GeminiVerifierError(
                                "Gemini blocked the response due to safety filters."
                            )
                    raise LLMEmptyResponseError("Gemini returned an empty response.")

                logger.info(
                    "Gemini API request succeeded model=%s elapsed_ms=%.1f json_mode=%s tokens_max=%s attempts=%d",
                    effective_model,
                    elapsed_ms,
                    json_mode,
                    max_tokens,
                    attempt + 1,
                )
                return text.strip()

            except TimeoutError:
                timeout_count += 1
                last_error = LLMTimeoutError(
                    f"Gemini request timed out after {call_timeout:.1f}s."
                )
                logger.warning(
                    "Gemini timeout for model %s (attempt %d/%d, call_timeout=%.1fs)",
                    effective_model,
                    attempt + 1,
                    self._max_retries + 1,
                    call_timeout,
                )

            except GeminiVerifierError:
                # Re-raise permanent/safety errors raised internally
                raise

            except LLMError as exc:
                last_error = exc
                last_raw_exc = exc
                if isinstance(exc, LLMTimeoutError):
                    timeout_count += 1
                logger.warning(
                    "Gemini LLMError for model %s (attempt %d/%d): %s",
                    effective_model,
                    attempt + 1,
                    self._max_retries + 1,
                    _sanitize_error_message(str(exc), self._api_key)[:200],
                )

            except Exception as exc:
                last_raw_exc = exc
                exc_str = _sanitize_error_message(str(exc), self._api_key)
                lower_exc = exc_str.lower()
                status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)

                # 1. Non-retryable: 401 Unauthorized (invalid key, unauthenticated)
                if (
                    status_code == 401
                    or "api key not valid" in lower_exc
                    or "unauthenticated" in lower_exc
                    or "invalid api key" in lower_exc
                ):
                    raise GeminiAuthError(
                        "Gemini API returned HTTP 401 (unauthorized): Invalid API key. "
                        "Check GEMINI_API_KEY configuration."
                    ) from exc

                # 2. Non-retryable: 403 Forbidden / Permission Denied (unless it's quota-related)
                if (
                    status_code == 403
                    or "permission_denied" in lower_exc
                    or "forbidden" in lower_exc
                ):
                    if "quota" in lower_exc or "rate" in lower_exc or "exhausted" in lower_exc or "ratelimit" in lower_exc:
                        last_error = GeminiRateLimitError(
                            f"Gemini API returned HTTP 403 (quota/rate limit exceeded): {exc_str}"
                        )
                        logger.warning(
                            "Gemini 403 quota/rate limit for model %s (attempt %d/%d): %s",
                            effective_model,
                            attempt + 1,
                            self._max_retries + 1,
                            exc_str[:200],
                        )
                    else:
                        raise GeminiPermissionError(
                            f"Gemini API returned HTTP 403 (forbidden): Model access denied for '{effective_model}'. "
                            f"Check project permissions and API enablement in Google AI Studio."
                        ) from exc

                # 3. Non-retryable: Model Not Found (404)
                if status_code == 404 or "not found" in lower_exc or "not_found" in lower_exc:
                    raise GeminiModelNotFoundError(
                        f"Gemini API returned HTTP 404: model '{effective_model}' not found. "
                        f"Check GEMINI_VERIFIER_MODEL configuration."
                    ) from exc

                # 4. Non-retryable: Bad Request / Invalid Argument (400)
                if status_code == 400 or "invalid_argument" in lower_exc or "bad request" in lower_exc:
                    raise GeminiVerifierError(
                        f"Gemini API rejected request as invalid (HTTP 400): {exc_str}"
                    ) from exc

                # 5. Non-retryable: Safety Blocks
                if "safety" in lower_exc or "blocked" in lower_exc:
                    raise GeminiVerifierError(
                        f"Gemini blocked response due to safety filters: {exc_str}"
                    ) from exc

                # 5. Retryable: Timeouts (HTTP 504 / socket / client timeouts)
                if (
                    status_code == 504
                    or "timeout" in lower_exc
                    or "timed out" in lower_exc
                    or "deadline_exceeded" in lower_exc
                    or "connecttimeout" in lower_exc
                    or "readtimeout" in lower_exc
                ):
                    timeout_count += 1
                    last_error = LLMTimeoutError(
                        f"Gemini request timed out after {call_timeout:.1f}s."
                    )
                    logger.warning(
                        "Gemini request timeout for model %s (attempt %d/%d): %s",
                        effective_model,
                        attempt + 1,
                        self._max_retries + 1,
                        exc_str[:200],
                    )

                # 6. Retryable: 503 High Demand / Service Unavailable
                elif (
                    status_code == 503
                    or "503" in lower_exc
                    or "unavailable" in lower_exc
                    or "high demand" in lower_exc
                    or "overloaded" in lower_exc
                ):
                    last_error = GeminiUnavailableError(
                        "Google Gemini Flash 3.8 is temporarily unavailable due to high demand on Google's servers. Please try again later."
                    )
                    logger.warning(
                        "Gemini 503 unavailable for model %s (attempt %d/%d): %s",
                        effective_model,
                        attempt + 1,
                        self._max_retries + 1,
                        exc_str[:200],
                    )

                # 7. Retryable: 429 Rate Limit / Quota Exceeded
                elif (
                    status_code == 429
                    or "429" in lower_exc
                    or "rate" in lower_exc
                    or "quota" in lower_exc
                    or "resource_exhausted" in lower_exc
                ):
                    last_error = GeminiRateLimitError(
                        f"Gemini API returned HTTP 429 (rate limit): {exc_str}"
                    )
                    logger.warning(
                        "Gemini rate-limited for model %s (attempt %d/%d): %s",
                        effective_model,
                        attempt + 1,
                        self._max_retries + 1,
                        exc_str[:200],
                    )

                # 8. Retryable: 5xx Server Errors (500, 502)
                elif status_code in (500, 502) or "bad gateway" in lower_exc or "internal server error" in lower_exc:
                    last_error = GeminiVerifierError(
                        f"Gemini API server error (HTTP {status_code}): {exc_str}"
                    )
                    logger.warning(
                        "Gemini server error for model %s (attempt %d/%d): %s",
                        effective_model,
                        attempt + 1,
                        self._max_retries + 1,
                        exc_str[:200],
                    )

                else:
                    last_error = GeminiVerifierError(
                        f"Gemini verification request failed: {exc_str}"
                    )
                    logger.warning(
                        "Gemini request failed for model %s (attempt %d/%d): %s",
                        effective_model,
                        attempt + 1,
                        self._max_retries + 1,
                        exc_str[:200],
                    )

            if attempt >= self._max_retries:
                break

            elapsed = time.perf_counter() - start_overall
            remaining_budget = self._total_retry_timeout - elapsed
            if remaining_budget <= min_attempt_budget:
                logger.warning(
                    "Gemini retry budget exhausted for model %s before backoff sleep (remaining=%.2fs)",
                    effective_model,
                    remaining_budget,
                )
                break

            # Calculate bounded exponential backoff with jitter
            server_delay = _parse_retry_delay(last_raw_exc) if last_raw_exc is not None else None
            calc_backoff = (self._initial_retry_delay * (self._backoff_factor ** attempt)) + random.uniform(0.0, self._jitter)
            delay = server_delay if server_delay is not None else calc_backoff
            delay = min(delay, self._max_retry_delay)

            # Backoff must not exceed remaining budget, and must leave at least min_attempt_budget for next attempt
            max_sleep = remaining_budget - min_attempt_budget
            if max_sleep <= 0.0:
                logger.warning(
                    "Insufficient time remaining (%.2fs) for backoff sleep and next attempt",
                    remaining_budget,
                )
                break

            sleep_secs = min(delay, max_sleep)
            await asyncio.sleep(sleep_secs)

        if timeout_count > 0:
            if attempts_made > 1 or timeout_count > 1:
                raise LLMTimeoutError(
                    "Gemini timed out after multiple attempts. Please try again later."
                )
            if isinstance(last_error, LLMTimeoutError):
                raise last_error
            raise LLMTimeoutError(
                "Gemini timed out after multiple attempts. Please try again later."
            )

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
