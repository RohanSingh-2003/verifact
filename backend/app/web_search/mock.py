from __future__ import annotations

from app.web_evidence.source_quality import classify_source_type
from app.web_search.base import WebSearchClient, WebSearchError, WebSource, domain_from_url


def _annotate(source: WebSource) -> WebSource:
    domain = source.domain or domain_from_url(source.url)
    return WebSource(
        title=source.title,
        url=source.url,
        domain=domain,
        snippet=source.snippet,
        published_at=source.published_at,
        relevance_score=source.relevance_score,
        source_type=source.source_type or classify_source_type(domain).value,
        question_type=source.question_type,
    )


class MockTavilyClient(WebSearchClient):
    """Deterministic web search for tests and Demo / Mock Mode."""

    def __init__(
        self,
        *,
        results_by_query: dict[str, list[WebSource]] | None = None,
        default_results: list[WebSource] | None = None,
        fail_with: Exception | None = None,
        empty: bool = False,
        fail_queries: set[str] | None = None,
        preferred_empty: bool = False,
        fallback_results: list[WebSource] | None = None,
    ) -> None:
        self.results_by_query = {k.casefold(): list(v) for k, v in (results_by_query or {}).items()}
        self.default_results = list(default_results or _default_sources())
        self.fail_with = fail_with
        self.empty = empty
        self.fail_queries = {q.casefold() for q in (fail_queries or set())}
        self.preferred_empty = preferred_empty
        self.fallback_results = list(fallback_results) if fallback_results is not None else None
        self.calls: list[str] = []
        self.call_options: list[dict] = []

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
        self.calls.append(query)
        self.call_options.append(
            {
                "include_domains": list(include_domains or []),
                "days": days,
                "topic": topic,
                "question_type": question_type,
            }
        )
        if self.fail_with is not None:
            raise self.fail_with
        if query.strip().casefold() in self.fail_queries:
            raise WebSearchError("mock per-query failure")
        if self.empty:
            return []

        # Preferred-domain pass can be empty to exercise fallback.
        if include_domains and self.preferred_empty:
            return []

        key = query.strip().casefold()
        hits = self.results_by_query.get(key)
        if hits is None:
            for stored_key, stored in self.results_by_query.items():
                if stored_key and stored_key in key:
                    hits = stored
                    break
        if hits is None:
            if include_domains is None and self.fallback_results is not None:
                hits = self.fallback_results
            else:
                hits = self.default_results

        # If domain filter is set, keep only matching domains when possible.
        if include_domains:
            allowed = {d.strip().lower().removeprefix("www.") for d in include_domains if d}
            filtered = [
                item
                for item in hits
                if any(
                    (item.domain or domain_from_url(item.url)).endswith(domain)
                    or domain.endswith(item.domain or "")
                    for domain in allowed
                )
            ]
            if filtered:
                hits = filtered
            elif self.preferred_empty:
                return []

        return [_annotate(item) for item in hits[: max(1, max_results)]]


def _default_sources() -> list[WebSource]:
    url = "https://en.wikipedia.org/wiki/Penicillin"
    return [
        WebSource(
            title="Penicillin — Wikipedia",
            url=url,
            domain=domain_from_url(url),
            snippet=(
                "Alexander Fleming discovered penicillin in 1928 at St Mary's Hospital in London."
            ),
            published_at=None,
            relevance_score=0.92,
            source_type="REFERENCE",
        ),
        WebSource(
            title="History of penicillin",
            url="https://www.britannica.com/science/penicillin",
            domain="britannica.com",
            snippet="Fleming observed antibacterial mold growth in 1928, later identified as penicillin.",
            published_at=None,
            relevance_score=0.88,
            source_type="REFERENCE",
        ),
        WebSource(
            title="Discovery of penicillin",
            url="https://www.sciencehistory.org/education/scientific-biographies/alexander-fleming/",
            domain="sciencehistory.org",
            snippet="Alexander Fleming discovered penicillin while working at St Mary's Hospital, London.",
            published_at=None,
            relevance_score=0.85,
            source_type="GENERAL",
        ),
    ]
