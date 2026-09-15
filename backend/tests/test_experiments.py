import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.database.db import SessionLocal, init_db
from app.evaluation.dataset_loader import load_dataset
from app.llm.mock import MockLLMClient
from app.main import app
from app.metaqa.scoring import aggregate_score, classify
from app.schemas.experiment import ExperimentRunRequest
from app.services.experiment_service import get_experiment, llm_for_experiment, run_experiment
from tests.fakes import detector_settings


def _mini_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "mini.json"
    path.write_text(
        """
        {"name": "mini", "version": "1.0", "examples": [
          {"id": "q1", "question": "What is the capital of France?", "reference_answer": "Paris",
           "category": "location", "mock_base_answer": "Paris is the capital."},
          {"id": "q2", "question": "What is the capital of Japan?", "reference_answer": "Tokyo",
           "category": "location", "mock_base_answer": "Tokyo is the capital."}
        ]}
        """,
        encoding="utf-8",
    )
    return path


async def test_2x2_fixed_mutations_and_no_duplicate_generation(tmp_path: Path) -> None:
    path = _mini_dataset(tmp_path)
    init_db()
    db = SessionLocal()
    settings = detector_settings()
    examples = load_dataset(path).examples
    llm = llm_for_experiment(MockLLMClient(), settings, examples, ["model-a", "model-b"])
    try:
        experiment = await run_experiment(
            llm=llm,
            db=db,
            settings=settings,
            payload=ExperimentRunRequest(dataset=str(path), name="mini 2x2"),
        )
        db.commit()
        assert experiment.status == "completed"
        assert len(experiment.generations) == 4  # 2 questions × 2 generators
        assert len(experiment.conditions) == 8  # 4 cells × 2 questions
        pair_types = {(item.generator_model, item.verifier_model, item.pair_type) for item in experiment.conditions}
        assert ("model-a", "model-a", "same") in pair_types
        assert ("model-a", "model-b", "cross") in pair_types
        assert ("model-b", "model-a", "cross") in pair_types
        assert ("model-b", "model-b", "same") in pair_types
        assert isinstance(llm, MockLLMClient)
        assert llm.answer_calls == 4
        assert llm.mutation_calls == 4
        assert llm.verify_calls == 8 * 10
        for generation in experiment.generations:
            assert len(generation.mutations) == 10
            assert len(generation.mutation_set_hash) == 64
            ids = [item.id for item in generation.mutations]
            texts = [item.mutated_text for item in generation.mutations]
            for condition in generation.conditions:
                assert [item.mutation_id for item in condition.verifications] == ids
                assert [item.mutation.mutated_text for item in condition.verifications] == texts
                contributions = [scored.contribution for scored in condition.verifications]
                assert all(item in {0.0, 0.5, 1.0} for item in contributions)
                assert condition.hallucination_score == aggregate_score(contributions)
                assert condition.classification == classify(condition.hallucination_score, 0.5).value
        for condition in experiment.conditions:
            if condition.verifier_model == "model-a":
                assert condition.hallucination_score == 0.0
                assert condition.classification == "Reliable"
            else:
                assert condition.hallucination_score == 1.0
                assert condition.classification == "Hallucinated"
        parsed = json.loads(experiment.summary_stats_json)
        assert "self_verification_score_difference" in experiment.summary_stats_json
        by_gen = {item["generator_model"]: item for item in parsed["self_verification"]}
        assert by_gen["model-a"]["self_verification_score_difference"] == -1.0
        assert by_gen["model-b"]["self_verification_score_difference"] == 1.0
        assert by_gen["model-a"]["classification_flip_rate"] == 1.0
        paired = parsed["paired_comparisons"]
        assert all(item["difference"] == item["same_model_score"] - item["cross_model_score"] for item in paired)
        assert "DEMO" in parsed["key_finding"]
    finally:
        db.close()


async def test_experiment_persists_and_reloads(tmp_path: Path) -> None:
    path = _mini_dataset(tmp_path)
    init_db()
    db = SessionLocal()
    settings = detector_settings()
    examples = load_dataset(path).examples
    llm = llm_for_experiment(MockLLMClient(), settings, examples, ["model-a", "model-b"])
    try:
        created = await run_experiment(
            llm=llm,
            db=db,
            settings=settings,
            payload=ExperimentRunRequest(dataset=str(path)),
        )
        db.commit()
        experiment_id = created.id
    finally:
        db.close()

    db = SessionLocal()
    try:
        loaded = get_experiment(db, experiment_id)
        assert loaded is not None
        assert loaded.status == "completed"
        assert len(loaded.conditions) == 8
        assert len(loaded.generations) == 4
        generation = loaded.generations[0]
        texts = [item.mutated_text for item in generation.mutations]
        for condition in generation.conditions:
            assert [item.mutation.mutated_text for item in condition.verifications] == texts
    finally:
        db.close()


