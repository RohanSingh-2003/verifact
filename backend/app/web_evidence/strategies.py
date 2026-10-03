"""Preferred-source strategies per question type (preferences, not truth rankings)."""

from __future__ import annotations

from dataclasses import dataclass

from app.web_evidence.question_types import QuestionType


@dataclass(frozen=True)
class SourceStrategy:
    question_type: QuestionType
    """Short labels shown in the UI (not domains)."""
    labels: tuple[str, ...]
    """Domains passed to Tavily include_domains on the preferred pass."""
    preferred_domains: tuple[str, ...]
    """Optional secondary domain set for diversity."""
    secondary_domains: tuple[str, ...] = ()
    """Tavily topic hint: general | news."""
    topic: str = "general"
    """If set (and freshness required), limit results to recent days."""
    default_days: int | None = None

    @property
    def preferred_include_domains(self) -> tuple[str, ...]:
        """Domains for Pass 1 (Primary & Authoritative)."""
        seen: set[str] = set()
        ordered: list[str] = []
        for domain in self.preferred_domains:
            key = domain.strip().lower().removeprefix("www.")
            if not key or "." not in key or key in seen:
                continue
            seen.add(key)
            ordered.append(key)
        return tuple(ordered[:8])

    @property
    def secondary_include_domains(self) -> tuple[str, ...]:
        """Domains for Pass 2 (Broader Reputable Sources)."""
        seen: set[str] = set()
        ordered: list[str] = []
        for domain in self.secondary_domains:
            key = domain.strip().lower().removeprefix("www.")
            if not key or "." not in key or key in seen:
                continue
            seen.add(key)
            ordered.append(key)
        return tuple(ordered[:8])

    @property
    def include_domains(self) -> tuple[str, ...]:
        """Default include_domains: primary preferred domains (keeps tests and callers consistent)."""
        return self.preferred_include_domains


