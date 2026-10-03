"""Parallel MetaQA ∥ Web Evidence pipeline: answer-first, isolation, overall_status."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_llm_client
from app.llm.mock import MockLLMClient
from app.main import app
from app.schemas.detect import OverallStatus, RunStatus
from app.services.overall_status import derive_overall_status
from app.web_evidence.types import WebEvidenceResult, WebEvidenceStatus


def _client(fake: MockLLMClient) -> TestClient:
    app.dependency_overrides[get_llm_client] = lambda: fake
    return TestClient(app)


def test_derive_overall_status_matrix() -> None:
    assert (
        derive_overall_status(RunStatus.ANSWER_READY, WebEvidenceStatus.PENDING, has_answer=True)
        == OverallStatus.RUNNING
    )
    assert (
        derive_overall_status(RunStatus.COMPLETED, WebEvidenceStatus.COMPLETED, has_answer=True)
        == OverallStatus.COMPLETED
    )
    assert (
        derive_overall_status(
            RunStatus.VERIFICATION_FAILED, WebEvidenceStatus.COMPLETED, has_answer=True
        )
        == OverallStatus.PARTIAL
    )
    assert (
        derive_overall_status(
            RunStatus.COMPLETED, WebEvidenceStatus.FAILED, has_answer=True
        )
        == OverallStatus.PARTIAL
    )
    assert (
        derive_overall_status(
            RunStatus.MUTATION_GENERATION_FAILED,
            WebEvidenceStatus.UNAVAILABLE,
            has_answer=True,
        )
        == OverallStatus.PARTIAL
    )
    assert (
        derive_overall_status(RunStatus.FAILED, WebEvidenceStatus.FAILED, has_answer=False)
        == OverallStatus.FAILED
    )


def test_answer_returned_before_metaqa_and_web_evidence() -> None:
    client = _client(MockLLMClient(scenario="reliable"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "answer_ready"
        assert body["overall_status"] == "running"
        assert body["base_answer"]["text"]
        assert body["hallucination_score"] is None
        # Web may still be pending on the POST payload (built before background tasks).
        assert body["web_evidence"] is not None

        detail = client.get(f"/api/runs/{body['run_id']}").json()
        assert detail["base_answer"]["text"] == body["base_answer"]["text"]
        assert detail["status"] == "completed"
        assert detail["web_evidence"]["status"] in {"completed", "unavailable", "failed"}
        assert detail["overall_status"] in {"completed", "partial"}
        assert detail["hallucination_score"] is not None
    finally:
        app.dependency_overrides.clear()


def test_metaqa_failure_does_not_stop_web_evidence() -> None:
    client = _client(MockLLMClient(fail_on="mutations"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        body = response.json()
        assert body["base_answer"]["text"]
        detail = client.get(f"/api/runs/{body['run_id']}").json()
        assert detail["status"] == "mutation_generation_failed"
        assert detail["hallucination_score"] is None
        assert detail["base_answer"]["text"] == body["base_answer"]["text"]
        assert detail["web_evidence"] is not None
        assert detail["web_evidence"]["status"] in {"completed", "unavailable", "failed"}
        assert detail["overall_status"] == "partial"
        # No invented MetaQA score on failure.
        assert detail["classification"] is None
    finally:
        app.dependency_overrides.clear()


def test_web_evidence_failure_does_not_stop_metaqa() -> None:
    async def _boom(*_args, **_kwargs):
        raise RuntimeError("forced web evidence crash")

    client = _client(MockLLMClient(scenario="reliable"))
    try:
        with patch("app.api.routes_detect.run_web_evidence", new=AsyncMock(side_effect=_boom)):
            response = client.post(
                "/api/detect", json={"question": "What is the capital of Australia?"}
            )
            assert response.status_code == 200
            run_id = response.json()["run_id"]
            detail = client.get(f"/api/runs/{run_id}").json()
        assert detail["status"] == "completed"
        assert detail["hallucination_score"] is not None
        assert detail["base_answer"]["text"]
        assert detail["web_evidence"]["status"] == "failed"
        assert detail["web_evidence"].get("consistency_score") is None
        assert detail["overall_status"] == "partial"
    finally:
        app.dependency_overrides.clear()


def test_both_verification_failures_keep_answer_and_partial() -> None:
    async def _boom(*_args, **_kwargs):
        raise RuntimeError("forced web evidence crash")

    client = _client(MockLLMClient(fail_on="mutations"))
    try:
        with patch("app.api.routes_detect.run_web_evidence", new=AsyncMock(side_effect=_boom)):
            response = client.post(
                "/api/detect", json={"question": "What is the capital of Australia?"}
            )
            assert response.status_code == 200
            body = response.json()
            detail = client.get(f"/api/runs/{body['run_id']}").json()
        assert detail["base_answer"]["text"] == body["base_answer"]["text"]
        assert detail["status"] == "mutation_generation_failed"
        assert detail["hallucination_score"] is None
        assert detail["web_evidence"]["status"] == "failed"
        assert detail["overall_status"] == "partial"
        summary = detail["verification_summary"]
        assert summary["ready"] is True
        assert summary["relationship"] == "BOTH_UNAVAILABLE"
        assert summary["metaqa_score"] is None
    finally:
        app.dependency_overrides.clear()


def test_parallel_branches_both_invoked() -> None:
    """Both MetaQA and Web Evidence continuations must be invoked for a detect run."""
    client = _client(MockLLMClient(scenario="reliable"))
    started: list[str] = []

    async def track_metaqa(**_kwargs):
        started.append("metaqa")

    async def track_web(**_kwargs):
        started.append("web")

    try:
        with (
            patch("app.api.routes_detect._continue_metaqa_analysis", new=track_metaqa),
            patch("app.api.routes_detect._continue_web_evidence", new=track_web),
        ):
            response = client.post(
                "/api/detect", json={"question": "What is the capital of Australia?"}
            )
            assert response.status_code == 200
            assert response.json()["status"] == "answer_ready"
            assert response.json()["base_answer"]["text"]

        assert started == ["metaqa", "web"] or set(started) == {"metaqa", "web"}
    finally:
        app.dependency_overrides.clear()


def test_verification_summary_partial_cases() -> None:
    from app.metaqa.scoring import Classification
    from app.schemas.web_evidence import WebEvidenceOut
    from app.services.verification_summary import build_verification_summary

    both = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.1,
        threshold=0.5,
        web_evidence=WebEvidenceOut(
            status=WebEvidenceStatus.COMPLETED,
            total_claims=2,
            supported_claims=2,
            consistency_score=1.0,
            consistency_verdict="CONSISTENT",
            consistency_verdict_label="Consistent",
        ),
    )
    assert both["ready"] is True
    assert both["relationship"] == "AGREE"
    assert both["metaqa_score"] == 0.1

    metaqa_only = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.2,
        threshold=0.5,
        web_evidence=WebEvidenceOut(status=WebEvidenceStatus.FAILED, error="search down"),
    )
    assert metaqa_only["relationship"] == "WEB_UNAVAILABLE"
    assert metaqa_only["metaqa_score"] == 0.2
    assert metaqa_only["web_consistency_score"] is None

    web_only = build_verification_summary(
        status=RunStatus.VERIFICATION_FAILED,
        classification=None,
        score=None,
        threshold=0.5,
        web_evidence=WebEvidenceOut(
            status=WebEvidenceStatus.COMPLETED,
            total_claims=1,
            supported_claims=1,
            consistency_score=1.0,
            consistency_verdict="CONSISTENT",
            consistency_verdict_label="Consistent",
        ),
    )
    assert web_only["relationship"] == "METAQA_UNAVAILABLE"
    assert web_only["metaqa_score"] is None

    neither = build_verification_summary(
        status=RunStatus.MUTATION_GENERATION_FAILED,
        classification=None,
        score=None,
        threshold=0.5,
        web_evidence=WebEvidenceOut(status=WebEvidenceStatus.FAILED),
    )
    assert neither["relationship"] == "BOTH_UNAVAILABLE"
    assert neither["metaqa_score"] is None
    assert neither["web_consistency_score"] is None


def test_frontend_polling_helper_continues_when_one_branch_fails() -> None:
    """Mirror frontend analysisStillRunning semantics for documentation/regression."""

    def analysis_still_running(status: str, web_status: str | None) -> bool:
        metaqa_done = status in {
            "completed",
            "mutation_generation_failed",
            "verification_failed",
            "scoring_failed",
            "failed",
        }
        web_done = web_status in {"completed", "unavailable", "failed"}
        return not (metaqa_done and web_done)

    assert analysis_still_running("verification_failed", "searching_web") is True
    assert analysis_still_running("verifying_mutations", "failed") is True
    assert analysis_still_running("verification_failed", "completed") is False
    assert analysis_still_running("completed", "failed") is False
    assert analysis_still_running("completed", "completed") is False


@pytest.mark.asyncio
async def test_claim_searches_run_concurrently() -> None:
    from app.config import Settings
    from app.llm.mock import MockLLMClient
    from app.web_evidence.pipeline import run_web_evidence
    from app.web_search.mock import MockTavilyClient

    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_claims=3,
        web_max_searches=3,
        web_results_per_claim=2,
    )
    search = MockTavilyClient()
    concurrent = {"max": 0, "current": 0}

    original = search.search

    async def tracked_search(*args, **kwargs):
        concurrent["current"] += 1
        concurrent["max"] = max(concurrent["max"], concurrent["current"])
        await asyncio.sleep(0.02)
        try:
            return await original(*args, **kwargs)
        finally:
            concurrent["current"] -= 1

    search.search = tracked_search  # type: ignore[method-assign]
    llm = MockLLMClient(scenario="reliable")
    result = await run_web_evidence(
        llm,
        search,
        question="What is water made of?",
        answer="Water is H2O. It boils at 100 C. Ice floats on water.",
        settings=settings,
    )
    assert isinstance(result, WebEvidenceResult)
    assert result.status == WebEvidenceStatus.COMPLETED
    # With multiple claims, preferred searches should overlap in flight.
    if result.searches_used >= 2:
        assert concurrent["max"] >= 2


@pytest.mark.asyncio
async def test_ollama_concurrency_limiter_bounds_active_requests() -> None:
    from app.llm.ollama import (
        OllamaConcurrencyLimiter,
        get_ollama_call_count,
        get_ollama_semaphore,
        increment_ollama_call_count,
        reset_ollama_call_count,
    )

    reset_ollama_call_count()
    assert get_ollama_call_count() == 0

    sem = OllamaConcurrencyLimiter.get_semaphore(limit=1)
    assert sem is get_ollama_semaphore(limit=1)
    concurrent = {"max": 0, "current": 0}

    async def _worker():
        async with sem:
            increment_ollama_call_count()
            concurrent["current"] += 1
            concurrent["max"] = max(concurrent["max"], concurrent["current"])
            await asyncio.sleep(0.01)
            concurrent["current"] -= 1

    await asyncio.gather(*[_worker() for _ in range(5)])
    assert concurrent["max"] == 1
    assert get_ollama_call_count() == 5


@pytest.mark.asyncio
async def test_web_evidence_max_3_claims_and_timing_instrumentation() -> None:
    from app.config import Settings
    from app.llm.mock import MockLLMClient
    from app.web_evidence.pipeline import run_web_evidence
    from app.web_search.mock import MockTavilyClient

    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_claims=3,
        web_max_searches=3,
        web_results_per_claim=2,
    )
    search = MockTavilyClient()
    llm = MockLLMClient(scenario="reliable")
    long_answer = (
        "Claim one is verifiable. Claim two is another fact. Claim three is a third fact. "
        "Claim four is a fourth fact. Claim five is a fifth fact. Claim six is a sixth fact."
    )
    result = await run_web_evidence(
        llm,
        search,
        question="What are the multiple facts?",
        answer=long_answer,
        settings=settings,
    )
    assert result.status == WebEvidenceStatus.COMPLETED
    assert len(result.claims) <= 3
    assert result.searches_used <= 3

    # Timing metrics must be populated
    assert "web_total_ms" in result.timing_ms
    assert "web_claim_extraction_ms" in result.timing_ms
    assert "web_search_ms" in result.timing_ms
    assert "web_verification_ms" in result.timing_ms
    assert "total_analysis_ms" in result.timing_ms


def test_search_cache_with_question_type() -> None:
    from app.web_search.base import InMemorySearchCache, WebSource

    cache = InMemorySearchCache()
    sample = [
        WebSource(
            title="Test",
            url="https://example.gov",
            domain="example.gov",
            snippet="Official fact.",
        )
    ]
    cache.set(
        "capital of india",
        2,
        sample,
        include_domains=["example.gov"],
        days=None,
        topic="general",
        question_type="GENERAL_FACT",
    )

    hit = cache.get(
        "capital of india",
        2,
        include_domains=["example.gov"],
        days=None,
        topic="general",
        question_type="GENERAL_FACT",
    )
    assert hit is not None
    assert len(hit) == 1
    assert hit[0].url == "https://example.gov"

    # Different question type should miss
    miss = cache.get(
        "capital of india",
        2,
        include_domains=["example.gov"],
        days=None,
        topic="general",
        question_type="SCIENCE",
    )
    assert miss is None


@pytest.mark.asyncio
async def test_partial_metaqa_when_one_mutation_times_out() -> None:
    from app.config import Settings
    from app.llm.base import LLMTimeoutError
    from app.llm.mock import MockLLMClient
    from app.metaqa.detector import BaseAnswer, run_metaqa_analysis

    settings = Settings(llm_mode="mock", synonym_count=2, antonym_count=2)
    fake_llm = MockLLMClient(scenario="reliable")

    # Wrap complete_json to fail on the 2nd verification call
    original_complete_json = fake_llm.complete_json
    call_count = {"verify": 0}

    async def flake_complete_json(*args, **kwargs):
        user_prompt = kwargs.get("user_prompt", "")
        if "Is the statement a consistent" in user_prompt:
            call_count["verify"] += 1
            if call_count["verify"] == 2:
                raise LLMTimeoutError("Simulated timeout on mutation 2")
        return await original_complete_json(*args, **kwargs)

    fake_llm.complete_json = flake_complete_json  # type: ignore[method-assign]

    result = await run_metaqa_analysis(
        fake_llm,
        question="What is the capital of Australia?",
        answer=BaseAnswer(text="Canberra is the capital of Australia.", model="mock-model"),
        settings=settings,
        generator_model="mock-model",
        verifier_model="mock-model",
    )
    # 4 expected, 3 verified -> partial completion, NOT crash!
    assert result.metaqa_completion == "partial"
    assert result.verified_count == 3
    assert result.expected_count == 4
    assert result.hallucination_score is not None

