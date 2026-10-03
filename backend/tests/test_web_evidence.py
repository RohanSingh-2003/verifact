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
    assert any("britannica.com" in d for d in s1.preferred_domains)
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


