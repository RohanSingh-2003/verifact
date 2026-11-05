from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.db import SessionLocal, init_db
from app.database.models import EvaluationResult, EvaluationRun, HumanAnnotation
from app.evaluation.agreement import (
    compute_cohens_kappa,
    compute_judge_human_agreement,
)
from app.evaluation.evaluator import run_evaluation
from app.evaluation.gemini_judge import (
    GeminiJudgeClient,
)
from app.evaluation.ground_truth import resolve_ground_truth
from app.evaluation.schemas import DatasetExample, GroundTruthSource
from app.llm.base import (
    LLMClient,
    LLMError,
    LLMMalformedResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.mock import MockLLMClient
from app.llm.registry import get_verifier_pool, validate_answer_model
from app.metaqa.scoring import Classification
from app.services.verification_summary import (
    MetaqaSignal,
    OverallVerdict,
    WebSignal,
    compute_overall_assessment,
)
from app.web_evidence.types import EvidenceVerdict, VerifiedClaim, WebEvidenceResult, WebEvidenceStatus
from tests.fakes import detector_settings


@pytest.fixture
def eval_db() -> Session:
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_judge_test_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "judge_benchmark.json"
    data = {
        "name": "judge_benchmark",
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
                "mock_base_answer": "Munich is the capital of Germany.",
                "mock_scenario": "hallucinated",
            },
            {
                "id": "q3",
                "question": "Ambiguous history query?",
                "reference_answer": "Unknown",
                "category": "general_fact",
                "needs_review": True,
                "mock_base_answer": "Some disputed historical claim.",
                "mock_scenario": "uncertain",
            },
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ── 1. OpenRouter Client Configuration ───────────────────────────────────────

def test_gemini_judge_client_configuration() -> None:
    """Configured with custom model, API key, base URL, and timeout settings."""
    client = GeminiJudgeClient(
        api_key="test-openrouter-key",
        model="google/gemini-2.5-pro",
        base_url="https://openrouter.ai/api/v1",
        timeout_seconds=45.0,
    )
    assert client.is_available is True
    assert client._model == "google/gemini-2.5-pro"
    assert client._base_url == "https://openrouter.ai/api/v1"
    assert client._timeout_seconds == 45.0

    # Also verify configuration from Settings
    settings = detector_settings(
        openrouter_api_key="sk-or-v1-test",
        ground_truth_judge_model="google/gemini-2.5-pro",
        ground_truth_judge_enabled=True,
    )
    from_settings = GeminiJudgeClient(settings=settings)
    assert from_settings.is_available is True
    assert from_settings._model == "google/gemini-2.5-pro"
    assert from_settings._api_key == "sk-or-v1-test"
    assert from_settings._base_url == "https://openrouter.ai/api/v1"


# ── 2. Missing API Key ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gemini_judge_missing_api_key_reports_unavailable() -> None:
    """Missing API key returns status='unavailable' without crashing or falling back."""
    client = GeminiJudgeClient(api_key="", model="google/gemini-2.5-pro")
    assert client.is_available is False

    verdict = await client.evaluate_answer(
        question="What is 2+2?",
        generated_answer="4",
        reference_answer="4",
    )
    assert verdict.status == "unavailable"
    assert verdict.label == "NEEDS_REVIEW"
    assert "OPENROUTER_API_KEY is not configured" in (verdict.error or "")


# ── 3. Missing Model & Automatic Routing Forbidden ───────────────────────────

@pytest.mark.asyncio
async def test_gemini_judge_missing_model_and_auto_routing_forbidden() -> None:
    """Missing model marks unavailable, and 'openrouter/auto' is strictly forbidden."""
    # Missing model
    no_model = GeminiJudgeClient(api_key="test-key", model="")
    assert no_model.is_available is False
    v1 = await no_model.evaluate_answer(
        question="What is 2+2?",
        generated_answer="4",
        reference_answer="4",
    )
    assert v1.status == "unavailable"
    assert "GROUND_TRUTH_JUDGE_MODEL is not configured" in (v1.error or "")

    # 'openrouter/auto' forbidden
    auto_model = GeminiJudgeClient(api_key="test-key", model="openrouter/auto")
    v2 = await auto_model.evaluate_answer(
        question="What is 2+2?",
        generated_answer="4",
        reference_answer="4",
    )
    assert v2.status == "failed"
    assert "Automatic model routing ('openrouter/auto') is forbidden" in (v2.error or "")


class BaseMockJudgeLLM(LLMClient):
    async def complete_text(self, *args, **kwargs) -> str:
        return ""

    async def complete_json(self, *args, **kwargs) -> dict:
        return {}


# ── 4. Successful Structured Judge Response ───────────────────────────────────

@pytest.mark.asyncio
async def test_gemini_judge_successful_structured_response() -> None:
    """Gemini judge parses supported claims, contradicted claims, evidence, and label."""
    class MockJudgeLLM(BaseMockJudgeLLM):
        async def complete_json(self, **kwargs):
            return {
                "label": "RELIABLE",
                "reasoning_summary": "Generated answer matches historical evidence.",
                "supported_claims": ["Alexander Fleming discovered penicillin in 1928."],
                "contradicted_claims": [],
                "unsupported_claims": [],
                "evidence_used": ["Fleming's 1928 laboratory notes at St. Mary's Hospital."],
                "confidence": 0.98,
            }

    judge = GeminiJudgeClient(test_llm=MockJudgeLLM())
    verdict = await judge.evaluate_answer(
        question="Who discovered penicillin?",
        generated_answer="Alexander Fleming discovered penicillin in 1928.",
        reference_answer="Alexander Fleming",
        aliases=["Fleming"],
    )
    assert verdict.status == "completed"
    assert verdict.label == "RELIABLE"
    assert len(verdict.supported_claims) == 1
    assert verdict.confidence == 0.98
    assert "Fleming's 1928" in verdict.evidence_used[0]


# ── 5. OpenRouter OpenAI-Compatible Request Verification ──────────────────────

@pytest.mark.asyncio
async def test_gemini_judge_openrouter_openai_compatible_http_request() -> None:
    """Verifies OpenRouter client formats OpenAI-compatible JSON payload without live credits."""
    recorded_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "google/gemini-2.5-pro"
        assert body["response_format"] == {"type": "json_object"}
        assert any(msg["role"] == "system" for msg in body["messages"])
        assert any(msg["role"] == "user" for msg in body["messages"])
        return httpx.Response(
            status_code=200,
            json={
                "id": "gen-12345",
                "model": "google/gemini-2.5-pro",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "label": "RELIABLE",
                                "reasoning_summary": "Tokyo is the verified capital of Japan.",
                                "supported_claims": ["Tokyo is the capital of Japan."],
                                "contradicted_claims": [],
                                "unsupported_claims": [],
                                "evidence_used": ["Official government records."],
                                "confidence": 0.97,
                            }),
                        }
                    }
                ],
            },
        )

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=transport, base_url="https://openrouter.ai/api/v1")

    with patch("app.llm.providers.httpx.AsyncClient", return_value=mock_client):
        judge = GeminiJudgeClient(
            api_key="test-openrouter-key",
            model="google/gemini-2.5-pro",
            base_url="https://openrouter.ai/api/v1",
        )
        verdict = await judge.evaluate_answer(
            question="What is the capital of Japan?",
            generated_answer="Tokyo is Japan's capital.",
            reference_answer="Tokyo",
        )
        assert verdict.status == "completed"
        assert verdict.label == "RELIABLE"
        assert verdict.confidence == 0.97
        assert len(recorded_requests) == 1
        assert recorded_requests[0].headers["Authorization"] == "Bearer test-openrouter-key"
        assert recorded_requests[0].headers["HTTP-Referer"] == "https://verifact.local"
        assert recorded_requests[0].headers["X-Title"] == "VeriFact"