_STRATEGIES: dict[QuestionType, SourceStrategy] = {
    QuestionType.GENERAL_FACT: SourceStrategy(
        question_type=QuestionType.GENERAL_FACT,
        labels=("Encyclopaedia Britannica", "Official institutions & archives", "Reference sources"),
        preferred_domains=(
            "britannica.com",
            "loc.gov",
            "si.edu",
            "archives.gov",
            "india.gov.in",
            "gov.uk",
            "whitehouse.gov",
        ),
        secondary_domains=("en.wikipedia.org", "encyclopedia.com"),
    ),
    QuestionType.SCIENCE: SourceStrategy(
        question_type=QuestionType.SCIENCE,
        labels=("NASA / ESA / NOAA", "NIH / CDC / USGS", "Peer-reviewed scientific journals", "University research"),
        preferred_domains=(
            "nasa.gov",
            "nih.gov",
            "cdc.gov",
            "noaa.gov",
            "usgs.gov",
            "esa.int",
            "nature.com",
            "science.org",
        ),
        secondary_domains=("arxiv.org", "mit.edu", "stanford.edu", "sciencedirect.com", "britannica.com"),
    ),
    QuestionType.GOVERNMENT_POLICY: SourceStrategy(
        question_type=QuestionType.GOVERNMENT_POLICY,
        labels=("Official government websites", "Legislative & regulatory portals", "Primary official releases"),
        preferred_domains=(
            "india.gov.in",
            "gov.uk",
            "whitehouse.gov",
            "congress.gov",
            "europa.eu",
            "pib.gov.in",
            "legislation.gov.uk",
        ),
        secondary_domains=("reuters.com", "apnews.com", "bbc.com"),
    ),
    QuestionType.POLITICS: SourceStrategy(
        question_type=QuestionType.POLITICS,
        labels=("Election commissions & parliaments", "Official government sources", "Reuters / AP / BBC"),
        preferred_domains=(
            "eci.gov.in",
            "fec.gov",
            "congress.gov",
            "parliament.uk",
            "reuters.com",
            "apnews.com",
            "bbc.com",
        ),
        secondary_domains=("bbc.co.uk", "npr.org"),
    ),
    QuestionType.CURRENT_EVENT: SourceStrategy(
        question_type=QuestionType.CURRENT_EVENT,
        labels=("Reuters", "Associated Press", "BBC News", "Primary official releases"),
        preferred_domains=("reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "npr.org"),
        secondary_domains=("whitehouse.gov", "gov.uk", "pib.gov.in"),
        topic="news",
        default_days=14,
    ),
    QuestionType.STATISTICS: SourceStrategy(
        question_type=QuestionType.STATISTICS,
        labels=("National statistical agencies (MOSPI/Census)", "World Bank / IMF / OECD / UN", "Official open data"),
        preferred_domains=(
            "mospi.gov.in",
            "rbi.org.in",
            "worldbank.org",
            "imf.org",
            "oecd.org",
            "un.org",
            "census.gov",
            "data.gov",
        ),
        secondary_domains=("ons.gov.uk", "reuters.com", "bloomberg.com"),
    ),
    QuestionType.TECHNOLOGY: SourceStrategy(
        question_type=QuestionType.TECHNOLOGY,
        labels=("Official documentation", "Standards bodies (W3C/IETF)", "Project repositories"),
        preferred_domains=(
            "react.dev",
            "developer.mozilla.org",
            "docs.python.org",
            "nodejs.org",
            "github.com",
            "w3.org",
            "ietf.org",
        ),
        secondary_domains=("arxiv.org", "acm.org", "ieee.org"),
    ),
    QuestionType.HISTORY: SourceStrategy(
        question_type=QuestionType.HISTORY,
        labels=("National archives & records", "Smithsonian & Library of Congress", "UNESCO & Britannica"),
        preferred_domains=(
            "archives.gov",
            "loc.gov",
            "si.edu",
            "unesco.org",
            "britannica.com",
            "nationalarchives.gov.uk",
        ),
        secondary_domains=("en.wikipedia.org", "bbc.com"),
    ),
    QuestionType.MEDICINE_HEALTH: SourceStrategy(
        question_type=QuestionType.MEDICINE_HEALTH,
        labels=("WHO / CDC / FDA", "NIH & PubMed", "NHS & Major medical institutions"),
        preferred_domains=(
            "who.int",
            "nih.gov",
            "cdc.gov",
            "fda.gov",
            "nhs.uk",
            "pubmed.ncbi.nlm.nih.gov",
            "mayoclinic.org",
        ),
        secondary_domains=("nature.com", "sciencedirect.com", "thelancet.com"),
    ),
    QuestionType.SPORTS: SourceStrategy(
        question_type=QuestionType.SPORTS,
        labels=("Official sports federations (ICC / BCCI / FIFA)", "Olympics & Leagues", "Reputable sports coverage"),
        preferred_domains=(
            "icc-cricket.com",
            "bcci.tv",
            "olympics.com",
            "fifa.com",
            "nba.com",
            "nfl.com",
            "premierleague.com",
        ),
        secondary_domains=("reuters.com", "apnews.com", "bbc.com", "espn.com"),
    ),
    QuestionType.BUSINESS_FINANCE: SourceStrategy(
        question_type=QuestionType.BUSINESS_FINANCE,
        labels=("SEC & central bank filings", "World Bank / IMF", "Reuters / Bloomberg / FT / WSJ"),
        preferred_domains=(
            "sec.gov",
            "rbi.org.in",
            "worldbank.org",
            "imf.org",
            "reuters.com",
            "bloomberg.com",
            "ft.com",
            "wsj.com",
        ),
        secondary_domains=("marketwatch.com", "cnbc.com"),
    ),
    QuestionType.ACADEMIC_RESEARCH: SourceStrategy(
        question_type=QuestionType.ACADEMIC_RESEARCH,
        labels=("arXiv & Academic repositories", "ACM / IEEE / Nature / Science", "Peer-reviewed publishers"),
        preferred_domains=(
            "arxiv.org",
            "acm.org",
            "ieee.org",
            "nature.com",
            "science.org",
            "springer.com",
            "sciencedirect.com",
            "pubmed.ncbi.nlm.nih.gov",
        ),
        secondary_domains=("mit.edu", "stanford.edu", "cambridge.org", "ox.ac.uk"),
    ),
    QuestionType.FACT_CHECK: SourceStrategy(
        question_type=QuestionType.FACT_CHECK,
        labels=("Established fact checkers", "Reuters / AP Fact Checks", "Authoritative references"),
        preferred_domains=(
            "snopes.com",
            "politifact.com",
            "factcheck.org",
            "fullfact.org",
            "reuters.com",
            "apnews.com",
        ),
        secondary_domains=("en.wikipedia.org",),
    ),
    QuestionType.OTHER: SourceStrategy(
        question_type=QuestionType.OTHER,
        labels=("General reputable web search",),
        preferred_domains=(),
        secondary_domains=(),
    ),
}


def get_source_strategy(question_type: QuestionType) -> SourceStrategy:
    return _STRATEGIES.get(question_type, _STRATEGIES[QuestionType.OTHER])