def test_experiment_api_mock_run_and_export() -> None:
    client = TestClient(app)
    created = client.post(
        "/api/experiments/run",
        json={
            "dataset": "pilot",
            "generator_models": ["model-a", "model-b"],
            "verifier_models": ["model-a", "model-b"],
            "synonym_count": 5,
            "antonym_count": 5,
            "threshold": 0.5,
            "trials": 1,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "completed"
    assert body["demo_data"] is True
    assert body["experiment_id"] == body["id"]
    assert len(body["condition_summaries"]) == 4
    assert body["question_count"] == 40
    means = {item["label"]: item["mean_score"] for item in body["condition_summaries"]}
    assert set(means) == {"A → A", "A → B", "B → A", "B → B"}
    assert means["A → A"] == 0.0
    assert means["A → B"] == 1.0
    assert means["B → A"] == 0.0
    assert means["B → B"] == 1.0
    assert len(body["paired_comparisons"]) == 80  # 40 questions × 2 generators
    assert "DEMO" in body["key_finding"]
    assert "bias" not in body["key_finding"].lower()
    experiment_id = body["id"]

    fetched = client.get(f"/api/experiments/{experiment_id}")
    assert fetched.status_code == 200
    assert fetched.json()["classification_flip_rate"] == body["classification_flip_rate"]
    assert fetched.json()["classification_flip_rate"] == 1.0

    latest = client.get("/api/experiments/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == experiment_id

    export = client.get(f"/api/experiments/{experiment_id}/export")
    assert export.status_code == 200
    assert "generator_model" in export.text
    assert "pair_type" in export.text
    assert "mutation_set_hash" in export.text
    assert "OPENAI" not in export.text
    assert export.text.count("\n") >= 160  # header + 160 condition rows

    paired = client.get(f"/api/experiments/{experiment_id}/export/paired")
    assert paired.status_code == 200
    assert "same_model_score" in paired.text
    assert "classification_flip" in paired.text

    generation_id = body["paired_comparisons"][0]["generation_id"]
    trace = client.get(f"/api/experiments/{experiment_id}/traces/{generation_id}")
    assert trace.status_code == 200
    payload = trace.json()
    assert len(payload["conditions"]) == 2
    texts_a = [item["mutated_text"] for item in payload["conditions"][0]["mutations"]]
    texts_b = [item["mutated_text"] for item in payload["conditions"][1]["mutations"]]
    assert texts_a == texts_b
    assert len(texts_a) == 10

    summary = client.get(f"/api/experiments/{experiment_id}/export/summary")
    assert summary.status_code == 200
    assert "mean_score" in summary.text
    flips = client.get(f"/api/experiments/{experiment_id}/export/flips")
    assert flips.status_code == 200
    assert "classification_flip" in flips.text
    sweep = client.get(f"/api/experiments/{experiment_id}/export/sweep")
    assert sweep.status_code == 200
    config = client.get(f"/api/experiments/{experiment_id}/export/config")
    assert config.status_code == 200
    log = config.json()
    assert log["dataset"] == "pilot"
    assert log["mode"] == "mock"
    assert "api_key" not in config.text.lower()
    assert "OPENAI" not in config.text
    assert body["research_log"]["experiment_id"] == experiment_id
    assert "research_summary" in body


def test_experiment_rejects_one_model() -> None:
    client = TestClient(app)
    response = client.post("/api/experiments/run", json={"generator_models": ["only-one"], "verifier_models": ["a", "b"]})
    assert response.status_code == 422


def test_experiment_rejects_empty_dataset(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text('{"name": "empty", "version": "1.0", "examples": []}', encoding="utf-8")
    client = TestClient(app)
    response = client.post("/api/experiments/run", json={"dataset": str(path)})
    assert response.status_code == 400


def test_experiment_rejects_invalid_threshold() -> None:
    client = TestClient(app)
    response = client.post("/api/experiments/run", json={"threshold": 1.5})
    assert response.status_code == 422
