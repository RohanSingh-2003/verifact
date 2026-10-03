"""Lightweight source-type metadata and authoritative retrieval hierarchy.

Metadata only — never proof that the content is truthful.
"""

from __future__ import annotations

import re
from enum import Enum


class SourceType(str, Enum):
    # Tier 1: Primary & Official
    PRIMARY_OFFICIAL = "PRIMARY_OFFICIAL"
    OFFICIAL = "OFFICIAL"  # Backward-compatible alias
    GOVERNMENT = "GOVERNMENT"  # Backward-compatible alias
    # Tier 2: Academic & Research
    ACADEMIC = "ACADEMIC"
    # Tier 3: Reputable News & Fact Check
    REPUTABLE_NEWS = "REPUTABLE_NEWS"
    NEWS = "NEWS"  # Backward-compatible alias
    FACT_CHECK = "FACT_CHECK"
    # Tier 4: Reference & Encyclopedias
    REFERENCE = "REFERENCE"
    # Tier 5: General Web
    GENERAL_WEB = "GENERAL_WEB"
    GENERAL = "GENERAL"  # Backward-compatible alias
    # Tier 6: Low Priority (blogs, marketing, content farms, SEO aggregators)
    LOW_PRIORITY = "LOW_PRIORITY"


_GOVERNMENT_EXACT = frozenset(
    {
        "gov.in",
        "india.gov.in",
        "pib.gov.in",
        "eci.gov.in",
        "mospi.gov.in",
        "rbi.org.in",
        "gov.uk",
        "legislation.gov.uk",
        "parliament.uk",
        "ons.gov.uk",
        "whitehouse.gov",
        "congress.gov",
        "senate.gov",
        "house.gov",
        "usa.gov",
        "europa.eu",
        "fec.gov",
        "sec.gov",
        "census.gov",
        "data.gov",
        "archives.gov",
        "nationalarchives.gov.uk",
        "loc.gov",
    }
)

_OFFICIAL_EXACT = frozenset(
    {
        # Scientific & space agencies
        "nasa.gov",
        "esa.int",
        "noaa.gov",
        "usgs.gov",
        "nist.gov",
        # Health & medical authorities
        "who.int",
        "nih.gov",
        "cdc.gov",
        "fda.gov",
        "nhs.uk",
        # International organizations
        "un.org",
        "imf.org",
        "worldbank.org",
        "oecd.org",
        "unesco.org",
        # Sports leagues & federations
        "fifa.com",
        "icc-cricket.com",
        "bcci.tv",
        "olympics.com",
        "nba.com",
        "nfl.com",
        "premierleague.com",
        # Standards & tech project docs
        "w3.org",
        "ietf.org",
        "iso.org",
        "react.dev",
        "nodejs.org",
        "docs.python.org",
        "developer.mozilla.org",
        "github.com",
        "kubernetes.io",
    }
)

_ACADEMIC_EXACT = frozenset(
    {
        "arxiv.org",
        "nature.com",
        "science.org",
        "pubmed.ncbi.nlm.nih.gov",
        "sciencedirect.com",
        "springer.com",
        "link.springer.com",
        "wiley.com",
        "onlinelibrary.wiley.com",
        "ieee.org",
        "ieeexplore.ieee.org",
        "acm.org",
        "dl.acm.org",
        "cell.com",
        "thelancet.com",
        "nejm.org",
        "pnas.org",
        "cambridge.org",
        "oxfordacademic.com",
        "academic.oup.com",
        "jstor.org",
        "mit.edu",
        "stanford.edu",
        "harvard.edu",
        "ox.ac.uk",
        "cam.ac.uk",
        "berkeley.edu",
        "si.edu",
    }
)

_NEWS_EXACT = frozenset(
    {
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "bbc.co.uk",
        "npr.org",
        "bloomberg.com",
        "ft.com",
        "wsj.com",
        "nytimes.com",
        "theguardian.com",
        "washingtonpost.com",
        "afp.com",
        "espn.com",
        "skysports.com",
        "hindustantimes.com",
        "thehindu.com",
        "indianexpress.com",
    }
)

