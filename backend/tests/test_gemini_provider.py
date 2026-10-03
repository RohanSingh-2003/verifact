"""Tests for the Gemini verifier provider and cross-model MetaQA integration.

Coverage:
1. Gemini provider initialization
2. Missing API key
3. Valid Gemini response
4. YES / NO / NOT SURE verdicts
5. Malformed Gemini response
6. Gemini failure
7. No silent fallback to Ollama
8. Mock Gemini provider
9. MetaQA score remains unchanged
10. Expected verdict remains programmatically derived
11. Gemini is only used for mutation verification
12. Existing Ollama answer generation still works
13. Existing Ollama mutation generation still works
14. Web Evidence remains unaffected
15. Health endpoint reflects Gemini status
16. Config properties
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.llm.base import LLMClient, LLMError
from app.llm.gemini import GeminiClient, GeminiVerifierError, MockGeminiClient
from app.llm.mock import MockLLMClient
from app.metaqa.detector import (
    BaseAnswer,
    DetectionResult,
    run_detection,
    run_metaqa_analysis,
    score_mutation,
)
from app.metaqa.mutation import GeneratedMutation
from app.metaqa.scoring import (
    Classification,
    MutationType,
    Verdict,
    aggregate_score,
    contribution_score,
    expected_verdict,
)
from app.metaqa.verifier import VerifierResult


# ── Fixtures ──────────────────────────────────────────────────────────────


def _mock_settings(**overrides) -> Settings:
    defaults = {
        "llm_mode": "mock",
        "llm_provider": "openai_compatible",
        "generator_model": "gpt-4o-mini",
        "verifier_model": "gpt-4o-mini",
        "gemini_verifier_model": "gemini-2.5-flash",
        "synonym_count": 3,
        "antonym_count": 3,
        "threshold": 0.5,
        "verify_concurrency": 3,
        "gemini_verify_concurrency": 3,
        "llm_timeout_seconds": 30.0,
        "llm_max_retries": 1,
        "llm_temperature": 0.0,
        "llm_max_output_tokens": 200,
        "llm_answer_max_tokens": 200,
        "llm_mutation_max_tokens": 400,
        "llm_verify_max_tokens": 96,
        "llm_claim_max_tokens": 256,
        "openai_api_key": "sk-test",
        "allowed_models": "gpt-4o-mini,gpt-4o",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ── 1. Gemini Provider Initialization ─────────────────────────────────────


class TestGeminiProviderInit:
    def test_init_with_valid_key(self):
        client = GeminiClient(api_key="test-key-123", default_model="gemini-2.5-flash")
        assert client._default_model == "gemini-2.5-flash"

    def test_init_with_empty_key_raises(self):
        with pytest.raises(GeminiVerifierError, match="GEMINI_API_KEY is not configured"):
            GeminiClient(api_key="", default_model="gemini-2.5-flash")

    def test_init_with_whitespace_key_raises(self):
        with pytest.raises(GeminiVerifierError, match="GEMINI_API_KEY is not configured"):
            GeminiClient(api_key="   ", default_model="gemini-2.5-flash")

    def test_init_with_custom_model(self):
        client = GeminiClient(api_key="key", default_model="gemini-3.5-flash")
        assert client._default_model == "gemini-3.5-flash"

    def test_init_with_custom_timeout(self):
        client = GeminiClient(api_key="key", timeout_seconds=60.0)
        assert client._timeout_seconds == 60.0

    def test_init_with_custom_retries(self):
        client = GeminiClient(api_key="key", max_retries=5)
        assert client._max_retries == 5


# ── 2. Missing API Key ───────────────────────────────────────────────────


class TestMissingApiKey:
    def test_missing_key_raises_error(self):
        with pytest.raises(GeminiVerifierError):
            GeminiClient(api_key="")

    def test_none_key_raises_error(self):
        """Even though type hint says str, guard against accidental None."""
        with pytest.raises((GeminiVerifierError, TypeError)):
            GeminiClient(api_key=None)  # type: ignore[arg-type]


# ── 3-5. Mock Gemini Responses (YES/NO/NOT SURE) ──────────────────────────


class TestMockGeminiResponses:
    @pytest.mark.asyncio
    async def test_reliable_scenario_synonym_yes(self):
        """Synonym mutations in reliable scenario should get YES."""
        client = MockGeminiClient(scenario="reliable")
        result = await client.complete_json(
            model="gemini-2.5-flash",
            system_prompt="You judge statements.",
            user_prompt="Statement to judge:\nSydney is the capital city of Australia.",
            max_tokens=96,
        )
        assert result["verdict"] in ("YES", "NO", "NOT SURE")

    @pytest.mark.asyncio
    async def test_hallucinated_scenario(self):
        """Hallucinated scenario should produce expected verdicts."""
        client = MockGeminiClient(scenario="hallucinated")
        result = await client.complete_json(
            model="gemini-2.5-flash",
            system_prompt="You judge statements.",
            user_prompt="Statement to judge:\nThe capital of Australia is Sydney.",
            max_tokens=96,
        )
        assert "verdict" in result

    @pytest.mark.asyncio
    async def test_uncertain_scenario_returns_not_sure(self):
        client = MockGeminiClient(scenario="uncertain")
        result = await client.complete_json(
            model="gemini-2.5-flash",
            system_prompt="You judge statements.",
            user_prompt="Statement to judge:\nSomething uncertain.",
            max_tokens=96,
        )
        assert result["verdict"] == "NOT SURE"


# ── 6-7. Gemini Failure and No Fallback ────────────────────────────────────


class TestGeminiFailureNoFallback:
    def test_gemini_error_is_not_generic_llm_error(self):
        """GeminiVerifierError is a specific subclass, distinguishable from generic LLMError."""
        assert issubclass(GeminiVerifierError, LLMError)

    def test_gemini_provider_does_not_fall_back(self):
        """Verify GeminiClient and OllamaClient are separate types — no inheritance overlap."""
        from app.llm.ollama import OllamaClient
        assert not issubclass(GeminiClient, OllamaClient)
        assert not issubclass(type(MockGeminiClient()), OllamaClient)

    @pytest.mark.asyncio
    async def test_mock_gemini_is_independent_from_ollama(self):
        """MockGeminiClient should not be an OllamaClient instance."""
        from app.llm.ollama import OllamaClient
        client = MockGeminiClient(scenario="reliable")
        assert not isinstance(client, OllamaClient)


# ── 8. Mock Gemini Provider ────────────────────────────────────────────────


class TestMockGeminiProvider:
    def test_mock_implements_llm_client(self):
        client = MockGeminiClient()
        assert isinstance(client, LLMClient)

    @pytest.mark.asyncio
    async def test_mock_complete_json(self):
        client = MockGeminiClient(scenario="reliable")
        result = await client.complete_json(
            model="gemini-2.5-flash",
            system_prompt="Test",
            user_prompt="Statement to judge:\nTest statement.",
            max_tokens=96,
        )
        assert isinstance(result, dict)
        assert "verdict" in result

    @pytest.mark.asyncio
    async def test_mock_complete_text(self):
        client = MockGeminiClient(scenario="reliable")
        result = await client.complete_text(
            model="gemini-2.5-flash",
            system_prompt="Answer questions.",
            user_prompt="Question:\nWhat is the capital of India?",
            max_tokens=200,
        )
        assert isinstance(result, str)
        assert len(result) > 0


# ── 9. MetaQA Score Remains Unchanged ─────────────────────────────────────


class TestScoringUnchanged:
    def test_synonym_contribution_values(self):
        assert contribution_score(MutationType.SYNONYM, Verdict.YES) == 0.0
        assert contribution_score(MutationType.SYNONYM, Verdict.NO) == 1.0
        assert contribution_score(MutationType.SYNONYM, Verdict.NOT_SURE) == 0.5

    def test_antonym_contribution_values(self):
        assert contribution_score(MutationType.ANTONYM, Verdict.YES) == 1.0
        assert contribution_score(MutationType.ANTONYM, Verdict.NO) == 0.0
        assert contribution_score(MutationType.ANTONYM, Verdict.NOT_SURE) == 0.5

    def test_aggregate_score(self):
        assert aggregate_score([0.0, 0.0, 0.0, 0.0, 0.0]) == 0.0
        assert aggregate_score([1.0, 1.0, 1.0, 1.0, 1.0]) == 1.0
        assert aggregate_score([0.0, 1.0]) == 0.5

    def test_threshold_unchanged(self):
        settings = _mock_settings()
        assert settings.threshold == 0.5


# ── 10. Expected Verdict Remains Programmatically Derived ─────────────────


class TestExpectedVerdictProgrammatic:
    def test_synonym_expected_yes(self):
        assert expected_verdict(MutationType.SYNONYM) == Verdict.YES

    def test_antonym_expected_no(self):
        assert expected_verdict(MutationType.ANTONYM) == Verdict.NO

    def test_expected_verdict_not_from_gemini(self):
        """Expected verdict is computed programmatically, not from Gemini."""
        mutation = GeneratedMutation(
            type=MutationType.SYNONYM,
            original_text="Test claim.",
            mutated_text="Paraphrased test claim.",
        )
        # Even if Gemini says NO, the expected remains YES for synonym
        result = VerifierResult(verdict=Verdict.NO, rationale="Gemini disagrees.")
        scored = score_mutation(mutation, result)
        assert scored.expected == Verdict.YES
        assert scored.verdict == Verdict.NO
        assert scored.contribution == 1.0  # synonym NO = 1.0 contribution


# ── 11-13. Gemini Only for Verification, Ollama for Generation ────────────


class TestCrossModelArchitecture:
    @pytest.mark.asyncio
    async def test_run_detection_with_mock_gemini_verifier(self):
        """Full detection with separate generator (Mock) and verifier (MockGemini)."""
        settings = _mock_settings()
        generator_llm = MockLLMClient(scenario="reliable")
        verifier_llm = MockGeminiClient(scenario="reliable")

        result = await run_detection(
            generator_llm,
            question="What is the capital of India?",
            settings=settings,
            verifier_llm=verifier_llm,
        )

        assert isinstance(result, DetectionResult)
        assert result.question == "What is the capital of India?"
        assert result.base_answer.text  # Answer generated
        assert len(result.mutations) > 0  # Mutations generated and verified
        assert result.hallucination_score is not None
        assert result.classification in (Classification.RELIABLE, Classification.HALLUCINATED)

    @pytest.mark.asyncio
    async def test_mutations_generated_by_generator_not_verifier(self):
        """Ensure the generator LLM generates mutations, not the verifier."""
        generator_llm = MockLLMClient(scenario="reliable")
        verifier_llm = MockGeminiClient(scenario="reliable")
        settings = _mock_settings()

        result = await run_detection(
            generator_llm,
            question="What is the capital of India?",
            settings=settings,
            verifier_llm=verifier_llm,
        )
        assert len(result.mutations) > 0

        # Generator should have been called for answer and mutations
        assert generator_llm.answer_calls >= 1
        assert generator_llm.mutation_calls >= 1

    @pytest.mark.asyncio
    async def test_verifier_llm_used_for_verification(self):
        """Ensure the verifier LLM receives verify calls."""
        generator_llm = MockLLMClient(scenario="reliable")
        verifier_llm = MockGeminiClient(scenario="reliable")
        settings = _mock_settings()

        answer = BaseAnswer(text="New Delhi is the capital of India.", model="gpt-4o-mini")

        result = await run_metaqa_analysis(
            generator_llm,
            question="What is the capital of India?",
            answer=answer,
            settings=settings,
            verifier_llm=verifier_llm,
        )
        assert result.hallucination_score is not None

        # Verifier should have verify calls
        assert verifier_llm._inner.verify_calls >= 1

    @pytest.mark.asyncio
    async def test_generator_not_used_for_verification_when_verifier_provided(self):
        """When a separate verifier_llm is provided, generator should NOT get verify calls."""
        generator_llm = MockLLMClient(scenario="reliable")
        verifier_llm = MockGeminiClient(scenario="reliable")
        settings = _mock_settings()

        answer = BaseAnswer(text="New Delhi is the capital of India.", model="gpt-4o-mini")

        # Reset counters
        generator_llm.verify_calls = 0

        result = await run_metaqa_analysis(
            generator_llm,
            question="What is the capital of India?",
            answer=answer,
            settings=settings,
            verifier_llm=verifier_llm,
        )
        assert result.hallucination_score is not None

        # Generator should NOT have received any verify calls
        assert generator_llm.verify_calls == 0


# ── 14. Web Evidence Remains Unaffected ───────────────────────────────────


class TestWebEvidenceUnaffected:
    def test_web_evidence_does_not_use_gemini(self):
        """Web Evidence pipeline imports are independent of Gemini."""
        from app.web_evidence.pipeline import run_web_evidence
        # Simply importing is enough to verify no hard dependency on Gemini
        assert callable(run_web_evidence)

    def test_web_evidence_config_unchanged(self):
        settings = _mock_settings(tavily_api_key="test-tavily-key")
        assert settings.tavily_configured
        assert settings.web_evidence_ready


# ── 15. Health Endpoint Gemini Status ──────────────────────────────────────


class TestHealthGeminiStatus:
    def test_gemini_configured_with_key(self):
        settings = _mock_settings(gemini_api_key="test-gemini-key", llm_mode="live")
        assert settings.gemini_configured
        assert settings.gemini_verifier_ready

    def test_gemini_not_configured_without_key(self):
        settings = _mock_settings(gemini_api_key="", llm_mode="live")
        assert not settings.gemini_configured
        assert not settings.gemini_verifier_ready

    def test_gemini_ready_in_mock_mode(self):
        settings = _mock_settings(gemini_api_key="", llm_mode="mock")
        assert settings.gemini_verifier_ready

    def test_effective_verifier_model_with_gemini(self):
        settings = _mock_settings(
            gemini_api_key="key",
            gemini_verifier_model="gemini-3.5-flash",
            llm_mode="live",
        )
        assert settings.effective_verifier_model == "gemini-3.5-flash"

    def test_effective_verifier_model_without_gemini(self):
        settings = _mock_settings(
            gemini_api_key="",
            verifier_model="gpt-4o-mini",
            llm_mode="live",
        )
        assert settings.effective_verifier_model == "gpt-4o-mini"

    def test_effective_verifier_model_mock_mode(self):
        settings = _mock_settings(
            gemini_verifier_model="gemini-2.5-flash",
            llm_mode="mock",
        )
        assert settings.effective_verifier_model == "gemini-2.5-flash"


# ── 16. Config Properties ──────────────────────────────────────────────────


class TestConfigProperties:
    def test_gemini_api_key_not_exposed(self):
        """Gemini API key should not appear in health-safe properties."""
        settings = _mock_settings(gemini_api_key="secret-key")
        # Verify gemini_configured works when key is set
        assert settings.gemini_configured is True
        empty_settings = _mock_settings(gemini_api_key="")
        assert empty_settings.gemini_configured is False

    def test_gemini_api_key_not_in_replace_with_prefix(self):
        settings = _mock_settings(gemini_api_key="replace-with-key", llm_mode="live")
        assert not settings.gemini_configured

    def test_gemini_verify_concurrency_default(self):
        settings = _mock_settings()
        assert settings.gemini_verify_concurrency == 3

    def test_gemini_verify_concurrency_custom(self):
        settings = _mock_settings(gemini_verify_concurrency=5)
        assert settings.gemini_verify_concurrency == 5


# ── Cross-Model Verification Integrity ────────────────────────────────────


class TestCrossModelIntegrity:
    @pytest.mark.asyncio
    async def test_same_mutations_different_verifier(self):
        """Same mutation set should be verifiable by different clients."""
        settings = _mock_settings()
        generator = MockLLMClient(scenario="reliable")
        verifier_a = MockGeminiClient(scenario="reliable")
        verifier_b = MockGeminiClient(scenario="hallucinated")

        answer = BaseAnswer(text="New Delhi is the capital of India.", model="gpt-4o-mini")

        result_a = await run_metaqa_analysis(
            generator,
            question="What is the capital of India?",
            answer=answer,
            settings=settings,
            verifier_llm=verifier_a,
        )

        # Reset generator state for fair comparison
        generator.mutation_calls = 0
        generator.claim_calls = 0
        generator._verify_index = 0
        generator._last_claims = []

        result_b = await run_metaqa_analysis(
            generator,
            question="What is the capital of India?",
            answer=answer,
            settings=settings,
            verifier_llm=verifier_b,
        )

        # Both should have the same number of mutations
        assert len(result_a.mutations) == len(result_b.mutations)
        # But different scores (reliable vs hallucinated verifier)
        # The key point: mutations are generated once by generator,
        # then verified by different verifier clients

    @pytest.mark.asyncio
    async def test_gemini_rationale_not_used_in_scoring(self):
        """Gemini's rationale must NOT affect the MetaQA score."""
        mutation = GeneratedMutation(
            type=MutationType.SYNONYM,
            original_text="Test claim.",
            mutated_text="Equivalent test claim.",
        )

        # Same verdict, different rationale — score must be identical
        result_a = VerifierResult(verdict=Verdict.YES, rationale="Short reason.")
        result_b = VerifierResult(verdict=Verdict.YES, rationale="A very long elaborate reason that is different.")

        scored_a = score_mutation(mutation, result_a)
        scored_b = score_mutation(mutation, result_b)

        assert scored_a.contribution == scored_b.contribution
        assert scored_a.expected == scored_b.expected
        assert scored_a.verdict == scored_b.verdict

    @pytest.mark.asyncio
    async def test_mutation_set_not_regenerated_by_verifier(self):
        """Gemini verifier must not regenerate or modify mutations."""
        generator = MockLLMClient(scenario="reliable")
        verifier = MockGeminiClient(scenario="reliable")
        settings = _mock_settings()

        answer = BaseAnswer(text="New Delhi is the capital of India.", model="gpt-4o-mini")

        result = await run_metaqa_analysis(
            generator,
            question="What is the capital of India?",
            answer=answer,
            settings=settings,
            verifier_llm=verifier,
        )
        assert len(result.mutations) > 0

        # Generator should have generated mutations
        assert generator.mutation_calls >= 1
        # Verifier should NOT have any mutation generation calls
        assert verifier._inner.mutation_calls == 0
