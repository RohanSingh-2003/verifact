from __future__ import annotations

import pytest

from app.config import Settings
from app.llm.mock import MockLLMClient
from app.web_evidence.pipeline import run_web_evidence
from app.web_evidence.relevance import evaluate_source_relevance
from app.web_evidence.scoring import compute_consistency_score
from app.web_evidence.types import (
    EvidenceVerdict,
    VerifiedClaim,
    WebEvidenceResult,
    WebEvidenceStatus,
)
from app.web_evidence.verifier import verify_claim_against_evidence
from app.web_search.base import WebSearchAuthError, WebSource
from app.web_search.mock import MockTavilyClient


@pytest.mark.asyncio
async def test_regression_relevant_official_government_page_supports_claim() -> None:
    """1. A relevant official government page correctly supports a claim."""
    gov_source = WebSource(
        title="Apollo 11 Mission Overview - NASA",
        url="https://www.nasa.gov/mission_pages/apollo/apollo-11.html",
        domain="nasa.gov",
        snippet="On July 20, 1969, Neil Armstrong and Buzz Aldrin landed the Apollo 11 Lunar Module on the Moon.",
        source_type="GOVERNMENT",
        relevance_score=0.92,
    )
    answer_text = "NASA's Apollo 11 landed on the Moon in July 1969."
    llm = MockLLMClient(answer=answer_text)
    search = MockTavilyClient(default_results=[gov_source])
    settings = Settings(llm_mode="mock", web_evidence_enabled=True)

    result = await run_web_evidence(
        llm,
        search,
        question="When did Apollo 11 land on the Moon?",
        answer=answer_text,
        settings=settings,
    )
    assert result.status == WebEvidenceStatus.COMPLETED
    assert len(result.claims) >= 1
    claim = result.claims[0]
    assert claim.verdict == EvidenceVerdict.SUPPORTED
    assert len(claim.sources) >= 1
    # Check official domain and tier rationale
    assert claim.sources[0].domain == "nasa.gov"
    assert claim.sources[0].source_type in ("GOVERNMENT", "PRIMARY")
    assert claim.sources[0].quality_rationale is not None
    assert "government" in claim.sources[0].quality_rationale.lower()


@pytest.mark.asyncio
async def test_regression_relevant_britannica_reference_supports_claim() -> None:
    """2. A relevant Britannica or authoritative reference page supports a claim."""
    ref_source = WebSource(
        title="French Revolution - Britannica",
        url="https://www.britannica.com/event/French-Revolution",
        domain="britannica.com",
        snippet="The French Revolution began in 1789 with the storming of the Bastille in Paris.",
        source_type="REFERENCE",
        relevance_score=0.95,
    )
    answer_text = "The French Revolution began in 1789."
    llm = MockLLMClient(answer=answer_text)
    search = MockTavilyClient(default_results=[ref_source])
    settings = Settings(llm_mode="mock", web_evidence_enabled=True)

    result = await run_web_evidence(
        llm,
        search,
        question="When did the French Revolution begin?",
        answer=answer_text,
        settings=settings,
    )
    assert result.status == WebEvidenceStatus.COMPLETED
    assert len(result.claims) >= 1
    claim = result.claims[0]
    assert claim.verdict == EvidenceVerdict.SUPPORTED
    assert claim.sources[0].domain == "britannica.com"
    assert "reference" in (claim.sources[0].quality_rationale or "").lower() or claim.sources[0].source_type == "REFERENCE"


def test_regression_top_ranked_but_irrelevant_page_rejected() -> None:
    """3. A top-ranked search result with high score but completely irrelevant content is rejected."""
    # High score from search engine, but content is recipe/unrelated
    high_scoring_irrelevant = WebSource(
        title="Delicious French Pastry Recipes for Home Bakers",
        url="https://bakingblog.com/french-pastries",
        domain="bakingblog.com",
        snippet="Learn how to bake croissants and eclairs with our authentic French baking guide and butter techniques.",
        relevance_score=0.98,  # deceptively high
    )
    claim_text = "The French Revolution began in 1789 with the storming of the Bastille."
    is_rel, _score, reason, _qual = evaluate_source_relevance(
        claim_text,
        high_scoring_irrelevant,
        min_threshold=0.25,
    )
    assert not is_rel
    assert "proposition" in reason.lower() or "missing" in reason.lower() or "off-topic" in reason.lower() or "concepts" in reason.lower() or "mismatch" in reason.lower() or "not found" in reason.lower()


