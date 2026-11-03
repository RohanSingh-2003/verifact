from __future__ import annotations

import json
from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.db import SessionLocal, init_db
from app.evaluation.evaluator import run_evaluation
from app.llm.base import LLMClient
from app.llm.mock import MockLLMClient
from app.metaqa.scoring import Classification
from app.schemas.detect import IndependentVerifierVerdict
from app.services.independent_verifiers import build_multi_model_summary
from tests.fakes import detector_settings


@pytest.fixture
def db_session() -> Session:
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_quorum_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "quorum_benchmark.json"
    data = {
        "name": "quorum_benchmark",
        "version": "1.0",
        "examples": [
            {
                "id": "q1",
                "question": "What is the capital of France?",
                "reference_answer": "Paris",
                "category": "location",
                "mock_base_answer": "Paris is the capital of France.",
                "mock_scenario": "reliable",
            },
            {
                "id": "q2",
                "question": "What is the capital of Germany?",
                "reference_answer": "Berlin",
                "category": "location",
                "mock_base_answer": "Berlin is the capital of Germany.",
                "mock_scenario": "reliable",
            },
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ── 1. Zero Successful Verifier Responses ─────────────────────────────────────

def test_zero_successful_verifier_responses() -> None:
    """When all verifiers fail/timeout, completed=0 and state is FAILED / Abstain."""
    verdicts = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="FAILED", status="failed", error="timeout"),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="FAILED", status="failed", error="503"),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="FAILED", status="failed", error="rate limit"),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="FAILED", status="failed", error="429"),
    ]
    summary = build_multi_model_summary(verdicts, min_quorum=2)
    assert summary.completed_verifiers == 0
    assert summary.failed_count == 4
    assert summary.agreement_state == "FAILED"
    assert summary.required_quorum == 2


# ── 2. Exactly One Successful Response (Insufficient Quorum) ──────────────────

def test_exactly_one_successful_response() -> None:
    """Single successful verifier must NEVER produce a decisive prediction."""
    verdicts = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="FAILED", status="failed", error="503"),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="FAILED", status="failed", error="timeout"),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="FAILED", status="failed", error="429"),
    ]
    summary = build_multi_model_summary(verdicts, min_quorum=2)
    assert summary.completed_verifiers == 1
    assert summary.correct_count == 1
    assert summary.failed_count == 3
    assert summary.agreement_state == "INSUFFICIENT_QUORUM"
    assert "Insufficient quorum: only 1 verifier(s) completed successfully" in summary.summary_text


# ── 3. Two Unanimous Correct Responses ────────────────────────────────────────

def test_two_unanimous_correct_responses() -> None:
    """Two unanimous Correct responses satisfy quorum and yield agreement."""
    verdicts = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="FAILED", status="failed", error="timeout"),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="FAILED", status="failed", error="429"),
    ]
    summary = build_multi_model_summary(verdicts, min_quorum=2)
    assert summary.completed_verifiers == 2
    assert summary.correct_count == 2
    assert summary.incorrect_count == 0
    assert summary.uncertain_count == 0
    assert summary.agreement_state == "AGREEMENT"
    assert summary.disagreements_detected is False


# ── 4. Two Unanimous Incorrect Responses ──────────────────────────────────────

def test_two_unanimous_incorrect_responses() -> None:
    """Two unanimous Incorrect responses satisfy quorum and yield agreement on hallucination."""
    verdicts = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="Incorrect", status="completed", contradictory_claims=["Wrong capital"]),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="Incorrect", status="completed", contradictory_claims=["Wrong capital"]),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="FAILED", status="failed", error="timeout"),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="FAILED", status="failed", error="429"),
    ]
    summary = build_multi_model_summary(verdicts, min_quorum=2)
    assert summary.completed_verifiers == 2
    assert summary.incorrect_count == 2
    assert summary.correct_count == 0
    assert summary.uncertain_count == 0
    assert summary.agreement_state == "AGREEMENT"
    assert summary.disagreements_detected is False
    assert "Wrong capital" in summary.contradictory_claims


