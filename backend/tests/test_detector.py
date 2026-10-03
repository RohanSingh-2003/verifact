import pytest

from app.config import Settings
from app.llm.base import LLMError
from app.llm.mock import MockLLMClient, SCENARIO_VERDICTS
from app.llm.prompts import VERIFY_SYSTEM, VERIFY_USER
from app.metaqa.detector import MetaqaVerificationUnavailable, run_detection
from app.metaqa.scoring import Classification, MutationType, Verdict
from tests.fakes import detector_settings


def test_mock_client_has_deterministic_scenarios() -> None:
    assert len(SCENARIO_VERDICTS["reliable"]) == 10
    assert SCENARIO_VERDICTS["reliable"] == ["YES"] * 5 + ["NO"] * 5
    assert SCENARIO_VERDICTS["hallucinated"] == ["NO"] * 5 + ["YES"] * 5
    assert SCENARIO_VERDICTS["uncertain"] == ["NOT SURE"] * 10


async def test_mock_client_can_fail_on_answer() -> None:
    llm = MockLLMClient(fail_on="answer")
    try:
        await llm.complete_text(model="mock", system_prompt="", user_prompt="q")
        raise AssertionError("expected LLMError")
    except LLMError:
        pass


async def test_case_a_completely_reliable() -> None:
    result = await run_detection(
        MockLLMClient(scenario="reliable"),
        question="What is the capital of Australia?",
        settings=detector_settings(),
    )
    assert result.hallucination_score == 0.0
    assert result.classification is Classification.RELIABLE
    assert result.not_sure_rate == 0.0
    assert len(result.mutations) == 10
    assert result.llm_mode == "mock"


async def test_case_b_completely_hallucinated() -> None:
    result = await run_detection(
        MockLLMClient(scenario="hallucinated"),
        question="What is the capital of Australia?",
        settings=detector_settings(),
    )
    assert result.hallucination_score == 1.0
    assert result.classification is Classification.HALLUCINATED


async def test_case_c_all_uncertain() -> None:
    result = await run_detection(
        MockLLMClient(scenario="uncertain"),
        question="What is the capital of Australia?",
        settings=detector_settings(),
    )
    assert result.hallucination_score == 0.5
    assert result.classification is Classification.HALLUCINATED
    assert result.not_sure_rate == 1.0


async def test_case_d_mixed() -> None:
    result = await run_detection(
        MockLLMClient(scenario="mixed"),
        question="What is the capital of Australia?",
        settings=detector_settings(),
    )
    assert result.hallucination_score == 0.3
    assert result.classification is Classification.RELIABLE
    assert result.not_sure_rate == 0.2


async def test_case_e_malformed_verifier_response() -> None:
    with pytest.raises(MetaqaVerificationUnavailable):
        await run_detection(
            MockLLMClient(scenario="malformed_verifier"),
            question="What is the capital of Australia?",
            settings=detector_settings(),
        )


async def test_expected_verdicts_come_from_mutation_type() -> None:
    result = await run_detection(
        MockLLMClient(scenario="mixed"),
        question="What is the capital of Australia?",
        settings=detector_settings(),
    )
    for item in result.mutations:
        if item.mutation.type is MutationType.SYNONYM:
            assert item.expected is Verdict.YES
        else:
            assert item.expected is Verdict.NO


async def test_one_verifier_failure_does_not_abort_run() -> None:
    result = await run_detection(
        MockLLMClient(scenario="reliable", fail_verify_indices={3}),
        question="What is the capital of Australia?",
        settings=detector_settings(),
    )
    assert len(result.mutations) == 10
    assert result.mutations[3].verdict is None
    assert result.mutations[3].parse_failed is True
    assert result.mutations[3].unavailable is True
    assert result.mutations[0].verdict is Verdict.YES
    assert result.verified_count == 9
    assert result.metaqa_completion == "partial"


async def test_base_answer_failure_raises() -> None:
    try:
        await run_detection(
            MockLLMClient(fail_on="answer"),
            question="What is the capital of Australia?",
            settings=detector_settings(),
        )
        raise AssertionError("expected LLMError")
    except LLMError:
        pass


async def test_mutation_generation_failure_raises() -> None:
    try:
        await run_detection(
            MockLLMClient(fail_on="mutations"),
            question="What is the capital of Australia?",
            settings=detector_settings(),
        )
        raise AssertionError("expected LLMError")
    except LLMError:
        pass


def test_mock_settings_skip_model_allow_list() -> None:
    settings = Settings(llm_mode="mock", generator_model="not-an-allowed-model")
    assert settings.require_model("not-an-allowed-model") == "not-an-allowed-model"


def test_verifier_prompt_does_not_leak_metaqa_internals() -> None:
    combined = f"{VERIFY_SYSTEM}\n{VERIFY_USER}".lower()
    for leaked in (
        "synonym",
        "antonym",
        "expected verdict",
        "expected_verdict",
        "contribution",
        "hallucination score",
        "hallucination label",
        "metaqa scoring",
        "threshold",
        "ground truth",
        "reference answer",
        "reliable",
        "hallucinated",
    ):
        assert leaked not in combined
    assert "statement to judge:" in VERIFY_USER.lower()
    assert "{question}" in VERIFY_USER
    assert "{answer}" in VERIFY_USER
    assert "{statement}" in VERIFY_USER


