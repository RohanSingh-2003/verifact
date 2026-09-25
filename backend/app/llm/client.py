from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from app.config import Settings
from app.llm.base import LLMClient, LLMError, LLMRateLimitError, LLMTimeoutError

logger = logging.getLogger("verifact.llm")

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class OpenAICompatibleClient(LLMClient):
    """Chat-completions client for OpenAI-compatible providers (including Ollama /v1)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.openai_base_url.rstrip("/"),
            timeout=settings.llm_timeout_seconds,
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
            user_prompt=user_prompt,
            json_mode=True,
            max_tokens=max_tokens,
        )
        parsed = parse_json_object(content)
        if parsed is None:
            logger.warning("Failed to parse JSON from model %s: %s", model, content[:500])
            raise LLMError("Model returned malformed JSON.")
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
        key = self._settings.openai_api_key.strip()
        if not key or key.startswith("replace-with-"):
            raise LLMError("OPENAI_API_KEY is not configured.")

        # Temperature is fixed for a run. Hosted APIs may still vary across calls.
        predict = max_tokens if max_tokens is not None else self._settings.llm_max_output_tokens
        payload: dict[str, Any] = {
            "model": model,
            "temperature": self._settings.llm_temperature,
            "max_tokens": predict,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(self._settings.llm_max_retries + 1):
            try:
                response = await self._client.post(
                    "/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json=payload,
                )
                if response.status_code == 429:
                    last_error = LLMRateLimitError("LLM provider rate-limited the request.")
                    logger.warning("LLM rate limit for model %s (attempt %s)", model, attempt + 1)
                    if attempt >= self._settings.llm_max_retries:
                        raise last_error
                    await asyncio.sleep(min(2 ** attempt, 20))
                    continue
                if response.status_code >= 500:
                    last_error = LLMError(f"LLM provider returned HTTP {response.status_code}.")
                    logger.error("LLM HTTP %s for model %s", response.status_code, model)
                    if attempt >= self._settings.llm_max_retries:
                        raise last_error
                    await asyncio.sleep(min(2 ** attempt, 20))
                    continue
                if response.status_code >= 400:
                    logger.error(
                        "LLM HTTP %s for model %s: %s",
                        response.status_code,
                        model,
                        response.text[:500],
                    )
                    raise LLMError(f"LLM provider returned HTTP {response.status_code}.")
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise LLMError("LLM provider returned an empty completion.")
                return content.strip()
            except httpx.TimeoutException as exc:
                last_error = LLMTimeoutError("LLM request timed out.")
                logger.warning("LLM timeout for model %s (attempt %s)", model, attempt + 1)
                if attempt >= self._settings.llm_max_retries:
                    raise last_error from exc
                await asyncio.sleep(min(2 ** attempt, 20))
            except LLMRateLimitError:
                raise
            except LLMError as exc:
                if "HTTP 4" in str(exc) and "HTTP 429" not in str(exc):
                    raise
                last_error = exc
                if attempt >= self._settings.llm_max_retries:
                    raise
                await asyncio.sleep(min(2 ** attempt, 20))
            except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                last_error = LLMError("LLM provider request failed.")
                logger.exception("LLM call failed for model %s", model)
                if attempt >= self._settings.llm_max_retries:
                    raise last_error from exc
                await asyncio.sleep(min(2 ** attempt, 20))
        raise last_error or LLMError("LLM provider request failed.")


def parse_json_object(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = JSON_BLOCK.search(text)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None
