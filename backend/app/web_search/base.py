from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass(frozen=True)
class WebSource:
    """Provider-agnostic web search hit used by Web Evidence."""

    title: str
    url: str
    domain: str
    snippet: str
    published_at: str | None = None
    relevance_score: float | None = None
    # Metadata only — not a truth score.
    source_type: str = "GENERAL"
    question_type: str | None = None
    evidence_summary: str | None = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "domain": self.domain,
            "snippet": self.snippet,
            "published_at": self.published_at,
            "relevance_score": self.relevance_score,
            "source_type": self.source_type,
            "question_type": self.question_type,
            "evidence_summary": self.evidence_summary,
        }


def domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.strip().lower()
        host = host.removeprefix("www.")
        return host or "unknown"
    except (TypeError, ValueError, AttributeError):
        return "unknown"


class WebSearchError(RuntimeError):
    """Raised when a web search provider call fails."""


class WebSearchAuthError(WebSearchError):
    """Invalid or missing API key."""


class WebSearchRateLimitError(WebSearchError):
    """Provider rate limit (HTTP 429)."""


class WebSearchTimeoutError(WebSearchError):
    """Provider request timed out."""


class WebSearchClient(ABC):
    @abstractmethod
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
        """Return normalized search results for a query."""


@dataclass
class InMemorySearchCache:
    """Simple process-local cache to avoid duplicate Tavily hits in one process."""

    _store: dict[str, list[WebSource]] = field(default_factory=dict)

    @staticmethod
    def _key(
        query: str,
        max_results: int,
        include_domains: list[str] | None,
        days: int | None,
        topic: str | None,
        question_type: str | None = None,
    ) -> str:
        domains = ",".join(sorted(d.strip().lower() for d in (include_domains or []) if d.strip()))
        return (
            f"{query.strip().casefold()}::{question_type or ''}::{max_results}::{domains}"
            f"::{days or ''}::{(topic or '').strip().lower()}"
        )

    def get(
        self,
        query: str,
        max_results: int,
        *,
        include_domains: list[str] | None = None,
        days: int | None = None,
        topic: str | None = None,
        question_type: str | None = None,
    ) -> list[WebSource] | None:
        return self._store.get(
            self._key(query, max_results, include_domains, days, topic, question_type)
        )

    def set(
        self,
        query: str,
        max_results: int,
        results: list[WebSource],
        *,
        include_domains: list[str] | None = None,
        days: int | None = None,
        topic: str | None = None,
        question_type: str | None = None,
    ) -> None:
        self._store[
            self._key(query, max_results, include_domains, days, topic, question_type)
        ] = list(results)


# Shared process cache for development credit protection.
SEARCH_CACHE = InMemorySearchCache()
