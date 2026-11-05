from fastapi.testclient import TestClient

from app.main import app


def test_evaluation_api_mock_run_and_export() -> None:
    client = TestClient(app)
    created = client.post(
        "/api/evaluations/run",
        json={"dataset": "hallucination_benchmark_frozen", "threshold": 0.5, "max_questions": 10},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "completed"
    assert body["demo_data"] is True
    assert body["llm_mode"] == "mock"
    assert body["dataset_name"] == "hallucination_benchmark_frozen"
    assert body["completed_examples"] == 10
    assert "metrics" in body
    assert "confusion_matrix" in body
    assert len(body["threshold_sweep"]) >= 9
    metrics = body["metrics"]
    eval_id = body["evaluation_id"]

    listed = client.get("/api/evaluations")
    assert listed.status_code == 200
    assert any(item["id"] == eval_id for item in listed.json()["items"])

    detail = client.get(f"/api/evaluations/{eval_id}")
    assert detail.status_code == 200
    assert detail.json()["metrics"]["f1"] == metrics["f1"]

    export = client.get(f"/api/evaluations/{eval_id}/export")
    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]
    text = export.text
    assert "question_id" in text
    assert "hallucination_score" in text
    assert "OPENAI" not in text
    assert "api_key" not in text.lower()


def test_evaluation_unknown_dataset() -> None:
    client = TestClient(app)
    response = client.post("/api/evaluations/run", json={"dataset": "missing-set"})
    assert response.status_code == 400


def test_evaluation_empty_dataset(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)
    path = tmp_path / "empty.json"
    path.write_text('{"name": "empty", "version": "1.0", "examples": []}', encoding="utf-8")
    client = TestClient(app)
    response = client.post("/api/evaluations/run", json={"dataset": str(path)})
    assert response.status_code == 400


def test_evaluation_rejects_path_traversal() -> None:
    client = TestClient(app)
    response = client.post("/api/evaluations/run", json={"dataset": "../../backend/app/main.py"})
    assert response.status_code == 400
    assert "Access denied" in response.json()["detail"]


def test_evaluation_sweep_export() -> None:
    client = TestClient(app)
    created = client.post(
        "/api/evaluations/run",
        json={"dataset": "hallucination_benchmark_frozen", "threshold": 0.5, "max_questions": 10},
    )
    assert created.status_code == 200
    eval_id = created.json()["evaluation_id"]
    sweep = client.get(f"/api/evaluations/{eval_id}/export/sweep")
    assert sweep.status_code == 200
    assert "precision" in sweep.text
    assert "0.3" in sweep.text
    assert "OPENAI" not in sweep.text


def test_evaluation_api_rejects_legacy_pilot() -> None:
    client = TestClient(app)
    res = client.post("/api/evaluations/run", json={"dataset": "pilot"})
    assert res.status_code == 400
    assert "permanently removed" in res.json()["detail"]