def test_regression_same_entity_different_fact_rejected() -> None:
    """4. A page mentioning the same entity but discussing an unrelated fact is rejected."""
    claim_text = "Albert Einstein received the Nobel Prize in Physics in 1921 for his explanation of the photoelectric effect."
    # Source mentions Einstein, but discusses his violin playing and childhood hobbies
    same_entity_diff_fact = WebSource(
        title="Albert Einstein's Musical Life - Einstein Archives",
        url="https://archives.org/einstein-violin",
        domain="archives.org",
        snippet="Albert Einstein loved playing Mozart sonatas on his violin named Lina throughout his childhood and later life.",
        relevance_score=0.70,
    )
    is_rel, _score, reason, _qual = evaluate_source_relevance(
        claim_text,
        same_entity_diff_fact,
        min_threshold=0.25,
    )
    assert not is_rel
    # Propositional concepts like 'nobel', 'prize', '1921', 'photoelectric' are missing
    assert "different fact" in reason.lower() or "missing" in reason.lower() or "proposition" in reason.lower()


def test_regression_conflicting_date_or_geographic_scope_rejected() -> None:
    """5. A page with a conflicting date or geographic scope is rejected when that distinction matters."""
    claim_text = "The Summer Olympic Games were held in Tokyo in 2021."
    # Discusses Olympics, but London in 2012
    wrong_year_source = WebSource(
        title="London 2012 Olympic Games Overview",
        url="https://olympics.com/en/olympic-games/london-2012",
        domain="olympics.com",
        snippet="The London 2012 Summer Olympic Games took place across venues in Great Britain in 2012.",
        relevance_score=0.80,
    )
    is_rel, _score, reason, _qual = evaluate_source_relevance(
        claim_text,
        wrong_year_source,
        min_threshold=0.25,
    )
    assert not is_rel
    assert "year" in reason.lower() or "date" in reason.lower() or "scope" in reason.lower() or "tokyo" in reason.lower()


@pytest.mark.asyncio
async def test_regression_query_refinement_discovers_relevant_source() -> None:
    """6. Bounded query refinement discovers a relevant source after an irrelevant initial result."""
    # When searched with initial broad query, return irrelevant page; when refined, return authoritative page
    initial_irrelevant = [
        WebSource(
            title="General World Facts",
            url="https://randomfacts.com/world",
            domain="randomfacts.com",
            snippet="The world has many capital cities and ancient cultures spanning thousands of years.",
            relevance_score=0.10,
        )
    ]
    refined_relevant = [
        WebSource(
            title="Ottawa - Capital of Canada",
            url="https://canada.ca/ottawa-capital",
            domain="canada.ca",
            snippet="Ottawa is the capital city of Canada and the seat of the federal government.",
            source_type="GOVERNMENT",
            relevance_score=0.88,
        )
    ]

    llm = MockLLMClient(answer="Ottawa is the capital of Canada.")
    # Mock search client that returns initial_irrelevant on first query and refined_relevant on refined queries
    search = MockTavilyClient(
        default_results=refined_relevant,
        results_by_query={
            "ottawa capital canada": initial_irrelevant,
        },
    )
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_query_refinements=2,
    )

    result = await run_web_evidence(
        llm,
        search,
        question="What is the capital of Canada?",
        answer="Ottawa is the capital of Canada.",
        settings=settings,
    )
    assert result.status == WebEvidenceStatus.COMPLETED
    assert len(result.claims) >= 1
    # Refinement successfully found the relevant source
    assert result.claims[0].verdict == EvidenceVerdict.SUPPORTED
    assert any("ottawa" in s.snippet.lower() for s in result.claims[0].sources)


