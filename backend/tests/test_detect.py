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
        assert body["status"] == "answer_ready"
        assert body["mutations"] == []
        assert body["hallucination_score"] is None
        assert body["classification"] is None
        assert body["threshold"] == 0.5
        assert body["llm_mode"] == "mock"
        run_id = body["run_id"]

        # TestClient waits for background tasks; completed state is available via GET.
        detail = client.get(f"/api/runs/{run_id}")
        assert detail.status_code == 200
        reconstructed = detail.json()
        assert reconstructed["status"] == "completed"
        assert reconstructed["hallucination_score"] == 0.0
        assert reconstructed["classification"] == "Reliable"
        assert reconstructed["not_sure_rate"] == 0.0
        assert len(reconstructed["mutations"]) == 10
        assert isinstance(reconstructed["hallucination_score"], (int, float))
        assert isinstance(reconstructed["not_sure_rate"], (int, float))

        listed = client.get("/api/runs")
        assert listed.status_code == 200
        assert listed.json()["total"] >= 1
        assert any(item["id"] == run_id for item in listed.json()["items"])

        assert [item["mutated_text"] for item in reconstructed["mutations"]]
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
        run_id = response.json()["run_id"]
        body = client.get(f"/api/runs/{run_id}").json()
        assert body["hallucination_score"] == 1.0
        assert body["classification"] == "Hallucinated"
        assert body["status"] == "completed"
    finally:
        app.dependency_overrides.clear()


def test_detect_case_d_mixed_persists_contributions() -> None:
    client = _client(MockLLMClient(scenario="mixed"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        body = client.get(f"/api/runs/{run_id}").json()
        assert body["hallucination_score"] == 0.3
        assert body["classification"] == "Reliable"
        assert body["not_sure_rate"] == 0.2
        contributions = [item["contribution"] for item in body["mutations"]]
        assert contributions == [0.0, 0.0, 1.0, 0.5, 0.0, 0.0, 1.0, 0.0, 0.5, 0.0]
        assert body["base_answer"]["model"]
        assert body["created_at"]
        assert any(item["verdict"] == Verdict.NOT_SURE.value for item in body["mutations"])
    finally:
        app.dependency_overrides.clear()


def test_detect_case_e_malformed_verifier() -> None:
    client = _client(MockLLMClient(scenario="malformed_verifier"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        body = client.get(f"/api/runs/{response.json()['run_id']}").json()
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
        assert "unable to generate an answer" in response.json()["detail"].lower()
        assert "traceback" not in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_detect_handles_mutation_generation_failure() -> None:
    client = _client(MockLLMClient(fail_on="mutations"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        # Answer is returned immediately; MetaQA failure is recorded on the run.
        assert response.status_code == 200
        body = response.json()
        assert body["base_answer"]["text"]
        assert body["status"] == "answer_ready"
        detail = client.get(f"/api/runs/{body['run_id']}").json()
        assert detail["status"] == "mutation_generation_failed"
        assert detail["base_answer"]["text"] == body["base_answer"]["text"]
        assert detail["hallucination_score"] is None
        assert detail["classification"] is None
        assert detail["analysis_error"]
        assert "mutation generator" in detail["analysis_error"].lower()
        assert "still available" in detail["analysis_error"].lower()
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
        with patch("app.api.routes_detect.create_answer_ready_run", side_effect=SQLAlchemyError("db down")):
            response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 500
        assert "could not be saved" in response.json()["detail"].lower()
        assert "traceback" not in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_detect_returns_answer_before_metaqa_completes() -> None:
    """POST /api/detect must return the real answer with answer_ready before MetaQA finishes."""
    client = _client(MockLLMClient(scenario="reliable"))
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "answer_ready"
        assert body["base_answer"]["text"]
        assert body["timing"]["time_to_answer_ms"] is not None
        # Background task finishes before TestClient returns; completed via GET.
        completed = client.get(f"/api/runs/{body['run_id']}").json()
        assert completed["status"] == "completed"
        assert len(completed["mutations"]) == 10
    finally:
        app.dependency_overrides.clear()


def test_progressive_mutations_available_during_verification() -> None:
    """GET /api/runs/{id} must expose mutations as soon as they are generated, before verification ends."""
    from app.database.db import SessionLocal
    from app.metaqa.detector import ScoredMutation
    from app.metaqa.mutation import GeneratedMutation
    from app.metaqa.scoring import MutationType, Verdict, contribution_score, expected_verdict
    from app.schemas.detect import RunStatus
    from app.services import run_service

    db = SessionLocal()
    try:
        run = run_service.create_answer_ready_run(
            db,
            question="What is the capital of India?",
            base_answer="New Delhi is the capital of India.",
            generator_model="mock-model",
            threshold=0.5,
            llm_mode="mock",
            answer_ms=12.0,
        )
        db.commit()
        run_id = run.id

        pending = [
            GeneratedMutation(
                type=MutationType.SYNONYM,
                original_text="New Delhi is the capital of India.",
                mutated_text="In other words, New Delhi is the capital of India.",
            ),
            GeneratedMutation(
                type=MutationType.ANTONYM,
                original_text="New Delhi is the capital of India.",
                mutated_text="New Delhi is not the capital of India.",
            ),
        ]
        run_service.persist_pending_mutations(
            db,
            run_id,
            mutations=pending,
            verifier_model="mock-verifier",
            mutation_ms=40.0,
        )
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    mid = client.get(f"/api/runs/{run_id}").json()
    assert mid["status"] == "mutations_ready"
    assert mid["hallucination_score"] is None
    assert mid["classification"] is None
    assert len(mid["mutations"]) == 2
    assert all(item["verified"] is False for item in mid["mutations"])
    assert all(item["verdict"] is None for item in mid["mutations"])
    assert mid["mutations"][0]["mutated_text"].startswith("In other words")
    assert mid["mutations"][0]["expected_verdict"] == "YES"
    assert mid["mutations"][1]["expected_verdict"] == "NO"

    first = pending[0]
    scored = ScoredMutation(
        mutation=first,
        verdict=Verdict.YES,
        expected=expected_verdict(first.type),
        contribution=contribution_score(first.type, Verdict.YES),
        rationale="Consistent",
        parse_failed=False,
    )
    db = SessionLocal()
    try:
        run_service.update_run_status(db, run_id, RunStatus.VERIFYING_MUTATIONS)
        run_service.update_mutation_verification(db, run_id, 0, scored)
        db.commit()
    finally:
        db.close()

    partial = client.get(f"/api/runs/{run_id}").json()
    assert partial["status"] == "verifying_mutations"
    assert partial["mutations"][0]["verified"] is True
    assert partial["mutations"][0]["verdict"] == "YES"
    assert partial["mutations"][0]["contribution"] == 0.0
    assert partial["mutations"][1]["verified"] is False
    assert partial["mutations"][1]["verdict"] is None


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
            completed = client.get(f"/api/runs/{body['run_id']}").json()
            assert completed["status"] == "completed"
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
        completed = client.get(f"/api/runs/{body['run_id']}").json()
        for m in completed["mutations"]:
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