_REFERENCE_EXACT = frozenset(
    {
        "britannica.com",
        "encyclopedia.com",
        "merriam-webster.com",
        "en.wikipedia.org",
        "wikipedia.org",
        "wikidata.org",
        "nationalgeographic.com",
        "smithsonianmag.com",
        "khanacademy.org",
        "mayoclinic.org",
    }
)

_FACT_CHECK_EXACT = frozenset(
    {
        "snopes.com",
        "politifact.com",
        "factcheck.org",
        "fullfact.org",
        "leadstories.com",
        "checkyourfact.com",
    }
)

_LOW_PRIORITY_EXACT = frozenset(
    {
        # Commercial vendor marketing blogs
        "k2view.com",
        "hubspot.com",
        "zapier.com",
        "marketo.com",
        "salesforce.com",
        # Blogging & user-generated platforms
        "medium.com",
        "substack.com",
        "blogspot.com",
        "wordpress.com",
        "tumblr.com",
        "wixsite.com",
        "weebly.com",
        "hashnode.dev",
        # Content mills & SEO aggregators
        "geeksforgeeks.org",
        "tutorialspoint.com",
        "javatpoint.com",
        "simplilearn.com",
        "buzzfeed.com",
        "boredpanda.com",
        "ehow.com",
        "wikihow.com",
        # Forums & social media
        "quora.com",
        "reddit.com",
        "pinterest.com",
        "facebook.com",
        "twitter.com",
        "x.com",
    }
)

_GOVERNMENT_SUFFIXES = (".gov", ".gov.uk", ".gov.au", ".gov.in", ".mil")
_ACADEMIC_SUFFIXES = (".edu", ".ac.uk", ".ac.in", ".ac.jp", ".ac.za")

_LOW_PRIORITY_HOST_PATTERNS = re.compile(
    r"(^blog\.|^blogs\.|wordpress\.com$|blogspot\.com$|tumblr\.com$|wixsite\.com$|weebly\.com$)",
    re.IGNORECASE,
)
_LOW_PRIORITY_PATH_PATTERNS = re.compile(
    r"(/(blog|blogs|posts|top-10|best-|affiliate)/)",
    re.IGNORECASE,
)


def is_low_priority_domain(domain: str, url: str = "") -> bool:
    """True if domain or url matches known low-priority blog/SEO/marketing sources."""
    host = (domain or "").strip().lower().removeprefix("www.")
    if not host or host == "unknown":
        return False
    if host in _LOW_PRIORITY_EXACT:
        return True
    if any(host.endswith("." + lp) for lp in _LOW_PRIORITY_EXACT):
        return True
    if _LOW_PRIORITY_HOST_PATTERNS.search(host):
        return True
    if url and _LOW_PRIORITY_PATH_PATTERNS.search(url):
        # Do not flag official or academic domains as low-priority just because they have a /blog/ path.
        if (
            host in _OFFICIAL_EXACT
            or host in _GOVERNMENT_EXACT
            or host in _ACADEMIC_EXACT
            or any(host.endswith(s) for s in _GOVERNMENT_SUFFIXES)
            or any(host.endswith(s) for s in _ACADEMIC_SUFFIXES)
        ):
            return False
        return True
    return False