@pytest.mark.asyncio
async def test_regression_relevant_sources_failing_to_resolve_yields_insufficient() -> None:
    """7. Case C: Relevant sources exist but do not resolve the claim -> INSUFFICIENT_EVIDENCE."""
    # Source is relevant to James Webb and exoplanet K2-18b, but inconclusive about life
    relevant_inconclusive = [
        WebSource(
            title="JWST Observations of Exoplanet K2-18b - ESA",
            url="https://esa.int/jwst-k2-18b",
            domain="esa.int",
            snippet="INSUFFICIENT_CLAIM: NASA's James Webb Space Telescope detected carbon-bearing molecules on K2-18b, but further observations are required to confirm dimethyl sulfide or biological activity.",
            source_type="GOVERNMENT",
            relevance_score=0.90,
        )
    ]
    llm = MockLLMClient()
    # We call verify_claim_against_evidence where snippet does not prove definitive alien life
    claim_text = "Astronomers have conclusively proven the presence of alien life on exoplanet K2-18b."
    verdict, _rationale = await verify_claim_against_evidence(
        llm,
        model="mock",
        claim=claim_text,
        sources=relevant_inconclusive,
    )
    # The source is relevant to the topic, but evidence is inconclusive / does not prove the claim
    assert verdict == EvidenceVerdict.INSUFFICIENT_EVIDENCE


@pytest.mark.asyncio
async def test_regression_no_relevant_source_yields_not_assessed() -> None:
    """8. Case D: No relevant source found -> NOT_ASSESSED_NO_RELEVANT_SOURCE with no numeric score."""
    llm = MockLLMClient()
    # Search returns empty results
    search = MockTavilyClient(empty=True)
    settings = Settings(llm_mode="mock", web_evidence_enabled=True)

    result = await run_web_evidence(
        llm,
        search,
        question="What is a hyper-obscure non-existent concept?",
        answer="The blorflax index reached 42 in year 3000.",
        settings=settings,
    )
    assert result.status == WebEvidenceStatus.COMPLETED
    assert len(result.claims) >= 1
    for claim in result.claims:
        assert claim.verdict == EvidenceVerdict.NOT_ASSESSED_NO_RELEVANT_SOURCE
        assert claim.sources == []
        assert "no sufficiently relevant" in claim.reason.lower() or "not assessed" in claim.reason.lower()

    # Aggregate score must be None (not 0.0 or 0.5)
    assert result.consistency_score is None
    assert result.unassessed_claims >= 1
    assert result.assessed_claims == 0


@pytest.mark.asyncio
async def test_regression_search_api_failure_distinguished_from_verdict() -> None:
    """9. Search API failure is reported as FAILED status, not a claim-level factual verdict."""
    llm = MockLLMClient()
    # Search client fails with auth error or connection error
    search = MockTavilyClient(fail_with=WebSearchAuthError("Invalid Tavily API key"))
    settings = Settings(llm_mode="mock", web_evidence_enabled=True)

    result = await run_web_evidence(
        llm,
        search,
        question="Where is Mount Fuji?",
        answer="Mount Fuji is in Japan.",
        settings=settings,
    )
    # Result status must be FAILED, not COMPLETED with false verdicts
    assert result.status == WebEvidenceStatus.FAILED
    assert result.error is not None
    assert "Invalid Tavily API key" in result.error
    assert result.consistency_score is None


