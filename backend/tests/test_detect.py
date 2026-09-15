from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_llm_client
from app.llm.base import LLMClient, LLMTimeoutError
from app.llm.mock import MockLLMClient
from app.main import app
from app.metaqa.scoring import MutationType, Verdict, expected_verdict


def _client(fake: MockLLMClient) -> TestClient:
    app.dependency_overrides[get_llm_client] = lambda: fake
    return TestClient(app)


def test_detect_case_a_with_mocked_llm() -> None:
    fake = MockLLMClient(scenario="reliable")
    client = _client(fake)
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        body = response.json()
        assert body["question"] == "What is the capital of Australia?"
        assert body["base_answer"]["text"] == fake.answer
        assert len(body["mutations"]) == 10
        assert body["hallucination_score"] == 0.0
        assert body["classification"] == "Reliable"
        assert body["not_sure_rate"] == 0.0
        assert body["threshold"] == 0.5
        assert body["llm_mode"] == "mock"
        assert isinstance(body["hallucination_score"], (int, float))
        assert isinstance(body["not_sure_rate"], (int, float))
        run_id = body["run_id"]

        listed = client.get("/api/runs")
        assert listed.status_code == 200
        assert listed.json()["total"] >= 1
        assert any(item["id"] == run_id for item in listed.json()["items"])

        detail = client.get(f"/api/runs/{run_id}")
        assert detail.status_code == 200
        reconstructed = detail.json()
        assert reconstructed["run_id"] == run_id
        assert reconstructed["hallucination_score"] == 0.0
        assert len(reconstructed["mutations"]) == 10
        assert [item["mutated_text"] for item in reconstructed["mutations"]] == [
            item["mutated_text"] for item in body["mutations"]
        ]
        for item in reconstructed["mutations"]:
            assert item["id"]
            assert item["type"] in {"synonym", "antonym"}
            assert item["original_text"]
            assert item["mutated_text"]
            assert item["verdict"] in {"YES", "NO", "NOT SURE"}
            assert item["expected_verdict"] == expected_verdict(MutationType(item["type"])).value
            assert isinstance(item["contribution"], (int, float))
            assert "rationale" in item
    finally:
        app.dependency_overrides.clear()


