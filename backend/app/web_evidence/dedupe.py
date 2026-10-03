"""URL normalization and source deduplication helpers."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.web_search.base import WebSource, domain_from_url

# Tracking / session params that do not change page identity.
_STRIP_QUERY_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "gclid",
        "fbclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "ref_url",
        "source",
        "si",
    }
)


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication without merging distinct pages.

    Handles trailing slash differences and common tracking query params.
    Does not collapse different paths on the same domain.
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except ValueError:
        return raw.casefold()

    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").lower().removeprefix("www.")
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    kept_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in _STRIP_QUERY_KEYS
    ]
    query = urlencode(kept_pairs, doseq=True)

    # Drop fragments — they usually point to the same page.
    normalized = urlunparse((scheme, netloc, path, "", query, ""))
    return normalized


def _content_fingerprint(source: WebSource) -> str:
    """Create a normalized fingerprint from title and snippet to detect syndicated copies."""
    title_norm = "".join(ch for ch in source.title.casefold() if ch.isalnum() or ch.isspace())
    words = title_norm.split()
    if len(words) >= 4:
        return "title::" + " ".join(words[:10])
    snippet_norm = "".join(ch for ch in (source.snippet or "").casefold() if ch.isalnum() or ch.isspace())
    snip_words = snippet_norm.split()
    if len(snip_words) >= 6:
        return "snip::" + " ".join(snip_words[:12])
    return ""


def dedupe_sources(sources: list[WebSource]) -> list[WebSource]:
    """Keep first occurrence of each URL; prefer higher-tier sources for syndicated duplicates."""
    from app.web_evidence.source_quality import source_tier_rank

    seen_urls: set[str] = set()
    fingerprint_to_index: dict[str, int] = {}
    unique: list[WebSource] = []

    for source in sources:
        url_key = normalize_url(source.url) or source.url.strip().casefold()
        if not url_key or url_key in seen_urls:
            continue
        seen_urls.add(url_key)

        fp = _content_fingerprint(source)
        if fp and fp in fingerprint_to_index:
            existing_idx = fingerprint_to_index[fp]
            existing = unique[existing_idx]
            # If the new source is higher tier (lower rank number), replace the duplicate with the primary!
            if source_tier_rank(source.source_type) < source_tier_rank(existing.source_type):
                unique[existing_idx] = source
            continue

        if fp:
            fingerprint_to_index[fp] = len(unique)
        unique.append(source)

    return unique


def attach_canonical_urls(sources: list[WebSource]) -> list[WebSource]:
    """Return copies with domain filled if missing (does not mutate frozen sources)."""
    out: list[WebSource] = []
    for source in sources:
        domain = source.domain.strip() or domain_from_url(source.url)
        if domain == source.domain:
            out.append(source)
        else:
            out.append(
                WebSource(
                    title=source.title,
                    url=source.url,
                    domain=domain,
                    snippet=source.snippet,
                    published_at=source.published_at,
                    relevance_score=source.relevance_score,
                    source_type=source.source_type,
                )
            )
    return out
