from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.llm.base import (
    LLMConnectionError,
    LLMEmptyResponseError,
    LLMError,
    LLMMalformedResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.client import parse_json_object
from app.llm.prompts import ANSWER_SYSTEM, ANSWER_USER
from app.llm.providers import ModelClient

logger = logging.getLogger("verifact.llm.cloudflare")


class CloudflareClient(ModelClient):
    """Cloudflare Workers AI REST API client for GLM-4.7-Flash (@cf/zai-org/glm-4.7-flash)."""

    def __init__(
        self,
        *,
        api_token: str,
        account_id: str,
        model_name: str = "@cf/zai-org/glm-4.7-flash",
        base_url: str = "https://api.cloudflare.com/client/v4",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self._api_token = (api_token or "").strip()
        self.account_id = (account_id or "").strip()
        self.model_name = (model_name or "@cf/zai-org/glm-4.7-flash").strip()
        self.base_url = (base_url or "https://api.cloudflare.com/client/v4").strip().rstrip("/")
        self.provider_name = "Cloudflare Workers AI"
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def endpoint_url(self) -> str:
        """Construct the REST API endpoint for the Cloudflare Workers AI model."""
        clean_model = self.model_name.lstrip("/")
        if "/accounts/" in self.base_url:
            if self.base_url.endswith("/ai/run"):
                return f"{self.base_url}/{clean_model}"
            return f"{self.base_url}/ai/run/{clean_model}"
        return f"{self.base_url}/accounts/{self.account_id}/ai/run/{clean_model}"

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
        return await self._run_ai(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
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
        content = await self.complete_text(
            system_prompt=system_prompt,
            user_prompt=f"{user_prompt}\n\nReturn a valid JSON object only. No commentary or markdown formatting outside JSON.",
            max_tokens=max_tokens,
            temperature=temperature,
        )
        parsed = parse_json_object(content)
        if parsed is None:
            logger.warning(
                "Failed to parse JSON from %s (%s): %s",
                self.provider_name,
                self.model_name,
                content[:500],
            )
            raise LLMMalformedResponseError(f"{self.provider_name} returned malformed JSON.")
        return parsed

    async def _run_ai(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None,
        temperature: float,
    ) -> str:
        if not self._api_token or self._api_token.startswith("replace-with-"):
            raise LLMError("Cloudflare Workers AI API token is not configured.")
        if not self.account_id or self.account_id.startswith("replace-with-"):
            raise LLMError("Cloudflare Workers AI Account ID is not configured.")

        payload: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature

        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

        url = self.endpoint_url
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.post(
                    url,
                    headers=headers,
                    json=payload,
                )
                if response.status_code == 429:
                    last_error = LLMRateLimitError(
                        f"{self.provider_name} rate-limited the request (HTTP 429)."
                    )
                    logger.warning(
                        "%s rate limit (attempt %s/%s)",
                        self.provider_name,
                        attempt + 1,
                        self.max_retries + 1,
                    )
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
                    logger.error(
                        "%s HTTP %s: %s",
                        self.provider_name,
                        response.status_code,
                        response.text[:400],
                    )
                    raise LLMError(f"{self.provider_name} returned HTTP {response.status_code}.")

                try:
                    data = response.json()
                except Exception as exc:
                    raise LLMMalformedResponseError(
                        f"{self.provider_name} returned non-JSON response."
                    ) from exc

                return self._extract_response_text(data)

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
                last_error = LLMConnectionError(
                    f"Could not connect to {self.provider_name} at {url}."
                )
                if attempt >= self.max_retries:
                    raise last_error from exc
                await asyncio.sleep(min(2**attempt, 15))
            except Exception as exc:
                last_error = LLMError(f"{self.provider_name} request failed: {exc}")
                if attempt >= self.max_retries:
                    raise last_error from exc
                await asyncio.sleep(min(2**attempt, 15))

        raise last_error or LLMError(f"{self.provider_name} request failed.")

    def _extract_response_text(self, data: Any) -> str:
        """Extract generated string from Cloudflare Workers AI response envelope."""
        if not isinstance(data, dict):
            if isinstance(data, str) and data.strip():
                return data.strip()
            raise LLMMalformedResponseError(f"{self.provider_name} returned invalid response format.")

        if data.get("success") is False:
            errors = data.get("errors") or []
            err_msg = "; ".join(e.get("message", str(e)) for e in errors) if errors else "Request failed."
            raise LLMError(f"{self.provider_name} error: {err_msg}")

        result = data.get("result")
        if result is not None:
            if isinstance(result, dict):
                if "response" in result and isinstance(result["response"], str):
                    content = result["response"].strip()
                    if content:
                        return content
                if "choices" in result and isinstance(result["choices"], list) and result["choices"]:
                    msg = result["choices"][0].get("message", {})
                    if isinstance(msg, dict) and "content" in msg and isinstance(msg["content"], str):
                        content = msg["content"].strip()
                        if content:
                            return content
                for key in ("text", "content", "output"):
                    if key in result and isinstance(result[key], str):
                        content = result[key].strip()
                        if content:
                            return content
            elif isinstance(result, str) and result.strip():
                return result.strip()

        if "response" in data and isinstance(data["response"], str):
            content = data["response"].strip()
            if content:
                return content

        if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
            msg = data["choices"][0].get("message", {})
            if isinstance(msg, dict) and "content" in msg and isinstance(msg["content"], str):
                content = msg["content"].strip()
                if content:
                    return content

        raise LLMEmptyResponseError(f"{self.provider_name} returned an empty completion.")
