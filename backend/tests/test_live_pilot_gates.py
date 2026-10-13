from fastapi.testclient import TestClient

from app.evaluation.dataset_loader import build_manifest, load_dataset
from app.evaluation.evaluator import estimate_evaluation_calls
from app.llm.base import LLMError
from app.llm.instrumented import InstrumentedLLMClient
from app.llm.mock import MockLLMClient
from app.main import app


def test_evaluation_call_estimate() -> None:
    evaluation = estimate_evaluation_calls(questions=40, mutations=10)
    assert evaluation["calls_per_question"] == 12
    assert evaluation["total_calls"] == 480


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


def test_pilot_manifest_contains_evaluation_only_fields() -> None:
    bundle = load_dataset("pilot")
    manifest = build_manifest(bundle)
    assert manifest["dataset_name"] == "pilot"
    assert manifest["item_count"] == 40
    assert "Needs Review" in manifest["ground_truth_policy"]
    assert all("question_id" in item and "reference_answer" in item for item in manifest["items"])
    assert all(item["category"] in {"named_entity", "date", "numeric", "location", "general_fact"} for item in manifest["items"])