def classify_source_type(domain: str, url: str = "") -> SourceType:
    """Classify a hostname into a source-category label.

    Metadata only — never proof that the content is correct.
    """
    host = (domain or "").strip().lower().removeprefix("www.")
    if not host or host == "unknown":
        return SourceType.GENERAL_WEB

    # Fact-checking and primary official domains take highest precedence.
    if host in _FACT_CHECK_EXACT or any(host.endswith("." + d) for d in _FACT_CHECK_EXACT):
        return SourceType.FACT_CHECK
    if host in _OFFICIAL_EXACT or any(host.endswith("." + d) for d in _OFFICIAL_EXACT):
        return SourceType.OFFICIAL
    if host in _GOVERNMENT_EXACT or any(host.endswith("." + d) for d in _GOVERNMENT_EXACT) or any(host.endswith(suffix) for suffix in _GOVERNMENT_SUFFIXES):
        return SourceType.GOVERNMENT
    if host in _ACADEMIC_EXACT or any(host.endswith("." + d) for d in _ACADEMIC_EXACT) or any(host.endswith(suffix) for suffix in _ACADEMIC_SUFFIXES):
        return SourceType.ACADEMIC

    labels = host.split(".")
    if len(labels) >= 2 and labels[-1] in {"gov", "mil"}:
        return SourceType.GOVERNMENT
    if len(labels) >= 2 and labels[-1] == "edu":
        return SourceType.ACADEMIC
    if len(labels) >= 3 and labels[-2] == "ac" and labels[-1] in {"uk", "in", "za", "jp"}:
        return SourceType.ACADEMIC

    if host in _NEWS_EXACT or any(host.endswith("." + d) for d in _NEWS_EXACT):
        return SourceType.NEWS
    if host in _REFERENCE_EXACT or any(host.endswith("." + d) for d in _REFERENCE_EXACT) or host.endswith(".wikipedia.org"):
        return SourceType.REFERENCE

    # Detect blogs, SEO content farms, marketing pages
    if is_low_priority_domain(host, url):
        return SourceType.LOW_PRIORITY

    return SourceType.GENERAL


def source_tier_rank(source_type: str | SourceType) -> int:
    """Internal tier ranking for retrieval sorting (lower = higher priority).

    Tier 1: Primary & Official (Government, agencies, documentation, sports federations)
    Tier 2: Academic & Research (Peer-reviewed journals, arXiv, universities)
    Tier 3: Reputable News & Fact Check (Reuters, AP, BBC, Snopes)
    Tier 4: Reference (Britannica, encyclopedias, Wikipedia)
    Tier 5: General Web
    Tier 6: Low Priority (random blogs, SEO content farms, vendor marketing)
    """
    raw = source_type.value if isinstance(source_type, SourceType) else str(source_type or "").upper()
    if raw in {"PRIMARY_OFFICIAL", "OFFICIAL", "GOVERNMENT", "PRIMARY"}:
        return 1
    if raw == "ACADEMIC":
        return 2
    if raw in {"REPUTABLE_NEWS", "NEWS", "FACT_CHECK"}:
        return 3
    if raw in {"REFERENCE", "SECONDARY"}:
        return 4
    if raw in {"GENERAL", "GENERAL_WEB"}:
        return 5
    if raw == "LOW_PRIORITY":
        return 6
    return 5


def source_type_label(value: str | SourceType) -> str:
    raw = value.value if isinstance(value, SourceType) else str(value or "").upper()
    if raw in {"PRIMARY_OFFICIAL", "OFFICIAL", "PRIMARY"}:
        return "Official / Primary"
    if raw == "GOVERNMENT":
        return "Government / Official"
    if raw == "ACADEMIC":
        return "Academic"
    if raw in {"REPUTABLE_NEWS", "NEWS"}:
        return "Reputable News"
    if raw in {"SECONDARY", "REFERENCE"}:
        return "Reference"
    if raw == "FACT_CHECK":
        return "Fact check"
    if raw == "LOW_PRIORITY":
        return "Low Priority / Blog"
    return "General Web"


def normalize_source_type_value(value: str | None) -> str:
    raw = (value or "GENERAL_WEB").strip().upper()
    aliases = {
        "PRIMARY": SourceType.OFFICIAL.value,
        "PRIMARY_OFFICIAL": SourceType.PRIMARY_OFFICIAL.value,
        "SECONDARY": SourceType.REFERENCE.value,
        "OFFICIAL": SourceType.OFFICIAL.value,
        "ACADEMIC": SourceType.ACADEMIC.value,
        "GOVERNMENT": SourceType.GOVERNMENT.value,
        "REPUTABLE_NEWS": SourceType.REPUTABLE_NEWS.value,
        "NEWS": SourceType.NEWS.value,
        "REFERENCE": SourceType.REFERENCE.value,
        "FACT_CHECK": SourceType.FACT_CHECK.value,
        "GENERAL_WEB": SourceType.GENERAL_WEB.value,
        "GENERAL": SourceType.GENERAL.value,
        "LOW_PRIORITY": SourceType.LOW_PRIORITY.value,
    }
    return aliases.get(raw, SourceType.GENERAL.value)