# ── 6. Malformed JSON Response ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gemini_judge_malformed_json_handling() -> None:
    """Malformed JSON response safely yields status='failed' and label='NEEDS_REVIEW'."""
    class BrokenJSONJudgeLLM(BaseMockJudgeLLM):
        async def complete_json(self, **kwargs):
            raise LLMMalformedResponseError("Unterminated string in JSON")

    judge = GeminiJudgeClient(test_llm=BrokenJSONJudgeLLM())
    verdict = await judge.evaluate_answer(
        question="What is gravity?",
        generated_answer="A fundamental interaction.",
        reference_answer="Fundamental interaction",
    )
    assert verdict.status == "failed"
    assert verdict.label == "NEEDS_REVIEW"
    assert "Malformed JSON" in (verdict.error or "")


# ── 7. Invalid Label Handled as NEEDS_REVIEW ──────────────────────────────────

@pytest.mark.asyncio
async def test_gemini_judge_invalid_label_handling() -> None:
    """Unrecognized label string from model is rejected and marked NEEDS_REVIEW."""
    class InvalidLabelJudgeLLM(BaseMockJudgeLLM):
        async def complete_json(self, **kwargs):
            return {
                "label": "SOME_UNKNOWN_LABEL",
                "reasoning_summary": "I am not sure.",
            }

    judge = GeminiJudgeClient(test_llm=InvalidLabelJudgeLLM())
    verdict = await judge.evaluate_answer(
        question="What is dark matter?",
        generated_answer="Hypothetical form of matter.",
        reference_answer="Hypothetical matter",
    )
    assert verdict.status == "failed"
    assert verdict.label == "NEEDS_REVIEW"
    assert "Invalid judge label" in (verdict.error or "")


