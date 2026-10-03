from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import Settings
from app.llm.base import LLMClient, LLMError, LLMRateLimitError, LLMTimeoutError
from app.llm.client import parse_json_object

logger = logging.getLogger("verifact.llm.ollama")



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


def native_ollama_base_url(settings: Settings) -> str:
    """Derive http://host:11434 from OLLAMA_BASE_URL (which may end with /v1)."""
    url = settings.ollama_base_url.strip().rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3].rstrip("/")
    return url


class OllamaClient(LLMClient):
    """Local Ollama client via the native /api/chat endpoint.

    Gemma thinking models on the OpenAI-compatible /v1 path often spend the
    entire max_tokens budget on reasoning and return empty/malformed JSON.
    The native API supports think=false, which keeps MetaQA JSON usable.

    One httpx.AsyncClient is reused for the process lifetime (via get_llm_client cache).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=native_ollama_base_url(settings),
            timeout=settings.llm_timeout_seconds,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        content = await self._chat(
            model=model,
            system_prompt=system_prompt,
            user_prompt=(
                f"{user_prompt}\n\n"
                "Return one JSON object only. No markdown fences. No commentary outside JSON."
            ),
            json_mode=True,
            max_tokens=max_tokens,
        )
        parsed = parse_json_object(content)
        if parsed is None:
            logger.warning("Failed to parse JSON from Ollama model %s: %s", model, content[:500])
            raise LLMError("Model returned malformed JSON.")
        if isinstance(parsed, dict):
            parsed["_raw"] = content
        return parsed

    async def complete_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> str:
        return await self._chat(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=False,
            max_tokens=max_tokens,
        )

    async def _chat(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        max_tokens: int | None,
    ) -> str:
        predict = max_tokens if max_tokens is not None else self._settings.llm_max_output_tokens
        payload: dict[str, Any] = {
            "model": model,
            "stream": False,
            "think": False,
            "keep_alive": self._settings.ollama_keep_alive,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": self._settings.llm_temperature,
                "num_predict": predict,
            },
        }
        if json_mode:
            payload["format"] = "json"

        concurrency = getattr(self._settings, "ollama_max_concurrency", 1)
        sem = get_ollama_semaphore(concurrency)
        async with sem:
            increment_ollama_call_count()
            last_error: Exception | None = None
            for attempt in range(self._settings.llm_max_retries + 1):
                try:
                    response = await self._client.post("/api/chat", json=payload)
                    if response.status_code == 429:
                        last_error = LLMRateLimitError("Ollama rate-limited the request.")
                        if attempt >= self._settings.llm_max_retries:
                            raise last_error
                        await asyncio.sleep(min(2**attempt, 20))
                        continue
                    if response.status_code >= 500:
                        last_error = LLMError(f"Ollama returned HTTP {response.status_code}.")
                        logger.error("Ollama HTTP %s for model %s", response.status_code, model)
                        if attempt >= self._settings.llm_max_retries:
                            raise last_error
                        await asyncio.sleep(min(2**attempt, 20))
                        continue
                    if response.status_code >= 400:
                        logger.error(
                            "Ollama HTTP %s for model %s: %s",
                            response.status_code,
                            model,
                            response.text[:500],
                        )
                        raise LLMError(f"Ollama returned HTTP {response.status_code}.")
                    data = response.json()
                    message = data.get("message") or {}
                    content = message.get("content")
                    if not isinstance(content, str) or not content.strip():
                        raise LLMError("Ollama returned an empty completion.")
                    return content.strip()
                except httpx.TimeoutException as exc:
                    last_error = LLMTimeoutError("Ollama request timed out.")
                    logger.warning("Ollama timeout for model %s (attempt %s)", model, attempt + 1)
                    if attempt >= self._settings.llm_max_retries:
                        raise last_error from exc
                    await asyncio.sleep(min(2**attempt, 20))
                except LLMRateLimitError:
                    raise
                except LLMError as exc:
                    if "HTTP 4" in str(exc) and "HTTP 429" not in str(exc):
                        raise
                    last_error = exc
                    if attempt >= self._settings.llm_max_retries:
                        raise
                    await asyncio.sleep(min(2**attempt, 20))
                except httpx.ConnectError as exc:
                    base_url = native_ollama_base_url(self._settings)
                    last_error = LLMError(
                        f"Cannot connect to Ollama at {base_url}. "
                        "Is the Ollama daemon running? Start it with 'ollama serve'."
                    )
                    logger.error(
                        "Ollama connection refused for model %s at %s (attempt %s)",
                        model, base_url, attempt + 1,
                    )
                    if attempt >= self._settings.llm_max_retries:
                        raise last_error from exc
                    await asyncio.sleep(min(2**attempt, 20))
                except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    last_error = LLMError("Ollama request failed.")
                    logger.exception("Ollama call failed for model %s", model)
                    if attempt >= self._settings.llm_max_retries:
                        raise last_error from exc
                    await asyncio.sleep(min(2**attempt, 20))
            raise last_error or LLMError("Ollama request failed.")