# ── 5. Two Disagreeing Responses ──────────────────────────────────────────────

def test_two_disagreeing_responses() -> None:
    """Two completed models with 1 Correct and 1 Incorrect yield DISAGREEMENT."""
    verdicts = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="Incorrect", status="completed", contradictory_claims=["Wrong"]),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="FAILED", status="failed", error="timeout"),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="FAILED", status="failed", error="429"),
    ]
    summary = build_multi_model_summary(verdicts, min_quorum=2)
    assert summary.completed_verifiers == 2
    assert summary.correct_count == 1
    assert summary.incorrect_count == 1
    assert summary.agreement_state == "DISAGREEMENT"
    assert summary.disagreements_detected is True


# ── 6. One Correct and One Uncertain Response ─────────────────────────────────

def test_one_correct_and_one_uncertain_response() -> None:
    """1 Correct + 1 Uncertain does not satisfy consensus unanimity and yields UNCERTAIN."""
    verdicts = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="Uncertain", status="completed"),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="FAILED", status="failed", error="timeout"),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="FAILED", status="failed", error="429"),
    ]
    summary = build_multi_model_summary(verdicts, min_quorum=2)
    assert summary.completed_verifiers == 2
    assert summary.correct_count == 1
    assert summary.uncertain_count == 1
    assert summary.incorrect_count == 0
    assert summary.agreement_state == "UNCERTAIN"


# ── 7. Two Successful Responses with Remaining Models Failing ─────────────────

def test_two_successful_responses_with_remaining_models_failing() -> None:
    """Two successful responses meet quorum while tracking the failed models in telemetry."""
    verdicts = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="FAILED", status="failed", error="HTTP 429"),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="FAILED", status="failed", error="HTTP 429"),
    ]
    summary = build_multi_model_summary(verdicts, min_quorum=2)
    assert summary.completed_verifiers == 2
    assert summary.failed_count == 2
    assert summary.total_verifiers == 4
    assert summary.agreement_state == "AGREEMENT"
    assert "(2 verifier(s) unavailable or failed)" in summary.summary_text


# ── 8. Invalid or Malformed Responses Not Counting Toward Quorum ──────────────

def test_invalid_or_malformed_responses_not_counting_toward_quorum() -> None:
    """Malformed or parse-failed verdicts must NOT count as completed."""
    verdicts = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="FAILED", status="failed", error="Invalid JSON syntax"),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="UNKNOWN_VERDICT", status="failed", error="Unsupported verdict"),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="FAILED — Request timed out", status="failed", error="timeout"),
    ]
    summary = build_multi_model_summary(verdicts, min_quorum=2)
    # Only GLM is valid
    assert summary.completed_verifiers == 1
    assert summary.failed_count == 3
    assert summary.agreement_state == "INSUFFICIENT_QUORUM"


# ── 9. Configurable Quorum Behaviour ──────────────────────────────────────────

def test_configurable_quorum_behaviour() -> None:
    """Quorum threshold can be adjusted from default 2 to 3 or 4."""
    verdicts = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="FAILED", status="failed", error="timeout"),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="FAILED", status="failed", error="429"),
    ]
    # With min_quorum = 2 -> Met
    summary_q2 = build_multi_model_summary(verdicts, min_quorum=2)
    assert summary_q2.agreement_state == "AGREEMENT"

    # With min_quorum = 3 -> Insufficient
    summary_q3 = build_multi_model_summary(verdicts, min_quorum=3)
    assert summary_q3.agreement_state == "INSUFFICIENT_QUORUM"
    assert summary_q3.required_quorum == 3

    # With min_quorum = 1 -> Met (single model would suffice)
    summary_q1 = build_multi_model_summary(verdicts[:1], min_quorum=1)
    assert summary_q1.agreement_state == "AGREEMENT"
    assert summary_q1.required_quorum == 1


# ── 10. Existing Consensus Behaviour Unchanged When Quorum is Satisfied ───────