# ── 8. OpenRouter API Timeout ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gemini_judge_api_timeout() -> None:
    """Timeout returns status='failed' and does not crash."""
    class TimeoutJudgeLLM(BaseMockJudgeLLM):
        async def complete_json(self, **kwargs):
            raise LLMTimeoutError("Request exceeded 30s deadline")

    judge = GeminiJudgeClient(test_llm=TimeoutJudgeLLM())
    verdict = await judge.evaluate_answer(
        question="What is entropy?",
        generated_answer="A measure of molecular disorder.",
        reference_answer="Measure of disorder",
    )
    assert verdict.status == "failed"
    assert verdict.label == "NEEDS_REVIEW"
    assert "timed out" in verdict.reasoning_summary.lower() or "timed out" in (verdict.error or "").lower()


# ── 9. OpenRouter Rate-Limit (HTTP 429) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_gemini_judge_rate_limit_failure() -> None:
    """HTTP 429 returns status='failed' and label='NEEDS_REVIEW'."""
    class RateLimitedJudgeLLM(BaseMockJudgeLLM):
        async def complete_json(self, **kwargs):
            raise LLMRateLimitError("Quota exceeded 429")

    judge = GeminiJudgeClient(test_llm=RateLimitedJudgeLLM())
    verdict = await judge.evaluate_answer(
        question="What is the speed of sound?",
        generated_answer="343 m/s in air at 20 C.",
        reference_answer="343 m/s",
    )
    assert verdict.status == "failed"
    assert verdict.label == "NEEDS_REVIEW"
    assert "rate limit" in verdict.reasoning_summary.lower() or "rate limit" in (verdict.error or "").lower()


# ── 10. No Silent Fallback to Gemma or Other Verifiers ────────────────────────

