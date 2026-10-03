from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings
from app.web_evidence.source_quality import classify_source_type
from app.web_search.base import (
    SEARCH_CACHE,
    WebSearchAuthError,
    WebSearchClient,
    WebSearchError,
    WebSearchRateLimitError,
    WebSearchTimeoutError,
    WebSource,
    domain_from_url,
)

logger = logging.getLogger("verifact.web_search.tavily")


class TavilyClient(WebSearchClient):
    """Tavily Basic Search client. Never raises for empty results — returns []."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._api_key = settings.tavily_api_key.strip()
        self._base_url = settings.tavily_base_url.rstrip("/")
        self._timeout = settings.tavily_timeout_seconds
        self._depth = settings.tavily_search_depth

    async def search(
        self,
        query: str,
        *,
        max_results: int = 3,
        include_domains: list[str] | None = None,
        days: int | None = None,
        topic: str | None = None,
        question_type: str | None = None,
    ) -> list[WebSource]:
        cleaned = " ".join(query.split()).strip()
        if not cleaned:
            return []
        if not self._api_key or self._api_key.startswith("replace-with-"):
            raise WebSearchAuthError("Tavily API key is not configured.")

        domains = [d.strip().lower() for d in (include_domains or []) if d and d.strip()]
        topic_value = (topic or "general").strip().lower() or "general"
        if topic_value not in {"general", "news"}:
            topic_value = "general"

        cached = SEARCH_CACHE.get(
            cleaned,
            max_results,
            include_domains=domains,
            days=days,
            topic=topic_value,
            question_type=question_type,
        )
        if cached is not None:
            logger.info("tavily cache hit query=%r results=%s", cleaned[:80], len(cached))
            return list(cached)

        payload: dict[str, Any] = {
            "api_key": self._api_key,
            "query": cleaned,
            "search_depth": self._depth,
            "max_results": max(1, min(max_results, 10)),
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "topic": topic_value,
        }
        if domains:
            payload["include_domains"] = domains[:8]
        if days is not None and days > 0:
            payload["days"] = int(days)

        url = f"{self._base_url}/search"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise WebSearchTimeoutError("Tavily search timed out.") from exc
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Tavily request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise WebSearchAuthError("Tavily API key was rejected.")
        if response.status_code == 429:
            raise WebSearchRateLimitError("Tavily rate limit exceeded.")
        if response.status_code >= 400:
            detail = response.text[:200]
            # Never echo API key material if accidentally present.
            raise WebSearchError(f"Tavily returned HTTP {response.status_code}: {detail}")

        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise WebSearchError("Tavily returned invalid JSON.") from exc

        results = normalize_tavily_results(data.get("results") or [])
        SEARCH_CACHE.set(
            cleaned,
            max_results,
            results,
            include_domains=domains,
            days=days,
            topic=topic_value,
            question_type=question_type,
        )
        logger.info(
            "tavily search query=%r depth=%s topic=%s domains=%s days=%s results=%s",
            cleaned[:80],
            self._depth,
            topic_value,
            len(domains),
            days,
            len(results),
        )
        return results


def normalize_tavily_results(raw_items: list[Any]) -> list[WebSource]:
    sources: list[WebSource] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        title = str(item.get("title") or "").strip() or url
        snippet = str(item.get("content") or item.get("snippet") or "").strip()
        published = item.get("published_date") or item.get("published_at")
        published_at = str(published).strip() if published else None
        score_raw = item.get("score")
        relevance: float | None
        try:
            relevance = float(score_raw) if score_raw is not None else None
        except (TypeError, ValueError):
            relevance = None
        domain = domain_from_url(url)
        sources.append(
            WebSource(
                title=title,
                url=url,
                domain=domain,
                snippet=snippet[:1200],
                published_at=published_at,
                relevance_score=relevance,
                source_type=classify_source_type(domain).value,
            )
        )
    return sources
