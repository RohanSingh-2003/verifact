"""Regression tests for factual audit of mock files and fixtures.

Verifies:
1. The mock answer for Australia's capital is Canberra.
2. The original Australia fixture is factually correct.
3. Synonym mutations preserve the original meaning.
4. Antonym mutations genuinely contradict the original claim.
5. Expected verdicts and score contributions are logically consistent.
6. Deliberately incorrect answers remain available for negative testing.
7. The other hardcoded factual fixtures do not contain known factual errors.
8. Live provider mode does not use mock answers.
9. Mock execution cannot silently contaminate real evaluation results.
10. Existing failure, malformed-response, uncertainty, and mixed-verdict tests still work.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.config import Settings
from app.evaluation.ground_truth import resolve_ground_truth
from app.evaluation.schemas import DatasetExample
from app.llm.base import LLMError
from app.llm.gemini import GeminiClient, GeminiVerifierError
from app.llm.mock import (
    DELIBERATE_HALLUCINATED_AUSTRALIA_ANSWER,
    DEFAULT_MUTATIONS,
    ORIGINAL,
    SCENARIO_VERDICTS,
    _BUILTIN_ANSWERS,
    _builtin_answer,
    _is_meaning_reversing,
    MockLLMClient,
)
from app.metaqa.detector import run_detection
from tests.fakes import detector_settings
from app.metaqa.scoring import Classification, MutationType, Verdict, contribution_score
from app.services.experiment_service import ExperimentConfigError, ExperimentRunRequest, validate_request


# ── 1. Mock answer for Australia's capital is Canberra ──────────────────────


@pytest.mark.asyncio
async def test_01_mock_answer_for_australia_is_canberra() -> None:
    """The built-in mock answer for Australia's capital must be Canberra."""
    assert _BUILTIN_ANSWERS["what is the capital of australia"] == "Canberra is the capital of Australia."
    assert _builtin_answer("What is the capital of Australia?") == "Canberra is the capital of Australia."
    assert _builtin_answer("what is the capital of australia") == "Canberra is the capital of Australia."

    client = MockLLMClient()
    ans = await client.complete_text(
        model="mock-model",
        system_prompt="Answer factually.",
        user_prompt="Question: What is the capital of Australia?\nWrite a concise factual answer.",
    )
    assert ans == "Canberra is the capital of Australia."
    assert "Sydney" not in ans
    assert "Melbourne" not in ans


# ── 2. The original Australia fixture is factually correct ──────────────────


def test_02_original_australia_fixture_is_factually_correct() -> None:
    """ORIGINAL must state Canberra as the capital of Australia, not Sydney or Melbourne."""
    assert ORIGINAL == "Canberra is the capital of Australia."
    assert "Canberra" in ORIGINAL
    assert "Sydney" not in ORIGINAL
    assert "Melbourne" not in ORIGINAL

    client = MockLLMClient()
    assert client.answer == "Canberra is the capital of Australia."


# ── 3. Synonym mutations preserve the original meaning ──────────────────────


def test_03_synonym_mutations_preserve_original_meaning() -> None:
    """All synonym mutations must maintain Canberra as the capital of Australia."""
    synonyms = [m for m in DEFAULT_MUTATIONS if m["type"] == MutationType.SYNONYM.value]
    assert len(synonyms) == 5

    for syn in synonyms:
        assert syn["original_text"] == "Canberra is the capital of Australia."
        assert "Canberra" in syn["mutated_text"]
        assert "Sydney" not in syn["mutated_text"]
        assert "Melbourne" not in syn["mutated_text"]
        # Must not be flagged as meaning-reversing
        assert not _is_meaning_reversing(syn["mutated_text"])


# ── 4. Antonym mutations genuinely contradict the original claim ────────────


def test_04_antonym_mutations_genuinely_contradict_original_claim() -> None:
    """All antonym mutations must contradict the canonical claim that Canberra is capital."""
    antonyms = [m for m in DEFAULT_MUTATIONS if m["type"] == MutationType.ANTONYM.value]
    assert len(antonyms) == 5

    contradicting_texts = [m["mutated_text"] for m in antonyms]
    assert "The capital of Australia is Sydney." in contradicting_texts
    assert "Canberra is not the capital of Australia." in contradicting_texts
    assert "Sydney, not Canberra, is the capital of Australia." in contradicting_texts
    assert "The capital of Australia is Melbourne." in contradicting_texts
    assert "Australia does not have Canberra as its capital city." in contradicting_texts

    for ant in antonyms:
        assert ant["original_text"] == "Canberra is the capital of Australia."
        # Every antonym must be recognized as meaning-reversing
        assert _is_meaning_reversing(ant["mutated_text"])