async def test_live_verifier_calls_do_not_include_expected_or_ground_truth() -> None:
    llm = MockLLMClient(scenario="reliable")
    await run_detection(
        llm,
        question="What is the capital of Australia?",
        settings=detector_settings(),
    )
    verify_prompts = [
        prompt for prompt in llm.captured_user_prompts if "Statement to judge:" in prompt
    ]
    assert len(verify_prompts) == 10
    blob = "\n".join(verify_prompts).lower()
    for leaked in ("expected", "contribution", "hallucination", "ground truth", "reference answer"):
        assert leaked not in blob


# ── Regression tests: question-aware mock ──────────────────────────────


async def test_different_questions_produce_different_answers() -> None:
    """Different questions must produce different base answers (root cause regression)."""
    llm = MockLLMClient(scenario="mixed")
    settings = detector_settings()
    questions = [
        "Who formulated the three laws of motion?",
        "What is the capital of France?",
        "Who wrote Hamlet?",
        "What is 2 + 2?",
    ]
    answers: list[str] = []
    for question in questions:
        result = await run_detection(llm, question=question, settings=settings)
        answers.append(result.base_answer.text)
    # All answers must be distinct
    assert len(set(answers)) == len(questions), f"Expected {len(questions)} unique answers, got {answers}"


async def test_question_is_passed_to_generator() -> None:
    """The user's question must appear in the generator prompt."""
    llm = MockLLMClient(scenario="mixed")
    settings = detector_settings()
    result = await run_detection(
        llm,
        question="Who formulated the three laws of motion?",
        settings=settings,
    )
    assert result.question == "Who formulated the three laws of motion?"
    assert "Newton" in result.base_answer.text


async def test_mutations_use_current_base_answer() -> None:
    """Mutations must derive from the actual base answer, not a hardcoded constant."""
    llm = MockLLMClient(scenario="mixed")
    settings = detector_settings()
    result = await run_detection(
        llm,
        question="Who wrote Hamlet?",
        settings=settings,
    )
    assert "Shakespeare" in result.base_answer.text or "Hamlet" in result.base_answer.text
    for scored in result.mutations:
        # Each mutation's original_text must reference the actual base answer
        assert scored.mutation.original_text == result.base_answer.text, (
            f"Mutation original_text {scored.mutation.original_text!r} does not match "
            f"base answer {result.base_answer.text!r}"
        )


async def test_mock_generator_is_deterministic() -> None:
    """Same question must always produce the same answer."""
    settings = detector_settings()
    answers: list[str] = []
    for _ in range(3):
        llm = MockLLMClient(scenario="mixed")
        result = await run_detection(
            llm,
            question="What is the capital of France?",
            settings=settings,
        )
        answers.append(result.base_answer.text)
    assert len(set(answers)) == 1, f"Determinism violation: got {answers}"


async def test_metaqa_scoring_unchanged_after_fix() -> None:
    """MetaQA scoring rules must remain: synonym YES=0, NO=1, NOT_SURE=0.5; antonym YES=1, NO=0, NOT_SURE=0.5."""
    from app.metaqa.scoring import contribution_score, MutationType, Verdict
    assert contribution_score(MutationType.SYNONYM, Verdict.YES) == 0.0
    assert contribution_score(MutationType.SYNONYM, Verdict.NO) == 1.0
    assert contribution_score(MutationType.SYNONYM, Verdict.NOT_SURE) == 0.5
    assert contribution_score(MutationType.ANTONYM, Verdict.YES) == 1.0
    assert contribution_score(MutationType.ANTONYM, Verdict.NO) == 0.0
    assert contribution_score(MutationType.ANTONYM, Verdict.NOT_SURE) == 0.5


async def test_unknown_question_gets_mock_prefix() -> None:
    """An unknown question should return a '[MOCK]' prefixed answer, not the hardcoded Sydney string."""
    llm = MockLLMClient(scenario="mixed")
    settings = detector_settings()
    result = await run_detection(
        llm,
        question="What is the meaning of life?",
        settings=settings,
    )
    assert result.base_answer.text.startswith("[MOCK]")
    assert "What is the meaning of life?" in result.base_answer.text
    assert "Sydney" not in result.base_answer.text


# ── Hallucination fixture tests (Section 14) ───────────────────────────


async def test_hallucinated_answer_is_flagged_hallucinated() -> None:
    """A factually wrong answer should produce a high hallucination score.

    Fixture: 'What is the capital of Australia?' with answer 'Sydney is the
    capital of Australia.' using the 'hallucinated' scenario (synonyms→NO,
    antonyms→YES) which yields score=1.0.

    This is a TEST FIXTURE only — it does NOT use fact-checking rules.
    It relies purely on the MetaQA pipeline with deterministic mock verdicts.
    """
    llm = MockLLMClient(
        scenario="hallucinated",
        answers_by_question={
            "What is the capital of Australia?": "Sydney is the capital of Australia.",
        },
    )
    settings = detector_settings()
    result = await run_detection(
        llm,
        question="What is the capital of Australia?",
        settings=settings,
    )
    assert result.base_answer.text == "Sydney is the capital of Australia."
    assert result.hallucination_score == 1.0
    assert result.classification is Classification.HALLUCINATED


