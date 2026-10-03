"""Call-count and interpretation regressions for interactive Detect performance."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.llm.mock import MockLLMClient
from app.metaqa.detector import run_detection
from app.metaqa.scoring import Classification
from app.schemas.detect import RunStatus
from app.schemas.web_evidence import WebClaimOut, WebEvidenceOut
from app.services.verification_summary import (
    WebSignal,
    attention_claims_from_web,
    build_verification_summary,
    web_signal_from_evidence,
)
from app.web_evidence.pipeline import run_web_evidence
from app.web_evidence.scoring import WebConsistencyVerdict, consistency_verdict_for
from app.web_evidence.types import EvidenceVerdict, WebEvidenceStatus
from app.web_search.mock import MockTavilyClient


@pytest.mark.asyncio
async def test_metaqa_ollama_call_count_interactive_defaults() -> None:
    """With 3+3 mutations: 1 answer + 1 claims + 1 mutations + 6 verifies = 9."""
    settings = Settings(
        llm_mode="mock",
        synonym_count=3,
        antonym_count=3,
        verify_concurrency=3,
        web_evidence_enabled=False,
    )
    llm = MockLLMClient(scenario="reliable")
    result = await run_detection(llm, question="What is water made of?", settings=settings)
    assert result.hallucination_score is not None
    # MockLLMClient counters: answer via complete_text; mutations+verify via complete_json (claims extracted in 0ms)
    assert llm.verify_calls == 6
    assert llm.claim_calls == 0
    assert llm.mutation_calls == 1


@pytest.mark.asyncio
async def test_web_evidence_uses_at_most_one_search_and_one_batch_verify() -> None:
    settings = Settings(
        llm_mode="mock",
        web_evidence_enabled=True,
        web_max_claims=3,
        web_max_searches=3,
        web_results_per_claim=2,
    )
    answer = (
        "Water is H2O. It freezes at 0 C. Ice is less dense than liquid water."
    )
    llm = MockLLMClient(answer=answer)
    search = MockTavilyClient()
    before_verify = llm.verify_calls
    result = await run_web_evidence(
        llm,
        search,
        question="What is water?",
        answer=answer,
        settings=settings,
    )
    assert result.status is WebEvidenceStatus.COMPLETED
    assert result.searches_used <= 3
    assert len(search.calls) <= 3
    # Prefer one batch verify (or 0 if all short-circuited). Never more than claim count.
    assert llm.verify_calls - before_verify <= max(1, result.total_claims)


def test_score_067_zero_contradictions_is_partially_supported() -> None:
    verdict = consistency_verdict_for(score=0.67, supported=1, contradicted=0, insufficient=2)
    assert verdict is WebConsistencyVerdict.PARTIALLY_SUPPORTED
    web = WebEvidenceOut(
        status=WebEvidenceStatus.COMPLETED,
        total_claims=3,
        supported_claims=1,
        contradicted_claims=0,
        insufficient_claims=2,
        consistency_score=0.67,
        consistency_verdict=verdict.value,
        consistency_verdict_label="Partially supported by evidence",
        claims=[
            WebClaimOut(
                id="c1",
                text="a",
                verdict=EvidenceVerdict.SUPPORTED,
                reason="ok",
            ),
            WebClaimOut(
                id="c2",
                text="b",
                verdict=EvidenceVerdict.INSUFFICIENT_EVIDENCE,
                reason="thin",
            ),
            WebClaimOut(
                id="c3",
                text="c",
                verdict=EvidenceVerdict.INSUFFICIENT_EVIDENCE,
                reason="thin",
            ),
        ],
    )
    signal = web_signal_from_evidence(web)
    assert signal is WebSignal.PARTIALLY_SUPPORTED
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.1,
        threshold=0.5,
        web_evidence=web,
    )
    assert "not treated as hallucination" in summary["web_interpretation"].casefold()
    assert "unreliable" not in summary["web_interpretation"].casefold()
    assert "no contradiction" in summary["web_interpretation"].casefold()
    assert summary["web_label"] == "Partially supported"
    # Attention list must not include insufficient-only claims.
    assert attention_claims_from_web(web) == []


def test_contradicted_claims_are_attention_only() -> None:
    web = WebEvidenceOut(
        status=WebEvidenceStatus.COMPLETED,
        total_claims=2,
        supported_claims=0,
        contradicted_claims=1,
        insufficient_claims=1,
        claims=[
            WebClaimOut(
                id="bad",
                text="wrong",
                verdict=EvidenceVerdict.CONTRADICTED,
                reason="conflict",
            ),
            WebClaimOut(
                id="thin",
                text="maybe",
                verdict=EvidenceVerdict.INSUFFICIENT_EVIDENCE,
                reason="thin",
            ),
        ],
    )
    attention = attention_claims_from_web(web)
    assert len(attention) == 1
    assert attention[0].id == "bad"


@pytest.mark.asyncio
async def test_single_mutation_timeout_does_not_cancel_metaqa() -> None:
    from app.llm.base import LLMTimeoutError
    from app.metaqa.detector import verify_mutations
    from app.metaqa.mutation import GeneratedMutation
    from app.metaqa.scoring import MutationType

    class Flaky(MockLLMClient):
        def __init__(self) -> None:
            super().__init__(scenario="reliable")
            self.n = 0

        async def complete_json(self, **kwargs):  # type: ignore[no-untyped-def]
            self.n += 1
            if self.n == 2:
                raise LLMTimeoutError("timeout")
            return await super().complete_json(**kwargs)

    mutations = [
        GeneratedMutation(
            type=MutationType.SYNONYM,
            original_text="Water is H2O.",
            mutated_text=f"Water consists of H2O variant {i}.",
        )
        for i in range(3)
    ]
    llm = Flaky()
    scored = await verify_mutations(
        llm,
        question="What is water?",
        answer="Water is H2O.",
        mutations=mutations,
        verifier_model="mock",
        concurrency=2,
        max_tokens=64,
    )
    assert len(scored) == 3
    unavailable = sum(1 for item in scored if item.unavailable)
    assert unavailable == 1
    usable = [item for item in scored if not item.unavailable]
    assert len(usable) == 2