# ── 5. Expected verdicts and score contributions are logically consistent ───


@pytest.mark.asyncio
async def test_05_expected_verdicts_and_score_contributions_logically_consistent() -> None:
    """Reliable scenario must give YES to Canberra synonyms and NO to antonyms, resulting in score 0.0."""
    client = MockLLMClient(scenario="reliable")
    settings = detector_settings()

    result = await run_detection(client, question="What is the capital of Australia?", settings=settings)
    assert result.base_answer.text == "Canberra is the capital of Australia."
    assert result.hallucination_score == 0.0
    assert result.classification is Classification.RELIABLE

    # Check each mutation verdict and contribution
    for scored in result.mutations:
        if scored.mutation.type == MutationType.SYNONYM:
            assert scored.verdict == Verdict.YES
            assert scored.expected == Verdict.YES
            assert scored.contribution == 0.0
            assert "consistent" in scored.rationale.lower()
        elif scored.mutation.type == MutationType.ANTONYM:
            assert scored.verdict == Verdict.NO
            assert scored.expected == Verdict.NO
            assert scored.contribution == 0.0
            assert "contradicts" in scored.rationale.lower() or "negates" in scored.rationale.lower()


# ── 6. Deliberately incorrect answers remain available for negative testing ─


@pytest.mark.asyncio
async def test_06_deliberately_incorrect_answers_for_negative_testing() -> None:
    """Deliberately false statements like Sydney must be detectable as hallucinations."""
    assert DELIBERATE_HALLUCINATED_AUSTRALIA_ANSWER == "Sydney is the capital of Australia."

    # Negative test case with deliberately false answer and hallucinated scenario
    client = MockLLMClient(
        scenario="hallucinated",
        answers_by_question={
            "What is the capital of Australia?": DELIBERATE_HALLUCINATED_AUSTRALIA_ANSWER,
        },
    )
    settings = detector_settings()
    result = await run_detection(client, question="What is the capital of Australia?", settings=settings)

    assert result.base_answer.text == "Sydney is the capital of Australia."
    assert result.hallucination_score == 1.0
    assert result.classification is Classification.HALLUCINATED

    # Verify ground-truth resolution correctly classifies Sydney as hallucination against Canberra
    dataset_example = DatasetExample(
        id="audit_q01",
        question="What is the capital of Australia?",
        reference_answer="Canberra",
        category="location",
        source="curated",
    )
    gt_decision = resolve_ground_truth(DELIBERATE_HALLUCINATED_AUSTRALIA_ANSWER, dataset_example)
    assert gt_decision.label is Classification.HALLUCINATED

    # Verify ground-truth resolution correctly classifies Canberra as reliable
    gt_correct = resolve_ground_truth("Canberra is the capital of Australia.", dataset_example)
    assert gt_correct.label is Classification.RELIABLE


# ── 7. Other hardcoded factual fixtures audited and correct ─────────────────


def test_07_other_hardcoded_factual_fixtures_audited() -> None:
    """Verify all built-in factual answers are accurate across science, geography, history, and math."""
    audited = {
        "what is the capital of india": "New Delhi",
        "what is the capital of france": "Paris",
        "who formulated the three laws of motion": "Isaac Newton",
        "who wrote hamlet": "William Shakespeare",
        "what is 2 + 2": "4",
        "what is the capital of australia": "Canberra",
        "what causes a solar eclipse": "Moon passes between the Earth and the Sun",
        "who wrote pride and prejudice": "Jane Austen",
        "how does a refrigerator work": "refrigerant fluid",
        "why is the sky blue": "scatter",
        "can you explain how photosynthesis converts light energy into chemical energy": "carbon dioxide and water into oxygen and glucose",
        "what is the speed of light": "299,792,458",
        "who painted the mona lisa": "Leonardo da Vinci",
        "what is the largest planet in our solar system": "Jupiter",
        "who discovered penicillin": "Alexander Fleming",
        "what is the boiling point of water": "100 degrees Celsius",
    }
    for question_key, expected_substring in audited.items():
        ans = _BUILTIN_ANSWERS[question_key]
        assert expected_substring.lower() in ans.lower(), f"Fact check failed for {question_key}: {ans}"


