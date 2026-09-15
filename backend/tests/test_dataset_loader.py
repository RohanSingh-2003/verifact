from pathlib import Path

import pytest

from app.evaluation.dataset_loader import DatasetError, load_dataset


def test_pilot_dataset_loads() -> None:
    bundle = load_dataset("pilot")
    assert bundle.name == "pilot"
    assert 30 <= len(bundle.examples) <= 50
    categories = {item.category for item in bundle.examples}
    assert categories == {"named_entity", "date", "numeric", "location", "general_fact"}
    assert any(item.needs_review for item in bundle.examples)


def test_truthfulqa_missing_is_explicit() -> None:
    with pytest.raises(DatasetError, match="TruthfulQA is not bundled"):
        load_dataset("truthfulqa")


def test_malformed_json_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"name": "bad", "examples": [{"id": "x"}]}', encoding="utf-8")
    with pytest.raises(DatasetError, match="Rejected malformed"):
        load_dataset(path)


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    path = tmp_path / "dup.json"
    path.write_text(
        """
        {"name": "dup", "examples": [
          {"id": "q1", "question": "Q?", "reference_answer": "A", "category": "date"},
          {"id": "q1", "question": "Q2?", "reference_answer": "B", "category": "date"}
        ]}
        """,
        encoding="utf-8",
    )
    with pytest.raises(DatasetError, match="duplicate id"):
        load_dataset(path)


def test_csv_loader(tmp_path: Path) -> None:
    path = tmp_path / "mini.csv"
    path.write_text(
        "id,question,reference_answer,category,source,aliases,needs_review\n"
        "q1,What is the capital of France?,Paris,location,curated,,false\n",
        encoding="utf-8",
    )
    bundle = load_dataset(path)
    assert len(bundle.examples) == 1
    assert bundle.examples[0].reference_answer == "Paris"
