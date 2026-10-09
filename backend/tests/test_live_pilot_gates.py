from pathlib import Path

from fastapi.testclient import TestClient

from app.database.db import SessionLocal, init_db
from app.evaluation.dataset_loader import build_manifest, load_dataset
from app.experiment.analysis import category_analysis
from app.experiment.cost import estimate_evaluation_calls, estimate_experiment_calls
from app.llm.base import LLMError
from app.llm.instrumented import InstrumentedLLMClient
from app.llm.mock import MockLLMClient
from app.main import app
from app.schemas.experiment import ExperimentConfigError, ExperimentRunRequest
from app.services.experiment_service import run_experiment, validate_request
from tests.fakes import detector_settings


def test_experiment_call_estimate() -> None:
    estimate = estimate_experiment_calls(questions=40, mutations=10)
    assert estimate["calls_per_generator"] == 22
    assert estimate["calls_per_question"] == 44
    assert estimate["total_calls"] == 1760
    evaluation = estimate_evaluation_calls(questions=40, mutations=10)
    assert evaluation["calls_per_question"] == 12
    assert evaluation["total_calls"] == 480


def test_estimate_endpoint() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/experiments/estimate",
        json={"dataset": "pilot", "generator_models": ["model-a", "model-b"], "verifier_models": ["model-a", "model-b"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["questions"] == 40
    assert body["total_calls"] == 1760
    assert "api_key" not in response.text.lower()


def test_settings_endpoint_has_no_secrets() -> None:
    client = TestClient(app)
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["llm_mode"] == "mock"
    assert body["live_ready"] is False
    assert body["frozen_experiment_id"] == "58baff20-fb86-4f43-b20e-895a086ceb6b"
    assert "openai_api_key" not in body
    assert "api_key" not in body
    assert "replace-with" not in response.text


def test_live_rejects_missing_key() -> None:
    settings = detector_settings(
        llm_mode="live",
        gemini_api_key="",
        groq_api_key="",
        openrouter_api_key="",
        ollama_api_key="",
        cloudflare_api_token="",
    )
    payload = ExperimentRunRequest(generator_models=["gemma4:26b", "qwen-2.5-32b"], verifier_models=["gemma4:26b", "qwen-2.5-32b"])
    try:
        validate_request(payload, settings)
        raise AssertionError("expected ExperimentConfigError")
    except ExperimentConfigError as exc:
        assert "credentials" in str(exc).lower() or "configured" in str(exc).lower()


def test_live_rejects_mock_model_ids() -> None:
    settings = detector_settings(llm_mode="live", gemini_api_key="AIza-test-live-key")
    payload = ExperimentRunRequest()
    try:
        validate_request(payload, settings)
        raise AssertionError("expected ExperimentConfigError")
    except ExperimentConfigError as exc:
        assert "model names" in str(exc)


async def test_live_confirm_required_before_llm(tmp_path: Path) -> None:
    path = tmp_path / "mini.json"
    path.write_text(
        """{"name":"mini","version":"1.0","examples":[
          {"id":"q1","question":"Capital of France?","reference_answer":"Paris","category":"location","mock_base_answer":"Paris"},
          {"id":"q2","question":"Capital of Japan?","reference_answer":"Tokyo","category":"location","mock_base_answer":"Tokyo"}
        ]}""",
        encoding="utf-8",
    )
    init_db()
    db = SessionLocal()
    settings = detector_settings(llm_mode="live", gemini_api_key="AIza-test-live-key")
    try:
        await run_experiment(
            llm=MockLLMClient(),
            db=db,
            settings=settings,
            payload=ExperimentRunRequest(
                dataset=str(path),
                generator_models=["gemma4:26b", "qwen-2.5-32b"],
                verifier_models=["gemma4:26b", "qwen-2.5-32b"],
                confirm_live_run=False,
            ),
        )
        raise AssertionError("expected confirm gate")
    except ExperimentConfigError as exc:
        assert "confirm_live_run" in str(exc)
    finally:
        db.close()


async def test_max_questions_slices_dataset(tmp_path: Path) -> None:
    path = tmp_path / "mini.json"
    path.write_text(
        """{"name":"mini","version":"1.0","examples":[
          {"id":"q1","question":"Capital of France?","reference_answer":"Paris","category":"location","mock_base_answer":"Paris is the capital."},
          {"id":"q2","question":"Capital of Japan?","reference_answer":"Tokyo","category":"location","mock_base_answer":"Tokyo is the capital."}
        ]}""",
        encoding="utf-8",
    )
    init_db()
    db = SessionLocal()
    settings = detector_settings()
    try:
        experiment = await run_experiment(
            llm=MockLLMClient(),
            db=db,
            settings=settings,
            payload=ExperimentRunRequest(dataset=str(path), max_questions=1),
        )
        db.commit()
        assert experiment.status == "completed"
        assert len(experiment.generations) == 2
        parsed = __import__("json").loads(experiment.summary_stats_json)
        assert parsed["question_count"] == 1
        assert parsed["mutation_reuse_valid"] is True
        assert parsed["call_stats"]["success"] > 0
        hashes = {item.mutation_set_hash for item in experiment.generations}
        assert all(len(item) == 64 for item in hashes)
        for generation in experiment.generations:
            cond_hashes = {
                generation.mutation_set_hash
                for _ in generation.conditions
            }
            assert cond_hashes == {generation.mutation_set_hash}
    finally:
        db.close()


async def test_instrumented_client_counts_failure() -> None:
    class Boom(MockLLMClient):
        async def complete_text(self, **kwargs):
            raise LLMError("boom")

    client = InstrumentedLLMClient(Boom())
    try:
        await client.complete_text(model="x", system_prompt="s", user_prompt="u")
        raise AssertionError("expected LLMError")
    except LLMError:
        pass
    assert client.stats() == {"success": 0, "failed": 1, "total": 1}


def test_category_analysis_uses_saved_scores() -> None:
    paired = [
        {
            "question_id": "q1",
            "generator_model": "model-a",
            "same_model_score": 0.2,
            "cross_model_score": 0.8,
            "classification_flip": True,
        },
        {
            "question_id": "q2",
            "generator_model": "model-a",
            "same_model_score": 0.1,
            "cross_model_score": 0.2,
            "classification_flip": False,
        },
    ]
    rows = [
        {"question_id": "q1", "category": "location"},
        {"question_id": "q2", "category": "date"},
    ]
    result = category_analysis(paired, rows)
    by_cat = {item["category"]: item for item in result}
    assert by_cat["location"]["n"] == 1
    assert by_cat["location"]["score_difference"] == -0.6
    assert by_cat["location"]["flip_rate"] == 1.0
    assert by_cat["location"]["insufficient_data"] is True


def test_pilot_manifest_contains_evaluation_only_fields() -> None:
    bundle = load_dataset("pilot")
    manifest = build_manifest(bundle)
    assert manifest["dataset_name"] == "pilot"
    assert manifest["item_count"] == 40
    assert "Needs Review" in manifest["ground_truth_policy"]
    assert all("question_id" in item and "reference_answer" in item for item in manifest["items"])
    assert all(item["category"] in {"named_entity", "date", "numeric", "location", "general_fact"} for item in manifest["items"])