def test_existing_consensus_behaviour_when_quorum_is_satisfied() -> None:
    """When 3 or 4 models respond, majority consensus rules operate as expected."""
    # 3 responses: 2 Correct, 1 Incorrect -> Disagreement with 2 Correct majority
    verdicts_3 = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="Incorrect", status="completed", contradictory_claims=["Wrong fact"]),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="FAILED", status="failed", error="429"),
    ]
    summary_3 = build_multi_model_summary(verdicts_3, min_quorum=2)
    assert summary_3.completed_verifiers == 3
    assert summary_3.correct_count == 2
    assert summary_3.incorrect_count == 1
    assert summary_3.disagreements_detected is True
    assert summary_3.agreement_state == "DISAGREEMENT"

    # 4 responses: 4 Correct -> Unanimous agreement
    verdicts_4 = [
        IndependentVerifierVerdict(model_id="glm", model_name="GLM", provider="Cloudflare", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="qwen", model_name="Qwen", provider="Groq", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="phi", model_name="Phi", provider="OpenRouter", verdict="Correct", status="completed"),
        IndependentVerifierVerdict(model_id="openrouter", model_name="Liquid", provider="OpenRouter", verdict="Correct", status="completed"),
    ]
    summary_4 = build_multi_model_summary(verdicts_4, min_quorum=2)
    assert summary_4.completed_verifiers == 4
    assert summary_4.correct_count == 4
    assert summary_4.disagreements_detected is False
    assert summary_4.agreement_state == "AGREEMENT"


# ── 11. End-to-End Pipeline Quorum Enforcement & Abstention Tracking ──────────

@pytest.mark.asyncio
async def test_pipeline_quorum_enforcement_and_abstention(tmp_path: Path, monkeypatch, db_session: Session) -> None:
    """Evaluation pipeline marks insufficient quorum as abstained with no decisive prediction."""
    dataset_path = create_quorum_dataset(tmp_path)
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)

    # Mock LLM that fails for 3 models and succeeds for only 1 model
    class PartialFailureLLM(MockLLMClient):
        async def complete_json(self, *, model: str, system_prompt: str, user_prompt: str, max_tokens: int | None = None):
            if "independent AI verifier" in system_prompt.lower() or "Generated Answer to evaluate:" in user_prompt:
                # Only let "glm-4.7-flash" succeed; fail all others
                if "glm" in model.lower():
                    return {"verdict": "Correct", "reasoning": "Accurate.", "contradictory_claims": [], "confidence": 0.9}
                from app.llm.base import LLMError
                raise LLMError(f"Simulated rate limit for model {model}")
            return await super().complete_json(model=model, system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens)

    settings = detector_settings()
    settings.llm_mode = "mock"
    settings.min_completed_verifiers = 2

    run = await run_evaluation(
        llm=PartialFailureLLM(),
        db=db_session,
        settings=settings,
        dataset=str(dataset_path),
        threshold=0.5,
        evaluate_web_evidence=False,
        evaluate_multi_model=True,
        min_completed_verifiers=2,
        persist_traces=False,
    )
    db_session.commit()

    assert run.status == "completed"
    assert len(run.results) == 2

    for row in run.results:
        # Crucial: With only 1 completed verifier and quorum=2, multi_pred MUST be None
        assert row.multi_model_prediction is None
        assert row.multi_model_status == "insufficient_quorum"
        assert row.multi_model_consensus == "INSUFFICIENT_QUORUM"
        assert row.multi_model_outcome == "Abstained"

        details = json.loads(row.component_details_json)
        mm = details["multi_model"]
        assert mm["completed_verifiers"] == 1
        assert mm["required_quorum"] == 2
        assert mm["multi_model_abstained"] is True
        assert mm["prediction"] is None

    # Verify summary metrics show 100% abstention and 0.0 coverage for multi_model
    summary = json.loads(run.summary_metrics_json)
    mm_summary = summary["multi_model"]
    assert mm_summary["coverage"] == 0.0
    assert mm_summary["abstained_examples"] == 2
    assert mm_summary["required_quorum"] == 2

