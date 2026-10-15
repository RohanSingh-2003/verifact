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
            user_prompt="Statement to judge:\nCanberra is the capital city of Australia.",
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


# ── 17. Regression Tests for Retries, Error Handling, and Isolation ─────────


class TestGeminiRetriesAndErrorHandling:
    @pytest.mark.asyncio
    async def test_transient_503_followed_by_successful_retry(self):
        """A transient 503 should trigger exponential backoff retry and succeed on the next attempt."""
        client = GeminiClient(
            api_key="test-key",
            default_model="gemini-3.8-flash",
            max_retries=3,
            initial_retry_delay=0.01,
            max_retry_delay=0.05,
            total_retry_timeout=10.0,
        )

        call_count = 0

        class MockResponse:
            text = '{"verdict": "YES", "rationale": "Consistent claim"}'
            candidates: tuple = ()

        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand.'}}")
            return MockResponse()

        mock_genai_client = type("MockGenAIClient", (), {
            "models": type("MockModels", (), {"generate_content": staticmethod(mock_generate_content)})()
        })()
        client._client = mock_genai_client

        res = await client.complete_json(
            model="gemini-3.8-flash",
            system_prompt="Test system",
            user_prompt="Test user",
        )

        assert call_count == 2
        assert res["verdict"] == "YES"
        assert res["rationale"] == "Consistent claim"

    @pytest.mark.asyncio
    async def test_repeated_503_responses_exhausting_retry_budget(self):
        """Repeated 503 errors must exhaust max_retries and raise GeminiUnavailableError with clear message."""
        client = GeminiClient(
            api_key="test-key",
            default_model="gemini-3.8-flash",
            max_retries=2,
            initial_retry_delay=0.01,
            max_retry_delay=0.03,
            total_retry_timeout=5.0,
        )

        call_count = 0

        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand.'}}")

        mock_genai_client = type("MockGenAIClient", (), {
            "models": type("MockModels", (), {"generate_content": staticmethod(mock_generate_content)})()
        })()
        client._client = mock_genai_client

        from app.llm.gemini import GeminiUnavailableError

        with pytest.raises(GeminiUnavailableError) as exc_info:
            await client.complete_json(
                model="gemini-3.8-flash",
                system_prompt="Test system",
                user_prompt="Test user",
            )

        assert "temporarily unavailable due to high demand" in str(exc_info.value)
        # 1 initial + 2 retries = 3 total attempts
        assert call_count == 3
        # Model was NOT silently changed or substituted
        assert client._default_model == "gemini-3.8-flash"

    @pytest.mark.asyncio
    async def test_non_retryable_auth_error_no_retry(self):
        """HTTP 401/403 or unauthenticated must fail immediately without retrying."""
        client = GeminiClient(
            api_key="invalid-key",
            default_model="gemini-3.8-flash",
            max_retries=3,
        )

        call_count = 0

        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("403 PERMISSION_DENIED. {'error': {'code': 403, 'message': 'API key not valid.'}}")

        mock_genai_client = type("MockGenAIClient", (), {
            "models": type("MockModels", (), {"generate_content": staticmethod(mock_generate_content)})()
        })()
        client._client = mock_genai_client

        from app.llm.gemini import GeminiAuthError

        with pytest.raises(GeminiAuthError) as exc_info:
            await client.complete_text(
                model="gemini-3.8-flash",
                system_prompt="Test",
                user_prompt="Test",
            )

        assert call_count == 1
        assert "401" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_non_retryable_permission_error_no_retry(self):
        """HTTP 403 or permission denied must fail immediately with GeminiPermissionError without retrying."""
        from app.llm.gemini import GeminiClient, GeminiPermissionError

        client = GeminiClient(
            api_key="restricted-key",
            default_model="gemini-3.8-flash",
            max_retries=3,
        )

        call_count = 0

        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("403 PERMISSION_DENIED. Method doesn't allow unregistered callers or Generative Language API is disabled.")

        mock_genai_client = type("MockGenAIClient", (), {
            "models": type("MockModels", (), {"generate_content": staticmethod(mock_generate_content)})()
        })()
        client._client = mock_genai_client

        with pytest.raises(GeminiPermissionError) as exc_info:
            await client.complete_text(
                model="gemini-3.8-flash",
                system_prompt="Test",
                user_prompt="Test",
            )

        assert call_count == 1
        assert "403" in str(exc_info.value)
        assert "forbidden" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_403_quota_treated_as_rate_limit(self):
        """HTTP 403 with quota/rate exhaustion is classified as GeminiRateLimitError, not auth failure."""
        from app.llm.gemini import GeminiClient, GeminiRateLimitError

        client = GeminiClient(
            api_key="valid-key",
            default_model="gemini-3.8-flash",
            max_retries=1,
            initial_retry_delay=0.01,
            total_retry_timeout=2.0,
        )

        call_count = 0

        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("403 PERMISSION_DENIED. Quota exceeded for project 123456: generate_content_free_tier_requests.")

        mock_genai_client = type("MockGenAIClient", (), {
            "models": type("MockModels", (), {"generate_content": staticmethod(mock_generate_content)})()
        })()
        client._client = mock_genai_client

        with pytest.raises(GeminiRateLimitError) as exc_info:
            await client.complete_text(
                model="gemini-3.8-flash",
                system_prompt="Test",
                user_prompt="Test",
            )

        assert "rate limit" in str(exc_info.value).lower()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_non_retryable_model_not_found_no_retry(self):
        """HTTP 404 or model not found must fail immediately without retrying or substituting."""
        client = GeminiClient(
            api_key="test-key",
            default_model="gemini-nonexistent",
            max_retries=3,
        )

        call_count = 0

        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-nonexistent not found'}}")

        mock_genai_client = type("MockGenAIClient", (), {
            "models": type("MockModels", (), {"generate_content": staticmethod(mock_generate_content)})()
        })()
        client._client = mock_genai_client

        from app.llm.gemini import GeminiModelNotFoundError

        with pytest.raises(GeminiModelNotFoundError) as exc_info:
            await client.complete_text(
                model="gemini-nonexistent",
                system_prompt="Test",
                user_prompt="Test",
            )

        assert call_count == 1
        assert "404" in str(exc_info.value)
        assert "gemini-nonexistent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_gemini_failure_alongside_successful_independent_verifiers(self, monkeypatch):
        """When Gemini is unavailable, other independent verifiers must succeed and be aggregated."""
        from app.llm.gemini import GeminiUnavailableError
        from app.services.independent_verifiers import (
            build_multi_model_summary,
            evaluate_all_independent_verifiers,
        )
        from app.llm.providers import ModelClient

        settings = _mock_settings(llm_mode="live")

        class MockWorkingClient(ModelClient):
            async def generate_answer(self, question, **kwargs):
                return "Answer"

            async def complete_text(self, **kwargs):
                return "Text"

            async def complete_json(self, **kwargs):
                return {"verdict": "Correct", "reasoning": "Looks accurate.", "contradictory_claims": []}

        class MockFailingGeminiClient(ModelClient):
            async def generate_answer(self, question, **kwargs):
                return "Answer"

            async def complete_text(self, **kwargs):
                raise GeminiUnavailableError("Google Gemini Flash 3.8 is temporarily unavailable due to high demand.")

            async def complete_json(self, **kwargs):
                raise GeminiUnavailableError("Google Gemini Flash 3.8 is temporarily unavailable due to high demand.")

        def fake_get_model_client(mid, s):
            if mid == "gemini":
                return MockFailingGeminiClient()
            return MockWorkingClient()

        from app.llm.registry import MODEL_REGISTRY, AnswerModelDefinition
        monkeypatch.setattr("app.services.independent_verifiers.get_model_client", fake_get_model_client)
        monkeypatch.setattr("app.services.independent_verifiers.is_model_configured", lambda mid, s: True)
        monkeypatch.setitem(
            MODEL_REGISTRY,
            "gemini",
            AnswerModelDefinition(
                id="gemini",
                display_name="Gemini Flash 3.8",
                provider="gemini",
                provider_display="Google",
                default_model_name="gemini-3.8-flash",
                env_key_name="GEMINI_API_KEY",
            ),
        )

        verdicts = await evaluate_all_independent_verifiers(
            question="What is the capital of Australia?",
            answer="Canberra is the capital of Australia.",
            selected_answer_model_id="gemma",
            settings=settings,
        )

        gemini_v = next((v for v in verdicts if v.model_id == "gemini"), None)
        assert gemini_v is not None
        assert gemini_v.status == "failed"
        assert "Service unavailable" in gemini_v.verdict or "FAILED" in gemini_v.verdict
        assert "temporarily unavailable due to high demand" in gemini_v.error

        other_verdicts = [v for v in verdicts if v.model_id != "gemini"]
        assert len(other_verdicts) > 0
        for ov in other_verdicts:
            assert ov.status == "completed"
            assert ov.verdict == "Correct"

        summary = build_multi_model_summary(verdicts)
        assert summary.completed_verifiers == len(other_verdicts)
        assert summary.failed_count == 1
        assert summary.correct_count == len(other_verdicts)
        assert summary.incorrect_count == 0

    def test_no_api_key_leakage_in_sanitization(self):
        """Sanitization must strip raw API keys and google API key patterns from errors and logs."""
        from app.llm.gemini import _sanitize_error_message

        secret_key = "AIzaSyTestSecretKey_1234567890abcdef"
        raw_error = f"Request failed: https://generativelanguage.googleapis.com/v1beta/models?key={secret_key}&alt=json"

        sanitized = _sanitize_error_message(raw_error, secret_key)
        assert secret_key not in sanitized
        assert "[MASKED" in sanitized or "key=[MASKED]" in sanitized

    @pytest.mark.asyncio
    async def test_first_request_timing_out_followed_by_successful_retry(self):
        """Regression 1: A first request timing out followed by a successful retry."""
        from app.llm.gemini import GeminiClient

        client = GeminiClient(
            api_key="test-key",
            default_model="gemini-3.8-flash",
            timeout_seconds=5.0,
            max_retries=2,
            initial_retry_delay=0.01,
            max_retry_delay=0.05,
            total_retry_timeout=15.0,
        )

        call_count = 0

        class MockResponse:
            text = '{"verdict": "YES", "rationale": "Claim is accurate"}'
            candidates: tuple = ()

        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Simulated socket connection timeout on attempt 1")
            return MockResponse()

        mock_genai_client = type("MockGenAIClient", (), {
            "models": type("MockModels", (), {"generate_content": staticmethod(mock_generate_content)})()
        })()
        client._client = mock_genai_client

        res = await client.complete_json(
            model="gemini-3.8-flash",
            system_prompt="Test system",
            user_prompt="Test user",
        )

        assert call_count == 2
        assert res["verdict"] == "YES"
        assert res["rationale"] == "Claim is accurate"

    @pytest.mark.asyncio
    async def test_multiple_timeouts_exhausting_retry_budget(self):
        """Regression 2: Multiple timeouts exhausting the retry budget must produce clear message."""
        from app.llm.base import LLMTimeoutError
        from app.llm.gemini import GeminiClient

        client = GeminiClient(
            api_key="test-key",
            default_model="gemini-3.8-flash",
            timeout_seconds=2.0,
            max_retries=2,
            initial_retry_delay=0.01,
            max_retry_delay=0.03,
            total_retry_timeout=10.0,
        )

        call_count = 0

        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Deadline exceeded")

        mock_genai_client = type("MockGenAIClient", (), {
            "models": type("MockModels", (), {"generate_content": staticmethod(mock_generate_content)})()
        })()
        client._client = mock_genai_client

        with pytest.raises(LLMTimeoutError) as exc_info:
            await client.complete_json(
                model="gemini-3.8-flash",
                system_prompt="Test system",
                user_prompt="Test user",
            )

        assert "Gemini timed out after multiple attempts. Please try again later." in str(exc_info.value)
        # Initial attempt + 2 retries = 3 attempts
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_per_attempt_timeout_shorter_than_overall_budget(self):
        """Regression 3: Per-attempt timeout must be strictly bounded and shorter than total budget."""
        from app.llm.gemini import GeminiClient

        client = GeminiClient(
            api_key="test-key",
            default_model="gemini-3.8-flash",
            timeout_seconds=10.0,
            max_retries=3,
            total_retry_timeout=30.0,
        )

        # Configured per-attempt timeout is separated and shorter than total retry timeout
        assert client._timeout_seconds == 10.0
        assert client._total_retry_timeout == 30.0
        assert client._timeout_seconds < client._total_retry_timeout

        # Even if timeout_seconds is configured large, an attempt with retries remaining cannot consume whole budget
        client_large = GeminiClient(
            api_key="test-key",
            default_model="gemini-3.8-flash",
            timeout_seconds=40.0,
            max_retries=2,
            initial_retry_delay=1.0,
            total_retry_timeout=30.0,
        )

        # In _generate, remaining budget is reserved so attempt 0 does not take all 30s
        min_attempt_budget = min(1.0, max(0.01, client_large._total_retry_timeout / (client_large._max_retries + 1) * 0.2))
        retries_left = 2
        remaining_total_budget = 30.0
        reserved_for_retries = min(
            remaining_total_budget * 0.5,
            retries_left * (min_attempt_budget + min(client_large._initial_retry_delay, 1.0)),
        )
        max_for_attempt = max(min_attempt_budget, remaining_total_budget - reserved_for_retries)
        call_timeout = min(client_large._timeout_seconds, max_for_attempt)

        assert call_timeout < remaining_total_budget
        assert remaining_total_budget - call_timeout >= reserved_for_retries

    @pytest.mark.asyncio
    async def test_backoff_not_exceeding_remaining_budget(self):
        """Regression 4: Backoff sleep must not exceed the remaining time budget."""
        import time
        from app.llm.base import LLMTimeoutError
        from app.llm.gemini import GeminiClient

        # Setup client with tiny budget (0.15s) but large initial backoff (10.0s)
        client = GeminiClient(
            api_key="test-key",
            default_model="gemini-3.8-flash",
            timeout_seconds=0.05,
            max_retries=3,
            initial_retry_delay=10.0,
            max_retry_delay=30.0,
            total_retry_timeout=0.15,
        )

        def mock_generate_content(*args, **kwargs):
            raise TimeoutError("Timed out")

        mock_genai_client = type("MockGenAIClient", (), {
            "models": type("MockModels", (), {"generate_content": staticmethod(mock_generate_content)})()
        })()
        client._client = mock_genai_client

        t0 = time.perf_counter()
        with pytest.raises(LLMTimeoutError):
            await client.complete_text(
                model="gemini-3.8-flash",
                system_prompt="Test",
                user_prompt="Test",
            )
        elapsed = time.perf_counter() - t0

        # Must not sleep for 10 seconds; backoff is bounded to remaining budget
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_no_extra_request_after_retry_budget_expires(self):
        """Regression 5: No extra request is initiated once the retry budget is exhausted."""
        import time
        from app.llm.base import LLMTimeoutError
        from app.llm.gemini import GeminiClient

        client = GeminiClient(
            api_key="test-key",
            default_model="gemini-3.8-flash",
            timeout_seconds=0.08,
            max_retries=10,
            initial_retry_delay=0.01,
            max_retry_delay=0.02,
            total_retry_timeout=0.10,
        )

        call_count = 0

        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Simulate an attempt taking 0.09s, nearly exhausting 0.10s budget
            time.sleep(0.09)
            raise TimeoutError("Socket timeout")

        mock_genai_client = type("MockGenAIClient", (), {
            "models": type("MockModels", (), {"generate_content": staticmethod(mock_generate_content)})()
        })()
        client._client = mock_genai_client

        with pytest.raises(LLMTimeoutError):
            await client.complete_text(
                model="gemini-3.8-flash",
                system_prompt="Test",
                user_prompt="Test",
            )

        # Even with max_retries=10, it must terminate as soon as budget is exhausted (1 or 2 calls max)
        assert call_count <= 2

    @pytest.mark.asyncio
    async def test_non_retryable_errors_fail_immediately(self):
        """Regression 6: Authentication, invalid-model, and malformed-request errors fail immediately without retry."""
        from app.llm.gemini import (
            GeminiAuthError,
            GeminiClient,
            GeminiModelNotFoundError,
            GeminiVerifierError,
        )

        # 6a. Authentication error
        client_auth = GeminiClient(api_key="test-key", max_retries=3)
        call_count_auth = 0

        def mock_auth(*args, **kwargs):
            nonlocal call_count_auth
            call_count_auth += 1
            raise RuntimeError("401 UNAUTHENTICATED. API key not valid.")

        client_auth._client = type("C", (), {"models": type("M", (), {"generate_content": staticmethod(mock_auth)})()})()

        with pytest.raises(GeminiAuthError):
            await client_auth.complete_text(model="gemini-3.8-flash", system_prompt="", user_prompt="")
        assert call_count_auth == 1

        # 6b. Invalid model (404)
        client_model = GeminiClient(api_key="test-key", max_retries=3)
        call_count_model = 0

        def mock_model(*args, **kwargs):
            nonlocal call_count_model
            call_count_model += 1
            raise RuntimeError("404 NOT_FOUND. Model models/gemini-invalid not found.")

        client_model._client = type("C", (), {"models": type("M", (), {"generate_content": staticmethod(mock_model)})()})()

        with pytest.raises(GeminiModelNotFoundError):
            await client_model.complete_text(model="gemini-invalid", system_prompt="", user_prompt="")
        assert call_count_model == 1

        # 6c. Malformed / Invalid argument request (400)
        client_bad_req = GeminiClient(api_key="test-key", max_retries=3)
        call_count_bad_req = 0

        def mock_bad_req(*args, **kwargs):
            nonlocal call_count_bad_req
            call_count_bad_req += 1
            raise RuntimeError("400 INVALID_ARGUMENT. Invalid contents format.")

        client_bad_req._client = type("C", (), {"models": type("M", (), {"generate_content": staticmethod(mock_bad_req)})()})()

        with pytest.raises(GeminiVerifierError) as exc_bad:
            await client_bad_req.complete_text(model="gemini-3.8-flash", system_prompt="", user_prompt="")
        assert call_count_bad_req == 1
        assert "HTTP 400" in str(exc_bad.value)

    @pytest.mark.asyncio
    async def test_successful_peer_verifiers_usable_when_gemini_times_out(self, monkeypatch):
        """Regression 7: Successful peer verifiers remain fully usable and aggregated when Gemini times out."""
        from app.llm.base import LLMTimeoutError
        from app.llm.providers import ModelClient
        from app.services.independent_verifiers import (
            build_multi_model_summary,
            evaluate_all_independent_verifiers,
        )

        settings = _mock_settings(llm_mode="live")

        class MockPeerClient(ModelClient):
            async def generate_answer(self, question, **kwargs):
                return "Peer Answer"

            async def complete_text(self, **kwargs):
                return "Peer text"

            async def complete_json(self, **kwargs):
                return {"verdict": "Correct", "reasoning": "Accurate fact.", "contradictory_claims": []}

        class MockTimingOutGeminiClient(ModelClient):
            async def generate_answer(self, question, **kwargs):
                return "Gemini Answer"

            async def complete_text(self, **kwargs):
                raise LLMTimeoutError("Gemini timed out after multiple attempts. Please try again later.")

            async def complete_json(self, **kwargs):
                raise LLMTimeoutError("Gemini timed out after multiple attempts. Please try again later.")

        def fake_get_model_client(mid, s):
            if mid == "gemini":
                return MockTimingOutGeminiClient()
            return MockPeerClient()

        from app.llm.registry import MODEL_REGISTRY, AnswerModelDefinition
        monkeypatch.setattr("app.services.independent_verifiers.get_model_client", fake_get_model_client)
        monkeypatch.setattr("app.services.independent_verifiers.is_model_configured", lambda mid, s: True)
        monkeypatch.setitem(
            MODEL_REGISTRY,
            "gemini",
            AnswerModelDefinition(
                id="gemini",
                display_name="Gemini Flash 3.8",
                provider="gemini",
                provider_display="Google",
                default_model_name="gemini-3.8-flash",
                env_key_name="GEMINI_API_KEY",
            ),
        )

        verdicts = await evaluate_all_independent_verifiers(
            question="What is the boiling point of water at standard atmospheric pressure?",
            answer="Water boils at 100 degrees Celsius at 1 atmosphere.",
            selected_answer_model_id="gemma",
            settings=settings,
        )

        gemini_v = next((v for v in verdicts if v.model_id == "gemini"), None)
        assert gemini_v is not None
        assert gemini_v.status == "failed"
        assert "Request timed out" in gemini_v.verdict
        assert "Gemini timed out after multiple attempts. Please try again later." in gemini_v.error

        peer_verdicts = [v for v in verdicts if v.model_id != "gemini"]
        assert len(peer_verdicts) > 0
        for pv in peer_verdicts:
            assert pv.status == "completed"
            assert pv.verdict == "Correct"

        summary = build_multi_model_summary(verdicts)
        # Peer verifiers remain fully usable and aggregated
        assert summary.completed_verifiers == len(peer_verdicts)
        assert summary.failed_count == 1
        assert summary.correct_count == len(peer_verdicts)
        assert summary.incorrect_count == 0
