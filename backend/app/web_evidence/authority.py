"""Authority-aware source selection and domain resolution.

Prioritizes official government portals, national mapping agencies, statistical bodies,
and authoritative public institutions by country and domain before falling back
to reputable secondary sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.web_evidence.question_types import QuestionType
from app.web_evidence.strategies import SourceStrategy, get_source_strategy


# ---------------------------------------------------------------------------
# Country detection patterns and authoritative domains
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CountryAuthority:
    country_code: str
    country_name: str
    pattern: re.Pattern
    primary_domains: tuple[str, ...]
    geographic_domains: tuple[str, ...] = ()
    legal_domains: tuple[str, ...] = ()
    statistical_domains: tuple[str, ...] = ()
    health_domains: tuple[str, ...] = ()
    space_domains: tuple[str, ...] = ()
    label: str = ""


_AUSTRALIA = CountryAuthority(
    country_code="AU",
    country_name="Australia",
    pattern=re.compile(
        r"\b(australia|australian|canberra|act\b|australian capital territory|"
        r"new south wales|nsw\b|sydney|melbourne|victoria|vic\b|queensland|qld\b|"
        r"brisbane|perth|western australia|wa\b|south australia|sa\b|adelaide|"
        r"tasmania|tas\b|hobart|darwin|northern territory|nt\b|"
        r"geoscience australia|parliament house canberra)\b",
        re.IGNORECASE,
    ),
    primary_domains=(
        "gov.au",
        "act.gov.au",
        "nsw.gov.au",
        "ga.gov.au",
        "australia.gov.au",
        "abs.gov.au",
        "legislation.gov.au",
        "directory.gov.au",
    ),
    geographic_domains=("ga.gov.au", "act.gov.au", "nsw.gov.au", "australia.gov.au", "gov.au"),
    legal_domains=("legislation.gov.au", "fedcourt.gov.au", "hcourt.gov.au", "gov.au"),
    statistical_domains=("abs.gov.au", "aihw.gov.au", "gov.au"),
    health_domains=("health.gov.au", "aihw.gov.au", "gov.au"),
    space_domains=("space.gov.au", "ga.gov.au", "gov.au"),
    label="Australian Government & Official Portals (gov.au, act.gov.au, ga.gov.au)",
)

_INDIA = CountryAuthority(
    country_code="IN",
    country_name="India",
    pattern=re.compile(
        r"\b(india|indian|delhi|new delhi|mumbai|lok sabha|rajya sabha|isro|rbi|"
        r"pib\b|niti aayog|modi|aadhaar|bharat|upsc|eci\b|supreme court of india|"
        r"survey of india|mospi)\b",
        re.IGNORECASE,
    ),
    primary_domains=(
        "gov.in",
        "nic.in",
        "india.gov.in",
        "pib.gov.in",
        "mospi.gov.in",
        "isro.gov.in",
        "eci.gov.in",
        "rbi.org.in",
    ),
    geographic_domains=("surveyofindia.gov.in", "india.gov.in", "gov.in", "nic.in"),
    legal_domains=("indiacode.nic.in", "sci.gov.in", "lawmin.gov.in", "nic.in"),
    statistical_domains=("mospi.gov.in", "rbi.org.in", "censusindia.gov.in", "gov.in"),
    health_domains=("mohfw.gov.in", "icmr.gov.in", "gov.in"),
    space_domains=("isro.gov.in", "gov.in"),
    label="Government of India & National Portals (gov.in, nic.in, pib.gov.in)",
)

_UNITED_STATES = CountryAuthority(
    country_code="US",
    country_name="United States",
    pattern=re.compile(
        r"\b(united states|usa\b|u\.s\.|u\.s\.a\.|america|american|washington d\.c\.|"
        r"white house|congress|capitol hill|nasa|cdc\b|fbi\b|fda\b|sec\b|irs\b|"
        r"census bureau|usgs\b|national archives|library of congress)\b",
        re.IGNORECASE,
    ),
    primary_domains=(
        "gov",
        "usa.gov",
        "loc.gov",
        "census.gov",
        "archives.gov",
        "whitehouse.gov",
        "congress.gov",
        "usgs.gov",
    ),
    geographic_domains=("usgs.gov", "census.gov", "usa.gov", "loc.gov", "gov"),
    legal_domains=("congress.gov", "supremecourt.gov", "justice.gov", "gov"),
    statistical_domains=("census.gov", "bls.gov", "bea.gov", "data.gov", "gov"),
    health_domains=("cdc.gov", "nih.gov", "fda.gov", "hhs.gov", "gov"),
    space_domains=("nasa.gov", "noaa.gov", "gov"),
    label="U.S. Official Government (gov, usa.gov, loc.gov, usgs.gov)",
)

_UNITED_KINGDOM = CountryAuthority(
    country_code="UK",
    country_name="United Kingdom",
    pattern=re.compile(
        r"\b(united kingdom|uk\b|u\.k\.|britain|british|england|scotland|wales|"
        r"northern ireland|london|westminster|downing street|house of commons|"
        r"house of lords|parliament\.uk|national archives uk|nhs\b|ordnance survey)\b",
        re.IGNORECASE,
    ),
    primary_domains=(
        "gov.uk",
        "legislation.gov.uk",
        "parliament.uk",
        "ons.gov.uk",
        "nationalarchives.gov.uk",
    ),
    geographic_domains=("ordnancesurvey.co.uk", "gov.uk", "nationalarchives.gov.uk"),
    legal_domains=("legislation.gov.uk", "parliament.uk", "supremecourt.uk", "gov.uk"),
    statistical_domains=("ons.gov.uk", "gov.uk"),
    health_domains=("nhs.uk", "gov.uk", "nice.org.uk"),
    space_domains=("gov.uk", "esa.int"),
    label="UK Government & Official Portals (gov.uk, legislation.gov.uk, parliament.uk)",
)

_CANADA = CountryAuthority(
    country_code="CA",
    country_name="Canada",
    pattern=re.compile(
        r"\b(canada|canadian|ottawa|ontario|quebec|british columbia|alberta|"
        r"toronto|montreal|vancouver|parliament of canada|statcan|"
        r"statistics canada|natural resources canada)\b",
        re.IGNORECASE,
    ),
    primary_domains=(
        "canada.ca",
        "gc.ca",
        "statcan.gc.ca",
        "parl.ca",
        "nrcan.gc.ca",
    ),
    geographic_domains=("nrcan.gc.ca", "canada.ca", "gc.ca", "statcan.gc.ca"),
    legal_domains=("laws-lois.justice.gc.ca", "justice.gc.ca", "scc-csc.ca", "canada.ca"),
    statistical_domains=("statcan.gc.ca", "canada.ca"),
    health_domains=("canada.ca", "gc.ca"),
    space_domains=("asc-csa.gc.ca", "canada.ca"),
    label="Government of Canada (canada.ca, gc.ca, statcan.gc.ca)",
)

_EUROPEAN_UNION = CountryAuthority(
    country_code="EU",
    country_name="European Union",
    pattern=re.compile(
        r"\b(european union|eu\b|brussels|european commission|european parliament|"
        r"european central bank|ecb\b|eurozone)\b",
        re.IGNORECASE,
    ),
    primary_domains=("europa.eu", "ec.europa.eu", "europarl.europa.eu", "ecb.europa.eu"),
    geographic_domains=("europa.eu",),
    legal_domains=("eur-lex.europa.eu", "curia.europa.eu", "europa.eu"),
    statistical_domains=("ec.europa.eu/eurostat", "europa.eu"),
    health_domains=("ema.europa.eu", "ecdc.europa.eu", "europa.eu"),
    space_domains=("esa.int", "europa.eu"),
    label="European Union Official Portals (europa.eu)",
)

_JAPAN = CountryAuthority(
    country_code="JP",
    country_name="Japan",
    pattern=re.compile(
        r"\b(japan|japanese|tokyo|kyoto|osaka|diet\b|imperial palace|shinjuku|"
        r"tokyo metropolitan government|kunaicho|gsi\.go\.jp|gsi\b|mofa\b|mext\b|"
        r"emperor of japan|prime minister of japan|national diet)\b",
        re.IGNORECASE,
    ),
    primary_domains=(
        "go.jp",
        "metro.tokyo.lg.jp",
        "japan.go.jp",
        "kunaicho.go.jp",
        "mofa.go.jp",
        "cas.go.jp",
        "stat.go.jp",
        "gsi.go.jp",
        "lg.jp",
    ),
    geographic_domains=("metro.tokyo.lg.jp", "gsi.go.jp", "japan.go.jp", "go.jp"),
    legal_domains=("japaneselawtranslation.go.jp", "courts.go.jp", "diet.go.jp", "go.jp"),
    statistical_domains=("stat.go.jp", "stat.go.jp/data", "go.jp"),
    health_domains=("mhlw.go.jp", "go.jp"),
    space_domains=("jaxa.jp", "go.jp"),
    label="Government of Japan & Tokyo Metropolitan Government (go.jp, metro.tokyo.lg.jp, japan.go.jp)",
)

_ALL_COUNTRIES: tuple[CountryAuthority, ...] = (
    _AUSTRALIA,
    _INDIA,
    _UNITED_STATES,
    _UNITED_KINGDOM,
    _CANADA,
    _EUROPEAN_UNION,
    _JAPAN,
)

# Topic cue regexes
_GEOGRAPHY_CUES = re.compile(
    r"\b(capital|enclave|exclave|territory|border|borders|boundary|boundaries|"
    r"geography|geographic|located in|location|coordinates|elevation|map|mapping|"
    r"province|state of|surrounded by|peninsula|island|archipelago)\b",
    re.IGNORECASE,
)
_LEGAL_CUES = re.compile(
    r"\b(law|laws|legislation|act of parliament|statute|statutes|constitution|"
    r"constitutional|amendment|court|ruling|treaty|legal|regulation|regulations)\b",
    re.IGNORECASE,
)
_STATISTICS_CUES = re.compile(
    r"\b(population|census|gdp|inflation|unemployment|statistic|statistics|"
    r"demographic|per capita|rate of|survey)\b",
    re.IGNORECASE,
)
_HEALTH_CUES = re.compile(
    r"\b(health|vaccine|vaccines|disease|virus|infection|medical|hospital|"
    r"mortality|clinical|treatment|who\b|cdc\b|fda\b|nhs\b)\b",
    re.IGNORECASE,
)
_SPACE_CUES = re.compile(
    r"\b(space|orbit|satellite|satellites|mars|moon|rocket|astronaut|cosmonaut|"
    r"spacecraft|telescope|isro\b|nasa\b|esa\b)\b",
    re.IGNORECASE,
)

# Standard secondary domains for Pass 2 fallback (reputable reference & news, never primary)
_STANDARD_SECONDARY_DOMAINS: tuple[str, ...] = (
    "britannica.com",
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "en.wikipedia.org",
)


def detect_countries(text: str) -> list[CountryAuthority]:
    """Identify which countries or jurisdictions are explicitly mentioned in text."""
    matches: list[CountryAuthority] = []
    for ca in _ALL_COUNTRIES:
        if ca.pattern.search(text):
            matches.append(ca)
    return matches


def resolve_authority_strategy(
    claim_text: str,
    question_text: str = "",
    base_type: QuestionType | None = None,
) -> SourceStrategy:
    """Resolve an authority-aware source strategy tailored to the claim and query.

    Prioritizes official government domains (e.g. gov.au, gov.in, gov, gov.uk, canada.ca)
    and specific official bodies (geography, law, stats, health, space) for Pass 1,
    while placing Britannica and news in secondary domains for Pass 2.
    """
    combined_text = f"{claim_text} {question_text}".strip()
    detected = detect_countries(combined_text)

    is_geo = bool(_GEOGRAPHY_CUES.search(combined_text))
    is_legal = bool(_LEGAL_CUES.search(combined_text))
    is_stats = bool(_STATISTICS_CUES.search(combined_text))
    is_health = bool(_HEALTH_CUES.search(combined_text))
    is_space = bool(_SPACE_CUES.search(combined_text))

    if detected:
        primary_domains: list[str] = []
        labels: list[str] = []

        for ca in detected:
            labels.append(ca.label or f"{ca.country_name} Official Portals")
            # Select topical domains if matched
            if is_geo and ca.geographic_domains:
                for d in ca.geographic_domains:
                    if d not in primary_domains:
                        primary_domains.append(d)
            if is_legal and ca.legal_domains:
                for d in ca.legal_domains:
                    if d not in primary_domains:
                        primary_domains.append(d)
            if is_stats and ca.statistical_domains:
                for d in ca.statistical_domains:
                    if d not in primary_domains:
                        primary_domains.append(d)
            if is_health and ca.health_domains:
                for d in ca.health_domains:
                    if d not in primary_domains:
                        primary_domains.append(d)
            if is_space and ca.space_domains:
                for d in ca.space_domains:
                    if d not in primary_domains:
                        primary_domains.append(d)

            # Append primary domains
            for d in ca.primary_domains:
                if d not in primary_domains:
                    primary_domains.append(d)

        # Build secondary domains
        sec_domains = list(_STANDARD_SECONDARY_DOMAINS)
        effective_type = base_type or QuestionType.GENERAL_FACT

        return SourceStrategy(
            question_type=effective_type,
            labels=tuple(labels),
            preferred_domains=tuple(primary_domains[:8]),
            secondary_domains=tuple(sec_domains[:8]),
        )

    # No country detected: fall back to base strategy for question type
    effective_type = base_type or QuestionType.GENERAL_FACT
    base_strategy = get_source_strategy(effective_type)
    return base_strategy