@pytest.mark.asyncio
async def test_no_silent_fallback_to_gemma_or_other_verifiers() -> None:
    """When Gemini judge fails, it NEVER calls Gemma or independent verifier models."""
    calls: list[str] = []

    class FailingJudgeLLM(BaseMockJudgeLLM):
        async def complete_json(self, *, model: str = "", **kwargs):
            calls.append(model)
            raise LLMError("OpenRouter Gemini service unavailable")

    judge = GeminiJudgeClient(model="google/gemini-2.5-pro", test_llm=FailingJudgeLLM())
    verdict = await judge.evaluate_answer(
        question="What is absolute zero?",
        generated_answer="-273.15 C",
        reference_answer="-273.15 degrees Celsius",
    )
    # Exactly one call was attempted, specifically for google/gemini-2.5-pro
    assert calls == ["google/gemini-2.5-pro"]
    assert verdict.status == "failed"
    assert verdict.label == "NEEDS_REVIEW"


# ── 11. NEEDS_REVIEW Handling in Ground Truth ─────────────────────────────────

def test_needs_review_handling_in_ground_truth() -> None:
    """Items flagged needs_review are excluded from decisive metrics in both modes."""
    ex = DatasetExample(
        id="q_ambig",
        question="Was King Arthur a real historical figure?",
        reference_answer="Disputed",
        needs_review=True,
    )
    # Formal mode
    dec_formal = resolve_ground_truth("Arthur ruled Britain in the 5th century.", ex, mode="formal")
    assert dec_formal.is_review is True
    assert dec_formal.label is None
    assert dec_formal.source == GroundTruthSource.NEEDS_REVIEW

    # Legacy mode
    dec_legacy = resolve_ground_truth("Arthur ruled Britain in the 5th century.", ex, mode="legacy")
    assert dec_legacy.is_review is True
    assert dec_legacy.label is None
    assert dec_legacy.source == GroundTruthSource.NEEDS_REVIEW


# ── 12. Formal Evaluation Requires Validated Labels ───────────────────────────

def test_formal_evaluation_requires_validated_labels_no_substring_matching() -> None:
    """Formal mode NEVER infers labels via string matching; requires explicit validated labels."""
    ex = DatasetExample(
        id="q_unvalidated",
        question="What is the capital of Canada?",
        reference_answer="Ottawa",
        aliases=["City of Ottawa"],
        ground_truth_label=None,  # No explicit validated label
    )
    # In legacy mode, it matches "Ottawa"
    legacy_dec = resolve_ground_truth("Ottawa is the capital.", ex, mode="legacy")
    assert legacy_dec.label == Classification.RELIABLE
    assert legacy_dec.source in (GroundTruthSource.LEGACY_INFERRED, GroundTruthSource.REFERENCE_MATCH)

    # In formal mode, it strictly REFUSES string matching and marks UNVALIDATED
    formal_dec = resolve_ground_truth("Ottawa is the capital.", ex, mode="formal")
    assert formal_dec.label is None
    assert formal_dec.source == GroundTruthSource.UNVALIDATED
    assert "Formal benchmark mode requires an explicit validated ground-truth label" in formal_dec.notes

    # When explicit validated label is provided, formal mode accepts it
    ex_validated = DatasetExample(
        id="q_validated",
        question="What is the capital of Canada?",
        reference_answer="Ottawa",
        ground_truth_label=Classification.RELIABLE,
    )
    formal_val_dec = resolve_ground_truth("Ottawa is the capital.", ex_validated, mode="formal")
    assert formal_val_dec.label == Classification.RELIABLE
    assert formal_val_dec.source in (GroundTruthSource.VALIDATED, GroundTruthSource.MANUAL)


# ── 13. Legacy Fallback Compatibility ─────────────────────────────────────────

def test_legacy_fallback_compatibility() -> None:
    """Legacy mode preserves fallback normalized reference matching for standalone examples."""
    ex_correct = DatasetExample(
        id="q_legacy_1",
        question="What is the capital of France?",
        reference_answer="Paris",
        aliases=["City of Paris"],
    )
    dec = resolve_ground_truth("Paris is France's capital city.", ex_correct, mode="legacy")
    assert dec.label == Classification.RELIABLE
    assert dec.source in (GroundTruthSource.LEGACY_INFERRED, GroundTruthSource.REFERENCE_MATCH)

    ex_incorrect = DatasetExample(
        id="q_legacy_2",
        question="What is the capital of Australia?",
        reference_answer="Canberra",
    )
    dec_inc = resolve_ground_truth("Sydney is the capital of Australia.", ex_incorrect, mode="legacy")
    assert dec_inc.label == Classification.HALLUCINATED
    assert dec_inc.source in (GroundTruthSource.LEGACY_INFERRED, GroundTruthSource.REFERENCE_MATCH)