async def test_reliable_answer_is_flagged_reliable() -> None:
    """A factually correct answer should produce a low hallucination score.

    Fixture: 'What is the capital of Australia?' with answer 'Canberra is the
    capital of Australia.' using the 'reliable' scenario (synonyms→YES,
    antonyms→NO) which yields score=0.0.

    This is a TEST FIXTURE only — it does NOT use fact-checking rules.
    """
    llm = MockLLMClient(
        scenario="reliable",
        answers_by_question={
            "What is the capital of Australia?": "Canberra is the capital of Australia.",
        },
    )
    settings = detector_settings()
    result = await run_detection(
        llm,
        question="What is the capital of Australia?",
        settings=settings,
    )
    assert result.base_answer.text == "Canberra is the capital of Australia."
    assert result.hallucination_score == 0.0
    assert result.classification is Classification.RELIABLE


async def test_hallucinated_and_reliable_differ_for_same_question() -> None:
    """The same question with a wrong vs right answer must produce different
    classifications through the MetaQA pipeline.

    This verifies the detector can distinguish hallucinated from reliable
    answers purely through metamorphic verification, not fact-checking.
    """
    settings = detector_settings()

    # Hallucinated case
    llm_h = MockLLMClient(
        scenario="hallucinated",
        answers_by_question={
            "What is the capital of Australia?": "Sydney is the capital of Australia.",
        },
    )
    result_h = await run_detection(
        llm_h,
        question="What is the capital of Australia?",
        settings=settings,
    )

    # Reliable case
    llm_r = MockLLMClient(
        scenario="reliable",
        answers_by_question={
            "What is the capital of Australia?": "Canberra is the capital of Australia.",
        },
    )
    result_r = await run_detection(
        llm_r,
        question="What is the capital of Australia?",
        settings=settings,
    )

    assert result_h.classification is Classification.HALLUCINATED
    assert result_r.classification is Classification.RELIABLE
    assert result_h.hallucination_score > result_r.hallucination_score
    assert result_h.base_answer.text != result_r.base_answer.text


async def test_correct_answer_not_automatically_hallucinated() -> None:
    """A correct factual answer under the reliable scenario must score 0.0 and be Reliable."""
    llm = MockLLMClient(scenario="reliable")
    settings = detector_settings()
    result = await run_detection(
        llm,
        question="Who formulated the three laws of motion?",
        settings=settings,
    )
    assert result.base_answer.text == "Isaac Newton formulated the three laws of motion."
    assert result.hallucination_score == 0.0
    assert result.classification is Classification.RELIABLE
    # Every synonym must have contribution 0.0 and every antonym must have contribution 0.0
    for scored in result.mutations:
        assert scored.contribution == 0.0
        if scored.mutation.type == MutationType.SYNONYM:
            assert scored.verdict == Verdict.YES
            assert scored.expected == Verdict.YES
        else:
            assert scored.verdict == Verdict.NO
            assert scored.expected == Verdict.NO


async def test_mock_verifier_input_aware_semantic_discrimination() -> None:
    """The mock verifier must distinguish meaning-preserving from meaning-reversing statements."""
    from app.llm.mock import _is_meaning_reversing
    # Synonyms
    assert not _is_meaning_reversing("In other words, Isaac Newton formulated the laws of motion")
    assert not _is_meaning_reversing("Put simply, Paris is the capital of France")
    assert not _is_meaning_reversing("Australia's capital city is Sydney.")
    # Antonyms
    assert _is_meaning_reversing("It is not the case that Isaac Newton formulated the laws of motion")
    assert _is_meaning_reversing("Contrary to popular belief, Paris is not the capital")
    assert _is_meaning_reversing("This is false: 2 + 2 equals 4")
    assert _is_meaning_reversing("Actually, this claim is a misconception.")


async def test_mock_verifier_stateless_no_cross_contamination() -> None:
    """Running a hallucinated question must not leave the client stuck in hallucinated state for subsequent runs."""
    llm = MockLLMClient(
        scenario="reliable",
        scenarios_by_question={
            "What is the capital of Australia?": "hallucinated",
        },
    )
    settings = detector_settings()

    # Run 1: Hallucinated Australia
    res1 = await run_detection(llm, question="What is the capital of Australia?", settings=settings)
    assert res1.hallucination_score == 1.0
    assert res1.classification is Classification.HALLUCINATED

    # Run 2: Reliable Newton (must NOT inherit hallucinated scenario)
    res2 = await run_detection(llm, question="Who formulated the three laws of motion?", settings=settings)
    assert res2.hallucination_score == 0.0
    assert res2.classification is Classification.RELIABLE

    # Run 3: Reliable France
    res3 = await run_detection(llm, question="What is the capital of France?", settings=settings)
    assert res3.hallucination_score == 0.0
    assert res3.classification is Classification.RELIABLE