# ── 8. Live provider mode does not use mock answers ─────────────────────────


def test_08_live_provider_mode_does_not_use_mock_answers() -> None:
    """Live provider clients must not fall back to or contain mock answers."""
    # Live Gemini client raises on missing key and never returns mock data
    with pytest.raises(GeminiVerifierError, match="GEMINI_API_KEY is not configured"):
        GeminiClient(api_key="")

    # Settings requiring live mode with no key cannot run live experiments
    live_settings = Settings(
        llm_mode="live",
        openai_api_key="",
        gemini_api_key="",
        openrouter_api_key="",
        ollama_api_key="",
        cloudflare_api_token="",
        groq_api_key="",
    )
    assert not live_settings.api_key_configured

    request = ExperimentRunRequest(
        name="Test Live Guard",
        dataset="pilot",
        generator_models=["gpt-4o-mini", "gpt-4o"],
        verifier_models=["gpt-4o-mini", "gpt-4o"],
        synonym_count=3,
        antonym_count=3,
        threshold=0.5,
    )
    with pytest.raises(ExperimentConfigError, match="Live experiments require configured cloud LLM credentials"):
        validate_request(request, live_settings)


# ── 9. Mock execution cannot silently contaminate real evaluation results ───


def test_09_mock_execution_cannot_contaminate_real_evaluations() -> None:
    """Live experiments forbid mock model IDs to prevent mock contamination."""
    live_settings = Settings(
        llm_mode="live",
        openrouter_api_key="sk-valid-test-key",
        allowed_models="gpt-4o-mini,gpt-4o,model-a,model-b",
    )

    # Attempting to run mock model IDs in live mode is explicitly rejected
    request = ExperimentRunRequest(
        name="Contamination Test",
        dataset="pilot",
        generator_models=["model-a", "model-b"],
        verifier_models=["model-a", "model-b"],
        synonym_count=3,
        antonym_count=3,
        threshold=0.5,
    )
    with pytest.raises(ExperimentConfigError, match="Live experiments require supported cloud model names, not mock ids"):
        validate_request(request, live_settings)


# ── 10. Existing failure, malformed, uncertainty, and mixed-verdict tests ────


@pytest.mark.asyncio
async def test_10_existing_failure_malformed_uncertain_mixed_scenarios() -> None:
    """Verify uncertainty, mixed verdicts, failures, and malformed verifier output work deterministically."""
    # 1. Uncertain scenario: yields NOT SURE
    client_uncertain = MockLLMClient(scenario="uncertain")
    settings = detector_settings()
    res_unc = await run_detection(client_uncertain, question="What is the capital of Australia?", settings=settings)
    assert all(m.verdict == Verdict.NOT_SURE for m in res_unc.mutations)

    # 2. Mixed scenario: deterministic mixture
    client_mixed = MockLLMClient(scenario="mixed")
    res_mix = await run_detection(client_mixed, question="What is the capital of Australia?", settings=settings)
    verdict_types = {m.verdict for m in res_mix.mutations}
    assert len(verdict_types) > 1

    # 3. Simulated failure: answer generation
    client_fail_ans = MockLLMClient(fail_on="answer")
    with pytest.raises(LLMError, match="mock generator failure"):
        await client_fail_ans.complete_text(
            model="mock", system_prompt="", user_prompt="Question: What is 2 + 2?"
        )

    # 4. Simulated failure: verification
    client_fail_ver = MockLLMClient(fail_on="verify")
    with pytest.raises(LLMError, match="mock verifier failure"):
        await client_fail_ver.complete_json(
            model="mock", system_prompt="You judge statements.", user_prompt="Statement to judge:\nTest"
        )

    # 5. Malformed verifier response
    client_malformed = MockLLMClient(scenario="malformed_verifier")
    res_malformed = await client_malformed.complete_json(
        model="mock", system_prompt="You judge statements.", user_prompt="Statement to judge:\nTest"
    )
    assert res_malformed["verdict"] == "???"