# ── 14. Human Annotation Persistence, Disagreement, and Adjudication ─────────

def test_human_annotation_persistence_disagreement_and_cohens_kappa(eval_db: Session) -> None:
    """Human annotations track Reviewer 1, Reviewer 2, disagreements, and Cohen's kappa."""
    run = EvaluationRun(
        id="test-run-annot",
        name="test_evaluation_run",
        dataset_name="test_dataset",
        dataset_version="1.0",
        generator_model="gemma:4:26b",
        verifier_model="glm-4.7-flash",
        threshold=0.5,
    )
    eval_db.add(run)
    res = EvaluationResult(
        id="res-1",
        evaluation_run_id="test-run-annot",
        question_id="q1",
        question="What is the capital of Australia?",
        reference_answer="Canberra",
        generated_answer="Canberra is the capital.",
        actual_label="RELIABLE",
        predicted_label="RELIABLE",
        hallucination_score=0.0,
        outcome="true_negative",
    )
    eval_db.add(res)
    eval_db.commit()

    annotation = HumanAnnotation(
        evaluation_result_id="res-1",
        evaluation_run_id="test-run-annot",
        question_id="q1",
        question="What is the capital of Australia?",
        reference_answer="Canberra",
        generated_answer="Canberra is the capital.",
        judge_label="RELIABLE",
        reviewer1_id="alice",
        reviewer1_label="RELIABLE",
        reviewer2_id="bob",
        reviewer2_label="HALLUCINATED",  # Disagreement!
        disagreement=True,
        validation_status="reviewed",
    )
    eval_db.add(annotation)
    eval_db.commit()

    # Adjudication resolves the disagreement
    annotation.adjudicated_label = "RELIABLE"
    annotation.adjudicator_id = "senior_researcher"
    annotation.adjudication_notes = "Canberra is indeed the capital city."
    annotation.validation_status = "adjudicated"
    eval_db.commit()

    loaded = eval_db.scalar(select(HumanAnnotation).where(HumanAnnotation.evaluation_result_id == "res-1"))
    assert loaded is not None
    assert loaded.disagreement is True
    assert loaded.adjudicated_label == "RELIABLE"
    assert loaded.validation_status == "adjudicated"

    # Test Cohen's kappa agreement calculation
    r1 = ["RELIABLE", "RELIABLE", "HALLUCINATED", "HALLUCINATED", "NEEDS_REVIEW"]
    r2 = ["RELIABLE", "HALLUCINATED", "HALLUCINATED", "HALLUCINATED", "NEEDS_REVIEW"]
    kappa = compute_cohens_kappa(r1, r2)
    assert kappa is not None
    assert 0.0 <= kappa <= 1.0

    # Test Judge vs Human agreement calculation
    judge_labels = ["RELIABLE", "RELIABLE", "HALLUCINATED", "HALLUCINATED"]
    human_labels = ["RELIABLE", "HALLUCINATED", "HALLUCINATED", "HALLUCINATED"]
    stats = compute_judge_human_agreement(judge_labels, human_labels)
    assert stats["total_pairs"] == 4
    assert stats["observed_agreement"] == 0.75


# ── 15. Gemini Remains Outside the Detection Pipeline ─────────────────────────

def test_gemini_remains_completely_outside_detection_pipeline() -> None:
    """Gemini is NEVER added to MODEL_REGISTRY, verifier pool, or detection flow."""
    # Gemma is the only generator
    assert validate_answer_model("gemma") == "gemma"

    # Verifier pool consists only of GLM, Qwen, OpenRouter/Liquid, Phi
    verifier_pool = get_verifier_pool("gemma", detector_settings())
    pool_ids = {v["id"] for v in verifier_pool}
    assert "gemini" not in pool_ids
    assert pool_ids == {"glm", "qwen", "openrouter", "phi"}