def test_detect_case_b_hallucinated() -> None:
    client = _client(MockLLMClient(scenario="hallucinated"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        body = response.json()
        assert body["hallucination_score"] == 1.0
        assert body["classification"] == "Hallucinated"
    finally:
        app.dependency_overrides.clear()


def test_detect_case_d_mixed_persists_contributions() -> None:
    client = _client(MockLLMClient(scenario="mixed"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        body = response.json()
        assert body["hallucination_score"] == 0.3
        assert body["classification"] == "Reliable"
        assert body["not_sure_rate"] == 0.2
        contributions = [item["contribution"] for item in body["mutations"]]
        assert contributions == [0.0, 0.0, 1.0, 0.5, 0.0, 0.0, 1.0, 0.0, 0.5, 0.0]
        detail = client.get(f"/api/runs/{body['run_id']}").json()
        assert [item["contribution"] for item in detail["mutations"]] == contributions
        assert detail["base_answer"]["model"]
        assert detail["created_at"]
        assert any(item["verdict"] == Verdict.NOT_SURE.value for item in detail["mutations"])
    finally:
        app.dependency_overrides.clear()


def test_detect_case_e_malformed_verifier() -> None:
    client = _client(MockLLMClient(scenario="malformed_verifier"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        body = response.json()
        assert all(item["verdict"] == "NOT SURE" for item in body["mutations"])
        assert all(item["parse_failed"] is True for item in body["mutations"])
        assert body["hallucination_score"] == 0.5
        assert body["classification"] == "Hallucinated"
    finally:
        app.dependency_overrides.clear()


def test_detect_rejects_blank_question() -> None:
    client = _client(MockLLMClient())
    try:
        response = client.post("/api/detect", json={"question": "   "})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_detect_handles_base_answer_failure() -> None:
    client = _client(MockLLMClient(fail_on="answer"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 502
        assert "language model" in response.json()["detail"].lower()
        assert "traceback" not in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_detect_handles_mutation_generation_failure() -> None:
    client = _client(MockLLMClient(fail_on="mutations"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 502
    finally:
        app.dependency_overrides.clear()


def test_missing_run_returns_404() -> None:
    client = _client(MockLLMClient())
    try:
        response = client.get("/api/runs/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_detect_rejects_extremely_long_question() -> None:
    client = _client(MockLLMClient())
    try:
        response = client.post("/api/detect", json={"question": "A" * 2001})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


class _TimeoutLLM(LLMClient):
    async def complete_json(self, **kwargs):
        raise LLMTimeoutError("timed out")

    async def complete_text(self, **kwargs):
        raise LLMTimeoutError("timed out")


def test_detect_timeout_returns_504() -> None:
    client = _client(_TimeoutLLM())
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 504
        assert "timed out" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_detect_database_failure_returns_500() -> None:
    client = _client(MockLLMClient(scenario="reliable"))
    try:
        with patch("app.api.routes_detect.persist_detection", side_effect=SQLAlchemyError("db down")):
            response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 500
        assert "could not be saved" in response.json()["detail"].lower()
        assert "traceback" not in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ── Regression tests: question-aware mock at API level ─────────────────


def test_api_different_questions_produce_different_answers() -> None:
    """API-level regression: different questions must return different answers."""
    fake = MockLLMClient(scenario="mixed")
    client = _client(fake)
    try:
        questions = [
            "Who formulated the three laws of motion?",
            "What is the capital of France?",
            "Who wrote Hamlet?",
            "What is 2 + 2?",
        ]
        answers: list[str] = []
        run_ids: list[str] = []
        for q in questions:
            resp = client.post("/api/detect", json={"question": q})
            assert resp.status_code == 200
            body = resp.json()
            assert body["question"] == q, f"Response question {body['question']!r} != submitted {q!r}"
            answers.append(body["base_answer"]["text"])
            run_ids.append(body["run_id"])
        assert len(set(answers)) == len(questions), f"Expected {len(questions)} unique answers, got {answers}"
        assert len(set(run_ids)) == len(questions), f"Expected {len(questions)} unique run_ids"
    finally:
        app.dependency_overrides.clear()


def test_api_response_question_matches_submitted() -> None:
    """The response body 'question' field must match the submitted question."""
    fake = MockLLMClient(scenario="mixed")
    client = _client(fake)
    try:
        resp = client.post("/api/detect", json={"question": "Who wrote Hamlet?"})
        assert resp.status_code == 200
        assert resp.json()["question"] == "Who wrote Hamlet?"
    finally:
        app.dependency_overrides.clear()


def test_api_new_detection_does_not_reuse_previous_run() -> None:
    """Each new detection must create a new run with a new answer."""
    fake = MockLLMClient(scenario="mixed")
    client = _client(fake)
    try:
        resp1 = client.post("/api/detect", json={"question": "What is the capital of France?"})
        resp2 = client.post("/api/detect", json={"question": "Who wrote Hamlet?"})
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        body1 = resp1.json()
        body2 = resp2.json()
        assert body1["run_id"] != body2["run_id"]
        assert body1["base_answer"]["text"] != body2["base_answer"]["text"]
        assert body1["question"] != body2["question"]
    finally:
        app.dependency_overrides.clear()


def test_api_mutations_reference_actual_answer() -> None:
    """Mutations must reference the generated base answer, not a hardcoded constant."""
    fake = MockLLMClient(scenario="mixed")
    client = _client(fake)
    try:
        resp = client.post("/api/detect", json={"question": "Who formulated the three laws of motion?"})
        assert resp.status_code == 200
        body = resp.json()
        base = body["base_answer"]["text"]
        assert "Newton" in base
        for m in body["mutations"]:
            assert m["original_text"] == base, (
                f"Mutation original_text {m['original_text']!r} != base answer {base!r}"
            )
    finally:
        app.dependency_overrides.clear()


def test_api_frontend_displays_correct_run_from_history() -> None:
    """Loading a saved run must return data belonging to that specific run."""
    fake = MockLLMClient(scenario="mixed")
    client = _client(fake)
    try:
        resp1 = client.post("/api/detect", json={"question": "What is the capital of France?"})
        resp2 = client.post("/api/detect", json={"question": "Who wrote Hamlet?"})
        body1 = resp1.json()
        body2 = resp2.json()

        # Reload each run by ID
        detail1 = client.get(f"/api/runs/{body1['run_id']}").json()
        detail2 = client.get(f"/api/runs/{body2['run_id']}").json()

        assert detail1["question"] == "What is the capital of France?"
        assert detail2["question"] == "Who wrote Hamlet?"
        assert detail1["base_answer"]["text"] != detail2["base_answer"]["text"]
    finally:
        app.dependency_overrides.clear()