def test_regression_unassessed_claims_excluded_from_aggregate_score() -> None:
    """10. Unassessed claims are excluded from consistency score numerator and denominator."""
    claims = [
        VerifiedClaim(
            id="c1",
            text="Claim 1: Supported fact",
            search_query="c1 query",
            verdict=EvidenceVerdict.SUPPORTED,  # 1.0
            reason="Verified by primary source",
            sources=[],
        ),
        VerifiedClaim(
            id="c2",
            text="Claim 2: Contradicted fact",
            search_query="c2 query",
            verdict=EvidenceVerdict.CONTRADICTED,  # 0.0
            reason="Contradicted by official records",
            sources=[],
        ),
        VerifiedClaim(
            id="c3",
            text="Claim 3: Unassessed fact with no relevant source",
            search_query="c3 query",
            verdict=EvidenceVerdict.NOT_ASSESSED_NO_RELEVANT_SOURCE,  # MUST BE EXCLUDED
            reason="No relevant sources were found on the web",
            sources=[],
        ),
    ]

    score = compute_consistency_score(claims)
    # Only 2 assessed claims: (1.0 + 0.0) / 2 = 0.5
    # If claim 3 were incorrectly included with 0 or 0.5: (1.0 + 0.0 + 0)/3 = 0.33 or (1.0 + 0.0 + 0.5)/3 = 0.5
    assert score == 0.5

    result = WebEvidenceResult(
        status=WebEvidenceStatus.COMPLETED,
        claims=claims,
        consistency_score=score,
    )
    assert result.total_claims == 3
    assert result.assessed_claims == 2
    assert result.unassessed_claims == 1


def test_regression_no_eligible_claims_produces_null_aggregate_score() -> None:
    """11. When all claims are unassessed, aggregate score is None (not 0.0 or 0.5)."""
    claims = [
        VerifiedClaim(
            id="ca",
            text="Claim A",
            search_query="ca query",
            verdict=EvidenceVerdict.NOT_ASSESSED_NO_RELEVANT_SOURCE,
            reason="No relevant sources found",
            sources=[],
        ),
        VerifiedClaim(
            id="cb",
            text="Claim B",
            search_query="cb query",
            verdict=EvidenceVerdict.NOT_ASSESSED_NO_RELEVANT_SOURCE,
            reason="No relevant sources found",
            sources=[],
        ),
    ]
    score = compute_consistency_score(claims)
    assert score is None

    result = WebEvidenceResult(
        status=WebEvidenceStatus.COMPLETED,
        claims=claims,
        consistency_score=score,
    )
    assert result.consistency_score is None
    assert result.assessed_claims == 0
    assert result.unassessed_claims == 2
    payload = result.to_dict()
    assert payload["consistency_score"] is None
    assert payload["assessed_claims"] == 0
    assert payload["unassessed_claims"] == 2


@pytest.mark.asyncio
async def test_regression_source_urls_and_passages_attached_to_claim() -> None:
    """12. Source URLs, domains, quality rationales, and extracted passages remain attached to claim."""
    source = WebSource(
        title="Kyoto Official Tourism Guide",
        url="https://kyoto.travel/en",
        domain="kyoto.travel",
        snippet="Kyoto was the ancient imperial capital of Japan for over a thousand years.",
        source_type="GOVERNMENT",
        relevance_score=0.91,
        quality_rationale="Official tourism authority of Kyoto",
        relevance_rationale="Directly confirms Kyoto as ancient capital",
        extracted_passage="Kyoto served as Japan's imperial capital from 794 until the Meiji Restoration.",
    )
    llm = MockLLMClient()
    search = MockTavilyClient(default_results=[source])
    settings = Settings(llm_mode="mock", web_evidence_enabled=True)

    result = await run_web_evidence(
        llm,
        search,
        question="What was Kyoto?",
        answer="Kyoto was the ancient capital of Japan.",
        settings=settings,
    )
    assert result.status == WebEvidenceStatus.COMPLETED
    assert len(result.claims) >= 1
    claim = result.claims[0]
    assert len(claim.sources) >= 1
    src = claim.sources[0]
    assert src.url == "https://kyoto.travel/en"
    assert src.domain == "kyoto.travel"
    assert src.quality_rationale is not None
    assert src.relevance_rationale is not None


def test_regression_metaqa_and_gemma_unchanged() -> None:
    """13. MetaQA scoring threshold theta=0.5 and Gemma generator model are unchanged."""
    settings = Settings()
    # Default generator model must be Gemma 4:26B
    assert "gemma" in settings.generator_model.lower()
    # MetaQA decision threshold must be 0.5
    assert settings.threshold == 0.5
    # Web evidence threshold is distinct
    assert settings.web_relevance_threshold == 0.25