# ── 16. Existing MetaQA, Web Evidence, Quorum, and Combined Scoring Unchanged ──

def test_existing_metaqa_web_quorum_combined_scoring_unchanged() -> None:
    """All existing scoring formulas and fusion invariants remain intact."""
    # Fused combined risk remains 0.5 * H + 0.5 * (1 - W)
    claim_supp = VerifiedClaim(id="c1", text="text", search_query="q", verdict=EvidenceVerdict.SUPPORTED, reason="r")
    verdict, _, _, _, comb_risk, web_risk = compute_overall_assessment(
        metaqa_signal=MetaqaSignal.CONSISTENT,
        metaqa_score=0.20,
        web_signal=WebSignal.SUPPORTED,
        web_evidence=WebEvidenceResult(status=WebEvidenceStatus.COMPLETED, claims=[claim_supp], consistency_score=0.80),
    )
    assert verdict == OverallVerdict.LIKELY_RELIABLE
    assert web_risk == 0.20
    assert comb_risk == 0.20  # 0.5 * 0.20 + 0.5 * 0.20 = 0.20


# ── 17. Evaluation Run with Gemini Judge Telemetry Persistence ────────────────

@pytest.mark.asyncio
async def test_evaluation_run_with_gemini_judge_records_telemetry(eval_db: Session, tmp_path, monkeypatch) -> None:
    """Legacy evaluation run executes Gemini judge and records structured telemetry in results when requested."""
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)
    class MockJudgeLLM(BaseMockJudgeLLM):
        async def complete_json(self, **kwargs):
            return {
                "label": "RELIABLE",
                "reasoning_summary": "Generated text matches known facts.",
                "supported_claims": ["Known fact."],
                "contradicted_claims": [],
                "unsupported_claims": [],
                "evidence_used": ["Reference benchmark."],
                "confidence": 0.95,
            }

    mini_path = tmp_path / "mock_judge_eval.json"
    mini_path.write_text(
        json.dumps({
            "name": "mock_judge_eval",
            "version": "1.0",
            "examples": [
                {"id": "q1", "question": "What is 2+2?", "reference_answer": "4", "category": "math"},
                {"id": "q2", "question": "What is the capital of France?", "reference_answer": "Paris", "category": "geo"},
            ]
        }),
        encoding="utf-8"
    )

    judge = GeminiJudgeClient(model="google/gemini-2.5-pro", test_llm=MockJudgeLLM())
    run = await run_evaluation(
        llm=MockLLMClient(),
        db=eval_db,
        settings=detector_settings(
            llm_mode="mock",
            openrouter_api_key="sk-or-test-key",
            ground_truth_judge_model="google/gemini-2.5-pro",
        ),
        dataset=str(mini_path),
        max_questions=2,
        evaluate_judge=True,
        judge_client=judge,
        benchmark_mode="legacy",
        evaluate_web_evidence=False,
        evaluate_multi_model=False,
    )

    assert run.total_examples == 2
    judge_results = [r for r in run.results if r.judge_label is not None]
    assert len(judge_results) == 2
    assert judge_results[0].judge_label == "RELIABLE"
    assert judge_results[0].judge_confidence == 0.95
    details = json.loads(judge_results[0].component_details_json)
    assert details.get("gemini_judge") is not None
    assert details["gemini_judge"]["status"] == "completed"


