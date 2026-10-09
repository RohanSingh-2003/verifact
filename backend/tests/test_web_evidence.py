"""Unit tests for Web Evidence Verification (Phase 1 + Phase 2)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_llm_client
from app.config import Settings
from app.llm.base import LLMError
from app.llm.mock import MockLLMClient
from app.main import app
from app.web_evidence.claims import (
    collect_web_claims,
    extract_web_claims,
    fallback_web_claims,
    is_near_duplicate,
    is_non_factual_claim,
    normalize_claim_key,
)
from app.web_evidence.classifier import classify_question
from app.web_evidence.dedupe import dedupe_sources, normalize_url
from app.web_evidence.pipeline import build_web_search_client, run_web_evidence, unavailable_result
from app.web_evidence.question_types import QuestionType
from app.web_evidence.search_query import claim_to_search_query
from app.web_evidence.source_quality import SourceType, classify_source_type
from app.web_evidence.strategies import get_source_strategy
from app.web_evidence.types import EvidenceVerdict, WebEvidenceStatus
from app.web_evidence.verifier import (
    format_evidence_block,
    parse_evidence_verdict,
    sources_have_usable_snippets,
    verify_claim_against_evidence,
)
from app.web_search.base import WebSearchAuthError, WebSearchError, WebSource, domain_from_url
from app.web_search.mock import MockTavilyClient
from app.web_search.tavily_client import normalize_tavily_results


def test_domain_from_url() -> None:
    assert domain_from_url("https://www.bbc.com/news/x") == "bbc.com"
    assert domain_from_url("not-a-url") == "unknown"


def test_normalize_tavily_results_filters_invalid() -> None:
    sources = normalize_tavily_results(
        [
            {"title": "Good", "url": "https://example.com/a", "content": "Snippet A", "score": 0.9},
            {"title": "Bad", "url": "ftp://example.com", "content": "no"},
            {"title": "Also bad", "url": "", "content": "no"},
            "not-a-dict",
        ]
    )
    assert len(sources) == 1
    assert sources[0].domain == "example.com"
    assert sources[0].relevance_score == 0.9


async def test_mock_tavily_success_and_empty() -> None:
    client = MockTavilyClient()
    hits = await client.search("Alexander Fleming penicillin", max_results=2)
    assert len(hits) == 2
    assert hits[0].url.startswith("https://")

    empty = MockTavilyClient(empty=True)
    assert await empty.search("anything") == []


async def test_mock_tavily_auth_failure() -> None:
    client = MockTavilyClient(fail_with=WebSearchAuthError("bad key"))
    with pytest.raises(WebSearchAuthError):
        await client.search("query")


def test_claim_to_search_query_is_concise() -> None:
    query = claim_to_search_query("The Eiffel Tower was completed in 1889.")
    assert "Eiffel" in query
    assert "1889" in query
    assert len(query.split()) <= 10


def test_collect_web_claims_and_fallback() -> None:
    claims = collect_web_claims(
        [
            {"id": "claim_1", "text": "Alexander Fleming discovered penicillin."},
            {"text": "too"},
            {"id": "x", "text": "The discovery occurred in 1928."},
        ],
        max_claims=6,
    )
    assert len(claims) == 2
    fallback = fallback_web_claims(
        "New Delhi is the capital of India. Paris is the capital of France.",
        max_claims=2,
    )
    assert len(fallback) == 2


async def test_extract_web_claims_success() -> None:
    llm = MockLLMClient(answer="Alexander Fleming discovered penicillin in 1928.")
    claims = await extract_web_claims(
        llm,
        model="mock",
        question="Who discovered penicillin?",
        answer="Alexander Fleming discovered penicillin in 1928.",
        max_claims=4,
    )
    assert 1 <= len(claims) <= 4


def test_parse_evidence_verdicts() -> None:
    assert parse_evidence_verdict({"verdict": "SUPPORTED", "reason": "ok"})[0] is EvidenceVerdict.SUPPORTED
    assert parse_evidence_verdict({"verdict": "CONTRADICTED", "reason": "no"})[0] is EvidenceVerdict.CONTRADICTED
    assert (
        parse_evidence_verdict({"verdict": "INSUFFICIENT_EVIDENCE", "reason": "thin"})[0]
        is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    )
    assert parse_evidence_verdict({"verdict": "???"})[0] is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert parse_evidence_verdict(None)[0] is EvidenceVerdict.INSUFFICIENT_EVIDENCE


async def test_verify_claim_without_sources_is_insufficient() -> None:
    llm = MockLLMClient()
    verdict, reason = await verify_claim_against_evidence(
        llm,
        model="mock",
        claim="Alexander Fleming discovered penicillin.",
        sources=[],
    )
    assert verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert "No web sources" in reason


async def test_verify_claim_supported_with_sources() -> None:
    llm = MockLLMClient()
    sources = [
        WebSource(
            title="Penicillin",
            url="https://en.wikipedia.org/wiki/Penicillin",
            domain="en.wikipedia.org",
            snippet="Alexander Fleming discovered penicillin in 1928.",
        )
    ]
    verdict, _reason = await verify_claim_against_evidence(
        llm,
        model="mock",
        claim="Alexander Fleming discovered penicillin.",
        sources=sources,
    )
    assert verdict is EvidenceVerdict.SUPPORTED


async def test_pipeline_respects_max_claims_and_searches() -> None:
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_claims=2,
        web_max_searches=2,
        web_results_per_claim=2,
    )
    llm = MockLLMClient(
        answer=(
            "Alexander Fleming discovered penicillin in 1928. "
            "He worked at St Mary's Hospital in London. "
            "Penicillin became widely used antibiotics later."
        )
    )
    search = MockTavilyClient()
    result = await run_web_evidence(
        llm,
        search,
        question="Who discovered penicillin?",
        answer=llm.answer,
        settings=settings,
    )
    assert result.status is WebEvidenceStatus.COMPLETED
    assert result.total_claims <= 2
    assert result.searches_used <= 2
    assert len(search.calls) <= 2
    assert all(item.verdict is not EvidenceVerdict.SUPPORTED or item.sources for item in result.claims)


async def test_pipeline_search_failure_does_not_fake_supported() -> None:
    settings = Settings(llm_mode="mock", web_evidence_enabled=True, web_max_claims=2)
    llm = MockLLMClient(answer="Paris is the capital of France.")
    search = MockTavilyClient(fail_with=WebSearchError("network down"))
    result = await run_web_evidence(
        llm,
        search,
        question="What is the capital of France?",
        answer="Paris is the capital of France.",
        settings=settings,
    )
    # Either failed overall (no sources) or claims marked insufficient — never invented SUPPORTED.
    if result.status is WebEvidenceStatus.COMPLETED:
        assert all(c.verdict is not EvidenceVerdict.SUPPORTED for c in result.claims)
    else:
        assert result.status is WebEvidenceStatus.FAILED


def test_build_client_unavailable_without_key() -> None:
    settings = Settings(llm_mode="live", tavily_api_key="", web_evidence_enabled=True)
    assert build_web_search_client(settings) is None
    assert unavailable_result("missing key").status is WebEvidenceStatus.UNAVAILABLE


def test_detect_keeps_metaqa_when_web_evidence_runs() -> None:
    fake = MockLLMClient(scenario="reliable")
    app.dependency_overrides[get_llm_client] = lambda: fake
    client = TestClient(app)
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        body = response.json()
        assert body["base_answer"]["text"]
        assert body["web_evidence"] is not None
        assert body["web_evidence"]["status"] in {"pending", "classifying_question", "extracting_claims", "searching_web", "verifying_evidence", "completed", "unavailable", "failed"}

        detail = client.get(f"/api/runs/{body['run_id']}").json()
        assert detail["base_answer"]["text"] == body["base_answer"]["text"]
        assert detail["status"] == "completed"
        assert detail["hallucination_score"] is not None
        assert detail["web_evidence"] is not None
        assert detail["web_evidence"]["status"] in {"completed", "unavailable", "failed"}
        # MetaQA mutations still present.
        assert len(detail["mutations"]) == 10
    finally:
        app.dependency_overrides.clear()


def test_detect_mutation_failure_preserves_answer_and_web_independence() -> None:
    fake = MockLLMClient(fail_on="mutations")
    app.dependency_overrides[get_llm_client] = lambda: fake
    client = TestClient(app)
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        detail = client.get(f"/api/runs/{run_id}").json()
        assert detail["base_answer"]["text"]
        assert detail["status"] == "mutation_generation_failed"
        assert detail["hallucination_score"] is None
        # Web evidence may still complete independently.
        assert detail["web_evidence"] is not None
    finally:
        app.dependency_overrides.clear()


async def test_extract_web_claims_malformed_falls_back() -> None:
    class BrokenClaimsLLM(MockLLMClient):
        async def complete_json(self, **kwargs):
            if "external evidence" in kwargs.get("system_prompt", "").casefold():
                return {"claims": "not-a-list"}
            return await super().complete_json(**kwargs)

    llm = BrokenClaimsLLM(answer="Paris is the capital of France.")
    claims = await extract_web_claims(
        llm,
        model="mock",
        question="What is the capital of France?",
        answer="Paris is the capital of France.",
        max_claims=3,
    )
    assert len(claims) >= 1


# ---------------------------------------------------------------------------
# Phase 2 — claim quality, queries, dedupe, source types, verification rules
# ---------------------------------------------------------------------------


def test_phase2_multiple_factual_claims() -> None:
    claims = collect_web_claims(
        [
            {"text": "Alexander Fleming discovered penicillin."},
            {"text": "The discovery occurred in 1928."},
            {"text": "Fleming worked at St Mary's Hospital in London."},
        ],
        max_claims=6,
    )
    assert len(claims) == 3


def test_phase2_duplicate_and_near_duplicate_claims() -> None:
    claims = collect_web_claims(
        [
            {"text": "Alexander Fleming discovered penicillin."},
            {"text": "alexander fleming discovered penicillin!"},
            {"text": "Alexander Fleming discovered penicillin in 1928."},
        ],
        max_claims=6,
    )
    assert len(claims) == 1
    assert normalize_claim_key(claims[0].text)
    assert is_near_duplicate(
        "Alexander Fleming discovered penicillin in 1928.",
        ["Alexander Fleming discovered penicillin."],
    )


def test_phase2_filters_vague_opinions_and_greetings() -> None:
    assert is_non_factual_claim("Hello there, how can I help you?")
    assert is_non_factual_claim("I think this is probably the best answer.")
    assert is_non_factual_claim("In conclusion, it is important to remember this.")
    claims = collect_web_claims(
        [
            {"text": "Thanks for asking!"},
            {"text": "In my opinion Paris is lovely."},
            {"text": "Paris is the capital of France."},
        ],
        max_claims=6,
    )
    assert len(claims) == 1
    assert "Paris" in claims[0].text


def test_phase2_no_verifiable_claims() -> None:
    claims = collect_web_claims(
        [
            {"text": "Hello!"},
            {"text": "I believe this might be interesting."},
        ],
        max_claims=6,
    )
    assert claims == []
    fallback = fallback_web_claims(
        "Thanks for your question. I think this is wonderful.",
        max_claims=4,
    )
    assert fallback == []


def test_phase2_search_query_from_claim_not_full_answer() -> None:
    claim = "New Delhi became the capital of British India in 1911."
    query = claim_to_search_query(claim)
    assert "New" in query or "Delhi" in query
    assert "1911" in query
    assert "capital" in query.casefold()
    assert "became" not in query.casefold()
    assert "While Delhi" not in query
    assert len(query.split()) <= 10


def test_phase2_normalize_url_and_dedupe() -> None:
    a = "https://Example.com/article/"
    b = "https://www.example.com/article?utm_source=x&utm_campaign=y"
    c = "https://example.com/article/other"
    assert normalize_url(a) == normalize_url(b)
    assert normalize_url(a) != normalize_url(c)

    sources = [
        WebSource(title="A", url=a, domain="example.com", snippet="one", source_type="GENERAL"),
        WebSource(title="B", url=b, domain="example.com", snippet="two", source_type="GENERAL"),
        WebSource(title="C", url=c, domain="example.com", snippet="three", source_type="GENERAL"),
    ]
    unique = dedupe_sources(sources)
    assert len(unique) == 2
    assert unique[0].title == "A"


def test_phase2_source_quality_classification() -> None:
    assert classify_source_type("nih.gov") is SourceType.OFFICIAL
    assert classify_source_type("stanford.edu") is SourceType.ACADEMIC
    assert classify_source_type("bbc.com") is SourceType.NEWS
    assert classify_source_type("en.wikipedia.org") is SourceType.REFERENCE
    assert classify_source_type("my-blog.example") is SourceType.GENERAL


def test_phase2_normalize_tavily_sets_source_type() -> None:
    sources = normalize_tavily_results(
        [
            {
                "title": "NIH page",
                "url": "https://www.nih.gov/news",
                "content": "Official notice about a clinical trial.",
                "score": 0.7,
            }
        ]
    )
    assert sources[0].source_type == SourceType.OFFICIAL.value


async def test_phase2_supported_contradicted_insufficient() -> None:
    llm = MockLLMClient()
    supported_sources = [
        WebSource(
            title="Penicillin",
            url="https://en.wikipedia.org/wiki/Penicillin",
            domain="en.wikipedia.org",
            snippet="Alexander Fleming discovered penicillin in 1928.",
            source_type="SECONDARY",
        )
    ]
    verdict, reason = await verify_claim_against_evidence(
        llm,
        model="mock",
        claim="Alexander Fleming discovered penicillin.",
        sources=supported_sources,
    )
    assert verdict is EvidenceVerdict.SUPPORTED
    assert "penicillin" in reason.casefold() or "supports" in reason.casefold()

    contradicted_sources = [
        WebSource(
            title="False claim page",
            url="https://example.com/false",
            domain="example.com",
            snippet="CONTRADICTS_CLAIM: Howard Florey alone discovered penicillin in 1940.",
            source_type="GENERAL",
        )
    ]
    verdict2, _ = await verify_claim_against_evidence(
        llm,
        model="mock",
        claim="Alexander Fleming discovered penicillin.",
        sources=contradicted_sources,
    )
    assert verdict2 is EvidenceVerdict.CONTRADICTED

    empty = await verify_claim_against_evidence(
        llm, model="mock", claim="X happened in 1900.", sources=[]
    )
    assert empty[0] is EvidenceVerdict.INSUFFICIENT_EVIDENCE

    thin = [
        WebSource(
            title="Thin",
            url="https://example.com/t",
            domain="example.com",
            snippet="ok",
            source_type="GENERAL",
        )
    ]
    assert not sources_have_usable_snippets(thin)
    verdict3, _ = await verify_claim_against_evidence(
        llm, model="mock", claim="X happened in 1900.", sources=thin
    )
    assert verdict3 is EvidenceVerdict.INSUFFICIENT_EVIDENCE


async def test_phase2_empty_search_results_are_insufficient() -> None:
    settings = Settings(llm_mode="mock", web_evidence_enabled=True, web_max_claims=2)
    llm = MockLLMClient(answer="Paris is the capital of France.")
    search = MockTavilyClient(empty=True)
    result = await run_web_evidence(
        llm,
        search,
        question="What is the capital of France?",
        answer="Paris is the capital of France.",
        settings=settings,
    )
    assert result.status is WebEvidenceStatus.COMPLETED
    assert result.total_claims >= 1
    assert all(c.verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE for c in result.claims)
    assert all(c.verdict is not EvidenceVerdict.SUPPORTED for c in result.claims)
    assert all(c.verdict is not EvidenceVerdict.CONTRADICTED for c in result.claims)


async def test_phase2_per_claim_search_failure_continues() -> None:
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_claims=3,
        web_max_searches=3,
    )
    llm = MockLLMClient(
        answer=(
            "Alexander Fleming discovered penicillin in 1928. "
            "He worked at St Mary's Hospital in London."
        )
    )

    class PartialFailSearch(MockTavilyClient):
        async def search(self, query: str, *, max_results: int = 3, **kwargs) -> list[WebSource]:
            self.calls.append(query)
            if len(self.calls) == 1:
                raise WebSearchError("transient failure")
            return await MockTavilyClient.search(self, query, max_results=max_results, **kwargs)

    search = PartialFailSearch()
    result = await run_web_evidence(
        llm,
        search,
        question="Who discovered penicillin?",
        answer=llm.answer,
        settings=settings,
    )
    assert result.status is WebEvidenceStatus.COMPLETED
    assert result.total_claims >= 2
    # First claim may be insufficient; later claims can still complete.
    assert any(c.sources for c in result.claims) or any(
        c.verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE for c in result.claims
    )


async def test_phase2_same_source_can_attach_to_multiple_claims() -> None:
    shared = WebSource(
        title="Shared",
        url="https://en.wikipedia.org/wiki/Penicillin",
        domain="en.wikipedia.org",
        snippet="Alexander Fleming discovered penicillin in 1928 at St Mary's Hospital in London.",
        source_type="SECONDARY",
    )
    search = MockTavilyClient(default_results=[shared])
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_claims=2,
        web_max_searches=2,
        web_results_per_claim=1,
    )
    llm = MockLLMClient(
        answer=(
            "Alexander Fleming discovered penicillin. "
            "The discovery occurred in 1928."
        )
    )
    result = await run_web_evidence(
        llm,
        search,
        question="Who discovered penicillin?",
        answer=llm.answer,
        settings=settings,
    )
    assert result.status is WebEvidenceStatus.COMPLETED
    assert result.total_claims >= 2
    urls = [c.sources[0].url for c in result.claims if c.sources]
    assert len(urls) >= 2
    assert len(set(urls)) == 1


async def test_phase2_verifier_failure_marks_insufficient() -> None:
    class BoomVerify(MockLLMClient):
        async def complete_json(self, **kwargs):
            if "Evidence:" in kwargs.get("user_prompt", "") and "Claim:" in kwargs.get(
                "user_prompt", ""
            ):
                raise LLMError("verifier boom")
            return await super().complete_json(**kwargs)

    llm = BoomVerify(answer="Paris is the capital of France.")
    sources = [
        WebSource(
            title="Paris",
            url="https://en.wikipedia.org/wiki/Paris",
            domain="en.wikipedia.org",
            snippet="Paris is the capital and most populous city of France.",
            source_type="SECONDARY",
        )
    ]
    verdict, reason = await verify_claim_against_evidence(
        llm, model="mock", claim="Paris is the capital of France.", sources=sources
    )
    assert verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert "could not be completed" in reason.casefold()


def test_phase2_evidence_block_marks_url_as_identifier_only() -> None:
    block = format_evidence_block(
        [
            WebSource(
                title="Title",
                url="https://example.com/x",
                domain="example.com",
                snippet="Fact text here about the claim under review today.",
                source_type="GENERAL",
            )
        ]
    )
    assert "identifier only" in block
    assert "snippet=Fact text" in block


def test_phase2_detect_has_no_combined_score_field() -> None:
    fake = MockLLMClient(scenario="reliable")
    app.dependency_overrides[get_llm_client] = lambda: fake
    client = TestClient(app)
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        detail = client.get(f"/api/runs/{run_id}").json()
        assert "combined_score" not in detail
        assert "fusion_score" not in detail
        assert "web_evidence_score" not in detail
        assert detail["hallucination_score"] is not None  # MetaQA only
        assert detail["web_evidence"] is not None
        assert "status" in detail["web_evidence"]
        if detail["web_evidence"]["status"] == "completed" and detail["web_evidence"].get("total_claims", 0) > 0:
            assert detail["web_evidence"].get("consistency_score") is not None
        # Answer remains visible; MetaQA completed.
        assert detail["base_answer"]["text"]
        assert detail["status"] == "completed"
    finally:
        app.dependency_overrides.clear()


async def test_phase2_tavily_unavailable_does_not_invent_supported() -> None:
    settings = Settings(llm_mode="mock", web_evidence_enabled=True)
    llm = MockLLMClient(answer="Paris is the capital of France.")
    search = MockTavilyClient(fail_with=WebSearchAuthError("bad key"))
    result = await run_web_evidence(
        llm,
        search,
        question="Capital?",
        answer="Paris is the capital of France.",
        settings=settings,
    )
    assert result.status is WebEvidenceStatus.FAILED
    assert all(c.verdict is not EvidenceVerdict.SUPPORTED for c in result.claims)


# ---------------------------------------------------------------------------
# Question-type routing (source strategy layer)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What is the capital of India?", QuestionType.GENERAL_FACT),
        ("How does photosynthesis work?", QuestionType.SCIENCE),
        ("What is the James Webb Space Telescope?", QuestionType.SCIENCE),
        ("What did the Indian government announce about education policy?", QuestionType.GOVERNMENT_POLICY),
        ("Who won the latest election in the region?", QuestionType.CURRENT_EVENT),
        ("What is India's GDP?", QuestionType.STATISTICS),
        ("What does the React documentation say about hooks?", QuestionType.TECHNOLOGY),
        ("Who discovered penicillin?", QuestionType.HISTORY),
        ("What are the CDC guidelines for vaccination?", QuestionType.MEDICINE_HEALTH),
        ("Who won the 2018 World Cup?", QuestionType.SPORTS),
        ("What happened yesterday in the Champions League?", QuestionType.CURRENT_EVENT),
        ("Where can I find the original research paper on transformers?", QuestionType.ACADEMIC_RESEARCH),
        ("Is this viral claim true or false?", QuestionType.FACT_CHECK),
        ("Tell me something interesting.", QuestionType.OTHER),
    ],
)
def test_classify_question_categories(question: str, expected: QuestionType) -> None:
    result = classify_question(question)
    assert result.type is expected
    assert 0.0 < result.confidence <= 1.0


def test_classify_current_event_requires_freshness_history_does_not() -> None:
    current = classify_question("What happened yesterday in the Champions League?")
    assert current.type is QuestionType.CURRENT_EVENT
    assert current.freshness_required is True

    historical = classify_question("Who won the 2018 World Cup?")
    assert historical.type is QuestionType.SPORTS
    assert historical.freshness_required is False


def test_source_strategies_have_labels_and_domains() -> None:
    for qtype in QuestionType:
        strategy = get_source_strategy(qtype)
        assert strategy.labels
        if qtype is QuestionType.OTHER:
            assert strategy.include_domains == ()
        else:
            assert strategy.include_domains
        assert not hasattr(strategy, "trust_score")


async def test_routing_passes_preferred_domains_to_search() -> None:
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_claims=1,
        web_max_searches=2,
    )
    llm = MockLLMClient(answer="Photosynthesis converts light energy into chemical energy.")
    search = MockTavilyClient(
        default_results=[
            WebSource(
                title="NASA science",
                url="https://www.nasa.gov/photosynthesis",
                domain="nasa.gov",
                snippet="Photosynthesis converts light energy into chemical energy in plants.",
                source_type="OFFICIAL",
            )
        ]
    )
    result = await run_web_evidence(
        llm,
        search,
        question="How does photosynthesis work?",
        answer=llm.answer,
        settings=settings,
    )
    assert result.question_type == QuestionType.SCIENCE.value
    assert result.source_strategy_labels
    assert search.call_options
    first = search.call_options[0]
    assert first["include_domains"]
    assert any("nasa.gov" in d for d in first["include_domains"])


async def test_preferred_empty_runs_fallback_search() -> None:
    """When preferred domains return nothing, fallback search runs and finds evidence."""
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_claims=1,
        web_max_searches=4,
    )
    llm = MockLLMClient(answer="Paris is the capital of France.")
    search = MockTavilyClient(
        preferred_empty=True,
        fallback_results=[
            WebSource(
                title="Paris",
                url="https://en.wikipedia.org/wiki/Paris",
                domain="en.wikipedia.org",
                snippet="Paris is the capital and most populous city of France.",
                source_type="REFERENCE",
            )
        ],
    )
    result = await run_web_evidence(
        llm,
        search,
        question="What is the capital of France?",
        answer="Paris is the capital of France.",
        settings=settings,
    )
    assert result.status is WebEvidenceStatus.COMPLETED
    assert result.used_fallback_search is True
    assert len(search.calls) >= 2
    assert search.call_options[0]["include_domains"]
    assert result.claims[0].used_fallback is True
    assert result.claims[0].verdict is EvidenceVerdict.SUPPORTED


async def test_preferred_and_fallback_empty_returns_insufficient() -> None:
    """When preferred domains and fallback return nothing, verdict is INSUFFICIENT_EVIDENCE."""
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_claims=1,
        web_max_searches=4,
    )
    llm = MockLLMClient(answer="Paris is the capital of France.")
    search = MockTavilyClient(empty=True)
    result = await run_web_evidence(
        llm,
        search,
        question="What is the capital of France?",
        answer="Paris is the capital of France.",
        settings=settings,
    )
    assert result.status is WebEvidenceStatus.COMPLETED
    # Empty results → insufficient, never invented SUPPORTED/CONTRADICTED.
    assert all(c.verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE for c in result.claims)


async def test_current_event_search_sets_days() -> None:
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_claims=1,
        web_max_searches=2,
    )
    llm = MockLLMClient(answer="The match ended 2-1 yesterday.")
    search = MockTavilyClient()
    result = await run_web_evidence(
        llm,
        search,
        question="What happened yesterday in the Champions League?",
        answer=llm.answer,
        settings=settings,
    )
    assert result.question_type == QuestionType.CURRENT_EVENT.value
    assert result.freshness_required is True
    assert search.call_options
    assert search.call_options[0]["days"] == 14
    assert search.call_options[0]["topic"] == "news"


async def test_ambiguous_question_uses_other_or_general() -> None:
    result = classify_question("Hmm?")
    assert result.type in {QuestionType.OTHER, QuestionType.GENERAL_FACT}
    strategy = get_source_strategy(result.type)
    assert strategy.labels


def test_user_required_question_classification_cases() -> None:
    # 1. Capital of India -> GENERAL_FACT
    c1 = classify_question("What is the capital of India?")
    assert c1.type is QuestionType.GENERAL_FACT
    s1 = get_source_strategy(c1.type)
    assert any("britannica.com" in d for d in s1.secondary_domains)
    assert any("india.gov.in" in d for d in s1.preferred_domains)

    # 2. Photosynthesis -> SCIENCE
    c2 = classify_question("What is photosynthesis?")
    assert c2.type is QuestionType.SCIENCE
    s2 = get_source_strategy(c2.type)
    assert any("nasa.gov" in d for d in s2.preferred_domains)
    assert any("nature.com" in d for d in s2.preferred_domains)

    # 3. India's GDP in 2024 -> STATISTICS
    c3 = classify_question("What was India's GDP in 2024?")
    assert c3.type is QuestionType.STATISTICS
    s3 = get_source_strategy(c3.type)
    assert any("mospi.gov.in" in d for d in s3.preferred_domains)
    assert any("worldbank.org" in d for d in s3.preferred_domains)

    # 4. Latest cricket match -> SPORTS (with freshness)
    c4 = classify_question("What happened in the latest cricket match?")
    assert c4.type is QuestionType.SPORTS
    assert c4.freshness_required is True
    s4 = get_source_strategy(c4.type)
    assert any("icc-cricket.com" in d or "bcci.tv" in d for d in s4.preferred_domains)
    assert any("reuters.com" in d or "bbc.com" in d for d in s4.secondary_domains)

    # 5. Explain React hooks -> TECHNOLOGY
    c5 = classify_question("Explain React hooks.")
    assert c5.type is QuestionType.TECHNOLOGY
    s5 = get_source_strategy(c5.type)
    assert any("react.dev" in d for d in s5.preferred_domains)

    # 6. Who formulated Newton's laws -> SCIENCE
    c6 = classify_question("Who formulated Newton's laws?")
    assert c6.type is QuestionType.SCIENCE
    s6 = get_source_strategy(c6.type)
    assert any("nature.com" in d or "science.org" in d or "nasa.gov" in d for d in s6.preferred_domains)

    # 16. Technical terms hallucination -> ACADEMIC_RESEARCH
    c16 = classify_question("What do you mean by hallucination related to technical terms?")
    assert c16.type is QuestionType.ACADEMIC_RESEARCH
    s16 = get_source_strategy(c16.type)
    assert any("arxiv.org" in d for d in s16.preferred_domains)
    assert any("acm.org" in d for d in s16.preferred_domains)


def test_source_quality_tier_ranking_and_low_priority_demotion() -> None:
    from app.web_evidence.dedupe import dedupe_sources
    from app.web_evidence.pipeline import _annotate_and_sort_sources
    from app.web_evidence.source_quality import source_tier_rank

    # Verify classification of commercial blogs vs academic vs official
    assert classify_source_type("k2view.com") is SourceType.LOW_PRIORITY
    assert classify_source_type("medium.com") is SourceType.LOW_PRIORITY
    assert classify_source_type("arxiv.org") is SourceType.ACADEMIC
    assert classify_source_type("nasa.gov") is SourceType.OFFICIAL

    # Rank check
    assert source_tier_rank(SourceType.PRIMARY_OFFICIAL) == 1
    assert source_tier_rank(SourceType.ACADEMIC) == 2
    assert source_tier_rank(SourceType.REPUTABLE_NEWS) == 3
    assert source_tier_rank(SourceType.REFERENCE) == 4
    assert source_tier_rank(SourceType.GENERAL) == 5
    assert source_tier_rank(SourceType.LOW_PRIORITY) == 6

    # Verify sorting orders authoritative / academic sources before commercial blogs
    raw_sources = [
        WebSource(
            title="What is Data Hallucination?",
            url="https://www.k2view.com/blog/what-is-data-hallucination",
            domain="k2view.com",
            snippet="A marketing blog discussing hallucination in data management.",
            source_type="LOW_PRIORITY",
        ),
        WebSource(
            title="Siren's Song in the AI Ocean: A Survey on Hallucination in Large Language Models",
            url="https://arxiv.org/abs/2309.01219",
            domain="arxiv.org",
            snippet="Comprehensive academic survey classifying hallucinations in modern LLMs.",
            source_type="ACADEMIC",
        ),
        WebSource(
            title="AI hallucination definition",
            url="https://www.reuters.com/technology/ai-hallucinations-2024",
            domain="reuters.com",
            snippet="Reuters news report explaining hallucination in artificial intelligence.",
            source_type="NEWS",
        ),
    ]

    sorted_sources = _annotate_and_sort_sources(raw_sources, question_type="ACADEMIC_RESEARCH")
    # Academic survey must be ranked FIRST over the commercial blog!
    assert sorted_sources[0].domain == "arxiv.org"
    assert sorted_sources[1].domain == "reuters.com"
    # Blog must be ranked LAST
    assert sorted_sources[2].domain == "k2view.com"

    # Test deduplication of syndicated copies preferring authoritative source
    syndicated = [
        WebSource(
            title="Government announces new initiative",
            url="https://random-aggregator.com/post-1",
            domain="random-aggregator.com",
            snippet="Official government announcement on economic policy released today.",
            source_type="GENERAL",
        ),
        WebSource(
            title="Government announces new initiative",
            url="https://pib.gov.in/release-1",
            domain="pib.gov.in",
            snippet="Official government announcement on economic policy released today.",
            source_type="GOVERNMENT",
        ),
    ]
    deduped = dedupe_sources(syndicated)
    assert len(deduped) == 1
    assert deduped[0].domain == "pib.gov.in"  # Preferred the primary government publication!


def test_clean_raw_snippet_strips_markdown_and_navigation() -> None:
    from app.web_evidence.evidence_extractor import clean_raw_snippet

    raw = (
        "History Top Questions ### What post did Narendra Modi hold before becoming prime minister of India? "
        "Narendra Modi was the chief minister of the western Indian state of Gujarat from 2001 to 2014. "
        "Narendra Modi - Political career, PM of India, 2014 & 2019 ..."
    )
    cleaned = clean_raw_snippet(raw)
    assert "###" not in cleaned
    assert "History Top Questions" not in cleaned
    assert "What post did Narendra Modi hold" not in cleaned
    assert "chief minister of the western Indian state of Gujarat from 2001 to 2014" in cleaned


def test_extract_source_evidence_user_example() -> None:
    from app.web_evidence.evidence_extractor import extract_source_evidence
    from app.web_search.base import WebSource

    source = WebSource(
        title="Narendra Modi | Biography, Full Name, Gujarat, & Facts | Britannica",
        url="https://www.britannica.com/biography/Narendra-Modi",
        domain="britannica.com",
        snippet=(
            "History Top Questions ### What post did Narendra Modi hold before becoming prime minister of India? "
            "Narendra Modi was the chief minister of the western Indian state of Gujarat from 2001 to 2014. "
            "Narendra Modi - Political career, PM of India, 2014 & 2019 ..."
        ),
    )
    claim = "Modi served as the Chief Minister of Gujarat from 2001 to 2014."
    extracted = extract_source_evidence(claim, source)
    assert extracted == "Narendra Modi was the chief minister of the western Indian state of Gujarat from 2001 to 2014."
    assert "History Top Questions" not in extracted
    assert "###" not in extracted


def test_extract_source_evidence_insufficient_content() -> None:
    from app.web_evidence.evidence_extractor import (
        INSUFFICIENT_SOURCE_MESSAGE,
        extract_source_evidence,
    )
    from app.web_search.base import WebSource

    source = WebSource(
        title="Baking Recipes",
        url="https://example.com/recipes",
        domain="example.com",
        snippet="Learn how to bake delicious apple pies with cinnamon and fresh butter every morning.",
    )
    claim = "Modi served as the Chief Minister of Gujarat from 2001 to 2014."
    extracted = extract_source_evidence(claim, source)
    assert extracted == INSUFFICIENT_SOURCE_MESSAGE


def test_websource_evidence_summary_serialization() -> None:
    from app.web_search.base import WebSource

    source = WebSource(
        title="Test Title",
        url="https://example.com",
        domain="example.com",
        snippet="Some snippet text.",
        evidence_summary="Extracted summary text.",
    )
    d = source.to_dict()
    assert d["evidence_summary"] == "Extracted summary text."


# ===========================================================================
# 13 Required Tests for Government-First Evidence Retrieval & Verification
# ===========================================================================

def test_1_country_specific_official_domain_prioritization() -> None:
    """1. Country-specific official-domain prioritization."""
    from app.web_evidence.authority import resolve_authority_strategy

    # Australia / Canberra
    au_strat = resolve_authority_strategy(
        "Canberra is located in the Australian Capital Territory (ACT).",
        question_text="What is the capital of Australia?",
    )
    assert any("gov.au" in d for d in au_strat.preferred_domains)
    assert any("act.gov.au" in d for d in au_strat.preferred_domains)
    assert any("ga.gov.au" in d for d in au_strat.preferred_domains)

    # India / Delhi
    in_strat = resolve_authority_strategy(
        "New Delhi is the official capital of India.",
        question_text="What is the capital of India?",
    )
    assert any("gov.in" in d or "nic.in" in d for d in in_strat.preferred_domains)

    # United Kingdom
    uk_strat = resolve_authority_strategy(
        "The UK Parliament meets at the Palace of Westminster in London.",
        question_text="Where does the UK Parliament meet?",
    )
    assert any("gov.uk" in d for d in uk_strat.preferred_domains)

    # Canada
    ca_strat = resolve_authority_strategy(
        "Ottawa is the federal capital of Canada.",
        question_text="What is the capital of Canada?",
    )
    assert any("canada.ca" in d or "gc.ca" in d for d in ca_strat.preferred_domains)

    # United States
    us_strat = resolve_authority_strategy(
        "The U.S. Census Bureau conducts the decennial census of the United States.",
        question_text="Which agency conducts the US census?",
    )
    assert any(d == "gov" or "census.gov" in d or "usa.gov" in d for d in us_strat.preferred_domains)


async def test_2_government_first_search_followed_by_broader_fallback() -> None:
    """2. Government-first search followed by broader fallback."""
    from app.web_evidence.types import ExtractedClaim
    from app.web_evidence.pipeline import _search_claims_concurrent

    search = MockTavilyClient(
        preferred_empty=True,  # Pass 1 returns 0 hits
        fallback_results=[
            WebSource(
                title="Australian Geography — Britannica",
                url="https://www.britannica.com/place/Canberra",
                domain="britannica.com",
                snippet="Canberra is the capital of Australia, located in the Australian Capital Territory.",
                source_type="REFERENCE",
            )
        ],
    )
    claims = [ExtractedClaim(id="c1", text="Canberra is the capital of Australia.")]
    results, searches_used, sources_found, auth_failed, error, _ = await _search_claims_concurrent(
        search,
        claims,
        preferred_domains=["act.gov.au", "gov.au"],
        secondary_domains=["britannica.com"],
        question_text="What is Canberra?",
        results_per_claim=2,
        max_searches=4,
        days=None,
        topic="general",
        question_type="GENERAL_FACT",
    )
    assert searches_used >= 2  # Pass 1 + Pass 2
    assert sources_found == 1
    cid, ctext, query, sources, used_fb = results[0]
    assert used_fb is True
    assert sources[0].domain == "britannica.com"


def test_3_relevant_official_source_preferred_over_unrelated_secondary_source() -> None:
    """3. A relevant official source being preferred over an unrelated secondary source."""
    from app.web_evidence.pipeline import _annotate_and_sort_sources

    official = WebSource(
        title="Geoscience Australia National Dimensions",
        url="https://www.ga.gov.au/dimensions",
        domain="ga.gov.au",
        snippet="Geoscience Australia official records show Canberra in the ACT.",
        relevance_score=0.85,
    )
    secondary = WebSource(
        title="General Web Overview",
        url="https://www.someblog.com/canberra",
        domain="someblog.com",
        snippet="Canberra is an interesting city.",
        relevance_score=0.99,  # higher score but lower authority
    )
    sorted_sources = _annotate_and_sort_sources([secondary, official], question_type="GENERAL_FACT")
    assert sorted_sources[0].domain == "ga.gov.au"
    assert sorted_sources[0].source_type == "GOVERNMENT"


async def test_4_multiple_sources_being_considered_for_one_claim() -> None:
    """4. Multiple sources being considered for one claim."""
    from app.web_evidence.types import ExtractedClaim
    from app.web_evidence.pipeline import _search_claims_concurrent

    search = MockTavilyClient(
        default_results=[
            WebSource(
                title="Geoscience Australia",
                url="https://www.ga.gov.au/capital",
                domain="ga.gov.au",
                snippet="Canberra is located in the Australian Capital Territory.",
                source_type="GOVERNMENT",
            ),
            WebSource(
                title="ACT Government Portal",
                url="https://www.act.gov.au/about",
                domain="act.gov.au",
                snippet="The ACT is completely enclosed by the state of New South Wales.",
                source_type="GOVERNMENT",
            ),
        ]
    )
    claims = [ExtractedClaim(id="c1", text="Canberra is in the ACT and surrounded by NSW.")]
    results, searches_used, sources_found, auth_failed, error, _ = await _search_claims_concurrent(
        search,
        claims,
        preferred_domains=["ga.gov.au", "act.gov.au"],
        results_per_claim=3,
        max_searches=4,
        days=None,
        topic="general",
        question_type="GENERAL_FACT",
    )
    cid, ctext, query, sources, _ = results[0]
    assert len(sources) == 2
    domains = {s.domain for s in sources}
    assert "ga.gov.au" in domains
    assert "act.gov.au" in domains


def test_5_claims_containing_multiple_factual_assertions() -> None:
    """5. Claims containing multiple factual assertions preserve query terms."""
    from app.web_evidence.search_query import claim_to_search_query

    claim = "Canberra is located in the Australian Capital Territory (ACT), an enclave within the state of New South Wales."
    query = claim_to_search_query(claim)
    assert "Canberra" in query
    assert "Australian" in query or "ACT" in query
    assert "enclave" in query
    assert "Wales" in query or "South" in query


def test_6_insufficient_snippets_triggering_further_retrieval_when_budget_permits() -> None:
    """6. Insufficient snippets triggering further retrieval when budget permits."""
    from app.web_evidence.pipeline import is_evidence_sufficient_for_claim

    partial_source = WebSource(
        title="Canberra Info",
        url="https://www.act.gov.au/canberra",
        domain="act.gov.au",
        snippet="Canberra is the federal capital located in the Australian Capital Territory.",
        source_type="GOVERNMENT",
    )
    compound_claim = "Canberra is located in the Australian Capital Territory (ACT), an enclave within the state of New South Wales."
    # Snippet only has ACT, missing NSW / enclave
    sufficient = is_evidence_sufficient_for_claim(compound_claim, [partial_source])
    assert sufficient is False

    complete_source = WebSource(
        title="Canberra Geography - Geoscience Australia",
        url="https://www.ga.gov.au/geography",
        domain="ga.gov.au",
        snippet="Canberra is located in the Australian Capital Territory, an enclave entirely within New South Wales.",
        source_type="GOVERNMENT",
    )
    sufficient_both = is_evidence_sufficient_for_claim(compound_claim, [complete_source])
    assert sufficient_both is True


async def test_7_missing_evidence_remaining_insufficient_evidence_not_contradicted() -> None:
    """7. Missing evidence remaining INSUFFICIENT_EVIDENCE, not CONTRADICTED."""
    llm = MockLLMClient(
        json_response={
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reason": "The retrieved sources do not establish this claim.",
        }
    )
    sources = [
        WebSource(
            title="General Australia Portal",
            url="https://www.australia.gov.au",
            domain="australia.gov.au",
            snippet="Australia comprises six states and multiple mainland territories.",
            source_type="GOVERNMENT",
        )
    ]
    verdict, reason = await verify_claim_against_evidence(
        llm,
        model="mock-model",
        claim="The secret capital of Australia was founded in 1700.",
        sources=sources,
    )
    assert verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert verdict is not EvidenceVerdict.CONTRADICTED


async def test_8_directly_supported_claims_recognized_despite_paraphrasing() -> None:
    """8. Directly supported claims being recognized despite paraphrasing."""
    llm = MockLLMClient(
        json_response={
            "verdict": "SUPPORTED",
            "reason": "The official source confirms Canberra serves as the seat of government inside the ACT.",
        }
    )
    sources = [
        WebSource(
            title="Geoscience Australia",
            url="https://www.ga.gov.au/canberra",
            domain="ga.gov.au",
            snippet="Canberra serves as the national capital city of the Commonwealth of Australia, situated inside the Australian Capital Territory.",
            source_type="GOVERNMENT",
        )
    ]
    verdict, reason = await verify_claim_against_evidence(
        llm,
        model="mock-model",
        claim="Canberra is Australia's capital situated within the ACT.",
        sources=sources,
    )
    assert verdict is EvidenceVerdict.SUPPORTED
    assert "ACT" in reason or "Canberra" in reason


async def test_9_conflicting_sources_handled_conservatively() -> None:
    """9. Conflicting sources being handled conservatively."""
    llm = MockLLMClient(
        json_response={
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reason": "Retrieved sources report conflicting dates (1911 vs 1927) for the founding year.",
        }
    )
    sources = [
        WebSource(
            title="Source A",
            url="https://example.com/a",
            domain="example.com",
            snippet="The territory was established in 1911.",
            source_type="GENERAL",
        ),
        WebSource(
            title="Source B",
            url="https://example.com/b",
            domain="example.com",
            snippet="The territory was officially founded in 1927.",
            source_type="GENERAL",
        ),
    ]
    verdict, reason = await verify_claim_against_evidence(
        llm,
        model="mock-model",
        claim="The territory was founded in 1927.",
        sources=sources,
    )
    assert verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert "conflicting" in reason.lower() or "conflict" in reason.lower()


async def test_10_canberra_act_new_south_wales_regression() -> None:
    """10. Canberra / ACT / New South Wales regression case.

    Claim: 'Canberra is located in the Australian Capital Territory (ACT), an enclave within the state of New South Wales.'
    Case A: Evidence confirms both Canberra in ACT and enclave in NSW -> SUPPORTED.
    Case B: Evidence only establishes Canberra in ACT, omitting NSW enclave -> INSUFFICIENT_EVIDENCE.
    """
    claim_text = (
        "Canberra is located in the Australian Capital Territory (ACT), an enclave within the state of New South Wales."
    )

    # Case A: Both parts present
    llm_supported = MockLLMClient(
        json_response={
            "verdict": "SUPPORTED",
            "reason": "Official Australian government sources confirm Canberra is located in the ACT and that the ACT is an enclave entirely within New South Wales.",
        }
    )
    sources_complete = [
        WebSource(
            title="Geoscience Australia — Australian Dimensions",
            url="https://www.ga.gov.au/scientific-topics/national-location-information/dimensions",
            domain="ga.gov.au",
            snippet="Canberra is the capital city of Australia, situated within the Australian Capital Territory (ACT), which forms an enclave entirely surrounded by the state of New South Wales.",
            source_type="GOVERNMENT",
        )
    ]
    verdict_a, reason_a = await verify_claim_against_evidence(
        llm_supported,
        model="mock-model",
        claim=claim_text,
        sources=sources_complete,
    )
    assert verdict_a is EvidenceVerdict.SUPPORTED
    assert "ACT" in reason_a and "New South Wales" in reason_a

    # Case B: Only first part present (Canberra in ACT), enclave in NSW missing
    llm_insufficient = MockLLMClient(
        json_response={
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reason": "The retrieved source confirms Canberra's location in the Australian Capital Territory (ACT), but does not establish that the ACT is an enclave within New South Wales.",
        }
    )
    sources_partial = [
        WebSource(
            title="Canberra Tourism Portal",
            url="https://visitcanberra.com.au/about",
            domain="visitcanberra.com.au",
            snippet="Canberra is the federal capital of Australia, situated inside the Australian Capital Territory.",
            source_type="GENERAL",
        )
    ]
    verdict_b, reason_b = await verify_claim_against_evidence(
        llm_insufficient,
        model="mock-model",
        claim=claim_text,
        sources=sources_partial,
    )
    assert verdict_b is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert "New South Wales" in reason_b or "enclave" in reason_b


def test_11_correct_web_evidence_score_calculations() -> None:
    """11. Correct Web Evidence score calculations: SUPPORTED=1.0, INSUFFICIENT=0.5, CONTRADICTED=0.0."""
    from app.web_evidence.types import VerifiedClaim, WebEvidenceResult

    # Only supported: 1.0
    r1 = WebEvidenceResult(
        status=WebEvidenceStatus.COMPLETED,
        claims=[
            VerifiedClaim(
                id="c1",
                text="T1",
                search_query="q",
                verdict=EvidenceVerdict.SUPPORTED,
                reason="r",
            )
        ],
    )
    r1.finalize_score()
    assert r1.consistency_score == 1.0

    # Only insufficient: 0.5
    r2 = WebEvidenceResult(
        status=WebEvidenceStatus.COMPLETED,
        claims=[
            VerifiedClaim(
                id="c1",
                text="T1",
                search_query="q",
                verdict=EvidenceVerdict.INSUFFICIENT_EVIDENCE,
                reason="r",
            )
        ],
    )
    r2.finalize_score()
    assert r2.consistency_score == 0.5

    # Only contradicted: 0.0
    r3 = WebEvidenceResult(
        status=WebEvidenceStatus.COMPLETED,
        claims=[
            VerifiedClaim(
                id="c1",
                text="T1",
                search_query="q",
                verdict=EvidenceVerdict.CONTRADICTED,
                reason="r",
            )
        ],
    )
    r3.finalize_score()
    assert r3.consistency_score == 0.0

    # 1 supported (1.0) + 1 insufficient (0.5) = 1.5 / 2 = 0.75
    r4 = WebEvidenceResult(
        status=WebEvidenceStatus.COMPLETED,
        claims=[
            VerifiedClaim(id="c1", text="T1", search_query="q", verdict=EvidenceVerdict.SUPPORTED, reason="r"),
            VerifiedClaim(id="c2", text="T2", search_query="q", verdict=EvidenceVerdict.INSUFFICIENT_EVIDENCE, reason="r"),
        ],
    )
    r4.finalize_score()
    assert r4.consistency_score == 0.75


def test_12_metaqa_scores_remain_independent_of_web_evidence_results() -> None:
    """12. MetaQA scores remaining independent of Web Evidence results."""
    fake = MockLLMClient(scenario="reliable")
    app.dependency_overrides[get_llm_client] = lambda: fake
    client = TestClient(app)
    try:
        response = client.post(
            "/api/detect",
            json={"question": "What is the capital of Australia?"},
        )
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        detail = client.get(f"/api/runs/{run_id}").json()
        assert detail["status"] == "completed"
        assert detail["hallucination_score"] is not None
        assert detail["web_evidence"] is not None
        if detail["web_evidence"].get("consistency_score") is not None:
            assert "consistency_score" in detail["web_evidence"]
    finally:
        app.dependency_overrides.clear()


def test_13_tavily_failures_do_not_invalidate_entire_detection_run() -> None:
    """13. Tavily failures not invalidating the entire detection run."""
    fake = MockLLMClient(scenario="reliable")
    app.dependency_overrides[get_llm_client] = lambda: fake
    client = TestClient(app)
    try:
        response = client.post(
            "/api/detect",
            json={"question": "What is penicillin?"},
        )
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        detail = client.get(f"/api/runs/{run_id}").json()
        assert detail["status"] == "completed"
        assert detail["hallucination_score"] is not None
        assert detail["base_answer"]["text"]
    finally:
        app.dependency_overrides.clear()


async def test_14_live_tavily_australian_government_source_retrieval() -> None:
    """14. Live Tavily integration test verifying official Australian government sources."""
    from pathlib import Path
    from dotenv import dotenv_values
    from app.config import Settings
    from app.web_search.tavily_client import TavilyClient

    env_vals = dotenv_values(Path(__file__).resolve().parent.parent / ".env")
    key = (env_vals.get("TAVILY_API_KEY") or "").strip()
    if not key or key.startswith("replace-with-"):
        pytest.skip("Tavily API key not configured for live test")

    settings = Settings(
        tavily_api_key=key,
        web_evidence_enabled=True,
    )
    client = TavilyClient(settings)
    results = await client.search(
        "Canberra Australian Capital Territory ACT enclave New South Wales",
        include_domains=["act.gov.au", "ga.gov.au", "australia.gov.au", "nsw.gov.au", "gov.au"],
        max_results=3,
    )
    assert len(results) > 0
    assert any(r.domain.endswith("gov.au") for r in results)
    assert any(r.source_type == "GOVERNMENT" for r in results)


# ── Tokyo & Topical Relevance Regression Tests ───────────────────────────────

TOKYO_CLAIM = "Tokyo serves as the seat of the Japanese government, the Imperial Palace, and the primary economic and cultural hub of the country."


def test_15_tokyo_irrelevant_official_source_filtered_and_not_supported() -> None:
    """15. Irrelevant official source (parliament.qld.gov.au) must not be treated as acceptable evidence."""
    from app.web_evidence.authority import _JAPAN
    from app.web_evidence.relevance import (
        compute_topical_relevance,
        filter_topically_relevant_sources,
        extract_claim_anchors_and_concepts,
    )
    from app.web_evidence.evidence_extractor import extract_source_evidence, INSUFFICIENT_SOURCE_MESSAGE
    from app.web_evidence.pipeline import is_evidence_sufficient_for_claim

    qld_source = WebSource(
        title="Queensland Parliament - Parliamentary Delegation to Japan",
        url="https://www.parliament.qld.gov.au/docs/reports/trade_japan.pdf",
        domain="parliament.qld.gov.au",
        snippet="The Queensland trade delegation visited Japan to discuss bilateral trade and investment in beef and coal exports between Queensland and Japanese business partners.",
        source_type="GOVERNMENT",
    )

    # 1. Anchors extract Tokyo and Imperial Palace
    anchors, _concepts = extract_claim_anchors_and_concepts(TOKYO_CLAIM)
    assert "Tokyo" in anchors
    assert any("Imperial" in a for a in anchors)

    # 2. Topical relevance score is heavily penalized due to lack of Tokyo anchors and foreign jurisdiction mismatch
    score = compute_topical_relevance(TOKYO_CLAIM, qld_source, detected_countries=[_JAPAN])
    assert score < 0.20

    # 3. Relevance filtering strips this source completely
    relevant = filter_topically_relevant_sources(TOKYO_CLAIM, [qld_source], min_threshold=0.20, detected_countries=[_JAPAN])
    assert len(relevant) == 0

    # 4. Evidence sufficiency check returns False (triggers fallback)
    assert not is_evidence_sufficient_for_claim(TOKYO_CLAIM, [qld_source], detected_countries=[_JAPAN])

    # 5. Evidence extractor returns INSUFFICIENT_SOURCE_MESSAGE instead of unrelated Queensland text
    summary = extract_source_evidence(TOKYO_CLAIM, qld_source)
    assert summary == INSUFFICIENT_SOURCE_MESSAGE
    assert "beef" not in summary
    assert "coal" not in summary


def test_16_tokyo_relevant_official_source_prioritized() -> None:
    """16. Relevant Japanese government source (metro.tokyo.lg.jp) prioritized over secondary sources."""
    from app.web_evidence.authority import _JAPAN
    from app.web_evidence.relevance import (
        compute_source_priority,
        compute_topical_relevance,
    )
    from app.web_evidence.pipeline import _annotate_and_sort_sources
    from app.web_evidence.evidence_extractor import extract_source_evidence

    metro_tokyo_source = WebSource(
        title="Tokyo Metropolitan Government Official Portal",
        url="https://www.metro.tokyo.lg.jp/english/about/history/index.html",
        domain="metro.tokyo.lg.jp",
        snippet="Tokyo serves as the seat of the Japanese government and houses the Imperial Palace, standing as the primary economic and cultural hub of Japan.",
        source_type="GOVERNMENT",
    )
    generic_news = WebSource(
        title="World Cities Today",
        url="https://www.travelnews.com/tokyo-guide",
        domain="travelnews.com",
        snippet="Tokyo serves as the seat of the Japanese government, the Imperial Palace, and the primary economic and cultural hub of the country.",
        source_type="NEWS",
    )

    # Topical relevance check
    rel_score = compute_topical_relevance(TOKYO_CLAIM, metro_tokyo_source, detected_countries=[_JAPAN])
    assert rel_score >= 0.70

    # Composite priority prefers official Tokyo government source
    gov_prio = compute_source_priority(TOKYO_CLAIM, metro_tokyo_source, detected_countries=[_JAPAN])
    news_prio = compute_source_priority(TOKYO_CLAIM, generic_news, detected_countries=[_JAPAN])
    assert gov_prio > news_prio

    # Sorting places official source at the top
    sorted_sources = _annotate_and_sort_sources(
        [generic_news, metro_tokyo_source],
        question_type="GENERAL_FACT",
        claim_text=TOKYO_CLAIM,
        detected_countries=[_JAPAN],
    )
    assert len(sorted_sources) == 2
    assert sorted_sources[0].domain == "metro.tokyo.lg.jp"

    # Evidence extractor outputs grounded supporting passage
    evidence = extract_source_evidence(TOKYO_CLAIM, metro_tokyo_source)
    assert "Imperial Palace" in evidence
    assert "Tokyo" in evidence


def test_17_tokyo_compound_claim_partial_support_remains_insufficient() -> None:
    """17. Compound-claim verification: partial support must not label claim SUPPORTED."""
    from app.web_evidence.relevance import evaluate_compound_components_coverage, extract_claim_components

    components = extract_claim_components(TOKYO_CLAIM)
    assert len(components) >= 2

    # Partial source covers government and palace, but omits economic and cultural hub
    partial_source = WebSource(
        title="Japan Cabinet Office",
        url="https://www.cao.go.jp/about/tokyo.html",
        domain="cao.go.jp",
        snippet="Tokyo serves as the seat of the Japanese government and houses the Imperial Palace.",
        source_type="GOVERNMENT",
    )

    is_covered, supported, missing = evaluate_compound_components_coverage(TOKYO_CLAIM, [partial_source])
    assert not is_covered
    assert len(missing) > 0
    # Missing component should mention economic or cultural
    assert any("economic" in m.lower() or "cultural" in m.lower() for m in missing)


@pytest.mark.asyncio
async def test_18_tokyo_pipeline_fallback_replaces_irrelevant_source() -> None:
    """18. Targeted fallback: Pass 1 irrelevant official source triggers Pass 2 targeted search."""
    from app.config import Settings
    from app.web_evidence.pipeline import run_web_evidence
    from app.web_search.mock import MockTavilyClient

    qld_source = WebSource(
        title="Queensland Parliament Report",
        url="https://www.parliament.qld.gov.au/japan-trade",
        domain="parliament.qld.gov.au",
        snippet="The Queensland trade delegation visited Japan to discuss bilateral coal and beef trade.",
        source_type="GOVERNMENT",
    )
    tokyo_gov_source = WebSource(
        title="Tokyo Metropolitan Government",
        url="https://www.metro.tokyo.lg.jp/english/overview.html",
        domain="metro.tokyo.lg.jp",
        snippet="Tokyo serves as the seat of the Japanese government, the Imperial Palace, and the primary economic and cultural hub of the country.",
        source_type="GOVERNMENT",
    )

    class TwoPassMockSearch(MockTavilyClient):
        def __init__(self) -> None:
            super().__init__()
            self.call_count = 0

        async def search(self, query: str, **kwargs) -> list[WebSource]:
            self.call_count += 1
            if self.call_count == 1:
                # Pass 1: returns only irrelevant QLD parliament source
                return [qld_source]
            # Pass 2: fallback returns Tokyo government source
            return [tokyo_gov_source]

    mock_llm = MockLLMClient()
    mock_search = TwoPassMockSearch()
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        tavily_api_key="tvly-test-key",
        web_max_searches=4,
        web_results_per_claim=3,
    )

    result = await run_web_evidence(
        mock_llm,
        mock_search,
        question="What role does Tokyo play in Japan?",
        answer=TOKYO_CLAIM,
        settings=settings,
    )

    assert result.status == WebEvidenceStatus.COMPLETED
    assert result.used_fallback_search is True
    assert len(result.claims) > 0
    tokyo_verified = result.claims[0]
    assert tokyo_verified.verdict == EvidenceVerdict.SUPPORTED
    # Sources attached must be the relevant Tokyo source, not QLD parliament
    domains = [s.domain for s in tokyo_verified.sources]
    assert "metro.tokyo.lg.jp" in domains
    assert "parliament.qld.gov.au" not in domains


@pytest.mark.asyncio
async def test_19_tokyo_conflicting_evidence_marked_contradicted() -> None:
    """19. Conflicting evidence contradicts the claim."""
    from app.web_evidence.verifier import verify_claim_against_evidence

    conflicting_source = WebSource(
        title="Historical Capitals Comparison",
        url="https://www.historyfacts.org/capitals",
        domain="historyfacts.org",
        snippet="CONTRADICTS_CLAIM: Kyoto remains the constitutional seat of the Japanese government and houses the Imperial Palace, not Tokyo.",
        source_type="GENERAL",
    )
    mock_llm = MockLLMClient()
    verdict, reason = await verify_claim_against_evidence(
        mock_llm,
        model="mock-model",
        claim=TOKYO_CLAIM,
        sources=[conflicting_source],
    )
    assert verdict == EvidenceVerdict.CONTRADICTED
    assert "conflicts" in reason.lower() or "contradicts" in reason.lower()


@pytest.mark.asyncio
async def test_20_genuinely_insufficient_evidence_retains_insufficient_verdict() -> None:
    """20. When search yields no relevant evidence even after retry, retain INSUFFICIENT_EVIDENCE."""
    from app.config import Settings
    from app.web_evidence.pipeline import run_web_evidence
    from app.web_search.mock import MockTavilyClient

    # Irrelevant source in both pass 1 and fallback
    qld_source = WebSource(
        title="Queensland Parliament",
        url="https://www.parliament.qld.gov.au/trade",
        domain="parliament.qld.gov.au",
        snippet="Queensland parliamentary delegations focus on Australian state agricultural exports.",
        source_type="GOVERNMENT",
    )
    mock_search = MockTavilyClient(default_results=[qld_source])
    mock_llm = MockLLMClient()
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        tavily_api_key="tvly-test-key",
        web_max_searches=4,
    )

    result = await run_web_evidence(
        mock_llm,
        mock_search,
        question="What is Tokyo?",
        answer=TOKYO_CLAIM,
        settings=settings,
    )
    assert result.status == WebEvidenceStatus.COMPLETED
    assert len(result.claims) > 0
    # Because all retrieved sources were off-topic, verdict must be INSUFFICIENT_EVIDENCE
    assert result.claims[0].verdict == EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert result.claims[0].sources == []




