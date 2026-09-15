from app.evaluation.evaluator import llm_for_evaluation, run_evaluation
from app.evaluation.metrics import confusion_counts, compute_metrics
from app.evaluation.schemas import DatasetExample
from app.llm.mock import MockLLMClient
from app.metaqa.detector import BaseAnswer, DetectionResult
from app.metaqa.scoring import Classification, classify
from tests.fakes import detector_settings


def _result(example: DatasetExample, answer: str, score: float) -> DetectionResult:
    return DetectionResult(
        question=example.question,
        base_answer=BaseAnswer(text=answer, model="mock-eval"),
        mutations=[],
        hallucination_score=score,
        threshold=0.5,
        classification=classify(score, 0.5),
        not_sure_rate=0.0,
        generator_model="mock-eval",
        verifier_model="mock-eval",
        llm_mode="mock",
    )


async def test_evaluation_with_mocked_detector(tmp_path) -> None:

    path = tmp_path / "mini.json"
    path.write_text(
        """
        {"name": "mini", "version": "1.0", "examples": [
          {"id": "a", "question": "Capital of France?", "reference_answer": "Paris",
           "category": "location", "mock_base_answer": "Paris is the capital.", "mock_scenario": "reliable"},
          {"id": "b", "question": "Capital of Australia?", "reference_answer": "Canberra",
           "category": "location", "mock_base_answer": "Sydney is the capital.", "mock_scenario": "hallucinated"},
          {"id": "c", "question": "Capital of Japan?", "reference_answer": "Tokyo",
           "category": "location", "mock_base_answer": "Tokyo is the capital.", "mock_scenario": "hallucinated"},
          {"id": "d", "question": "Capital of Canada?", "reference_answer": "Ottawa",
           "category": "location", "mock_base_answer": "Toronto is the capital.", "mock_scenario": "reliable"},
          {"id": "e", "question": "Ambiguous item?", "reference_answer": "Maybe",
           "category": "general_fact", "needs_review": true, "mock_base_answer": "I don't know"}
        ]}
        """,
        encoding="utf-8",
    )
    calls: list[str] = []

    async def detect(example: DatasetExample) -> DetectionResult:
        calls.append(example.question)
        assert example.reference_answer not in example.question
        if example.id == "a":
            return _result(example, "Paris is the capital.", 0.1)
        if example.id == "b":
            return _result(example, "Sydney is the capital.", 0.9)
        if example.id == "c":
            return _result(example, "Tokyo is the capital.", 0.9)
        if example.id == "d":
            return _result(example, "Toronto is the capital.", 0.1)
        return _result(example, "I don't know", 0.4)

    from app.database.db import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        run = await run_evaluation(
            llm=MockLLMClient(),
            db=db,
            settings=detector_settings(),
            dataset=str(path),
            threshold=0.5,
            detect_fn=detect,
            persist_traces=False,
        )
        db.commit()
        assert run.status == "completed"
        assert run.llm_mode == "mock"
        assert len(calls) == 5
        labeled = [item for item in run.results if item.outcome != "Needs Review"]
        assert len(labeled) == 4
        assert run.review_examples == 1
        actuals = [Classification(item.actual_label) for item in labeled]
        preds = [Classification(item.predicted_label) for item in labeled]
        metrics = compute_metrics(confusion_counts(actuals, preds))
        assert metrics.tp == 1
        assert metrics.tn == 1
        assert metrics.fp == 1
        assert metrics.fn == 1
        primary = next(item for item in run.metrics if item.is_primary)
        assert primary.tp == 1
        assert {item.threshold for item in run.metrics} >= {0.3, 0.5, 0.7}
        assert len(calls) == 5
    finally:
        db.close()


def test_eval_llm_does_not_receive_reference_answers() -> None:
    examples = [
        DatasetExample(
            id="q1",
            question="What is the capital of Australia?",
            reference_answer="Canberra",
            category="location",
            mock_base_answer="Sydney is the capital of Australia.",
            mock_scenario="hallucinated",
        )
    ]
    client = llm_for_evaluation(MockLLMClient(), detector_settings(), examples)
    assert isinstance(client, MockLLMClient)
    assert "Canberra" not in client.answers_by_question.values()
    assert client.answers_by_question[examples[0].question] == "Sydney is the capital of Australia."