@pytest.mark.asyncio
async def test_formal_benchmark_strictly_disables_gemini_judge(eval_db: Session) -> None:
    """Formal benchmark evaluation strictly disables Gemini judge execution and telemetry."""
    class FailIfCalledJudgeLLM(BaseMockJudgeLLM):
        async def complete_json(self, **kwargs):
            raise AssertionError("Gemini judge must NEVER be called during formal benchmark evaluation!")

    judge = GeminiJudgeClient(model="google/gemini-2.5-pro", test_llm=FailIfCalledJudgeLLM())
    run = await run_evaluation(
        llm=MockLLMClient(),
        db=eval_db,
        settings=detector_settings(
            llm_mode="mock",
            openrouter_api_key="sk-or-test-key",
            ground_truth_judge_model="google/gemini-2.5-pro",
            ground_truth_judge_enabled=True,
        ),
        dataset="hallucination_benchmark_frozen",
        split="test",
        max_questions=3,
        evaluate_judge=True,  # Even when explicitly requested, formal benchmark must disallow judge
        judge_client=judge,
        evaluate_web_evidence=False,
        evaluate_multi_model=False,
    )

    assert run.total_examples == 3
    for r in run.results:
        assert r.judge_status == "disabled_in_formal_eval"
        assert r.judge_label is None
        assert r.judge_confidence is None
        details = json.loads(r.component_details_json)
        assert details.get("gemini_judge") is None


# ── 18. Human Annotation REST Endpoints ────────────────────────────────────────

def test_annotation_routes_endpoints(eval_db: Session) -> None:
    """Annotation endpoints support creation, double-review updates, and agreement calculation."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    run = EvaluationRun(
        id="run-api-test-1",
        name="api_test_run",
        dataset_name="test_dataset",
        dataset_version="1.0",
        generator_model="gemma:4:26b",
        verifier_model="glm-4.7-flash",
        threshold=0.5,
    )
    eval_db.add(run)
    res = EvaluationResult(
        id="res-api-test-1",
        evaluation_run_id="run-api-test-1",
        question_id="q_paris",
        question="What is the capital of France?",
        reference_answer="Paris",
        generated_answer="Paris is the capital of France.",
        actual_label="RELIABLE",
        predicted_label="RELIABLE",
        hallucination_score=0.0,
        outcome="true_negative",
    )
    eval_db.add(res)
    eval_db.commit()

    # 1. Create annotation
    resp_create = client.post("/api/annotations/", json={
        "evaluation_result_id": "res-api-test-1",
        "question_id": "q_paris",
        "question": "What is the capital of France?",
        "reference_answer": "Paris",
        "generated_answer": "Paris is the capital of France.",
        "judge_label": "RELIABLE",
        "reviewer1_id": "annotator_1",
        "reviewer1_label": "RELIABLE",
    })
    assert resp_create.status_code == 201
    annot_data = resp_create.json()
    annot_id = annot_data["id"]
    assert annot_data["reviewer1_label"] == "RELIABLE"
    assert annot_data["disagreement"] is False

    # 2. Add second reviewer with disagreement
    resp_patch = client.patch(f"/api/annotations/{annot_id}", json={
        "reviewer2_id": "annotator_2",
        "reviewer2_label": "HALLUCINATED",
    })
    assert resp_patch.status_code == 200
    updated_data = resp_patch.json()
    assert updated_data["reviewer2_label"] == "HALLUCINATED"
    assert updated_data["disagreement"] is True
    assert updated_data["validation_status"] == "reviewed"

    # 3. Adjudicate
    resp_adj = client.patch(f"/api/annotations/{annot_id}", json={
        "adjudicated_label": "RELIABLE",
        "adjudicator_id": "senior_researcher",
        "adjudication_notes": "France capital is definitely Paris.",
    })
    assert resp_adj.status_code == 200
    adj_data = resp_adj.json()
    assert adj_data["adjudicated_label"] == "RELIABLE"
    assert adj_data["validation_status"] == "adjudicated"

    # 4. Check agreement endpoint
    resp_agree = client.get("/api/annotations/agreement")
    assert resp_agree.status_code == 200
    agree_data = resp_agree.json()
    assert agree_data["both_reviewed_count"] >= 1
    assert agree_data["disagreements_count"] >= 1
    assert agree_data["adjudicated_count"] >= 1
