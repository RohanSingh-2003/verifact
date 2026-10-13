import os
from pathlib import Path

import pytest

from app.evaluation.dataset_loader import (
    DatasetError,
    _resolve_dataset_path,
    load_dataset,
    resolve_dataset_path,
)


def test_pilot_dataset_loads() -> None:
    bundle = load_dataset("pilot")
    assert bundle.name == "pilot"
    assert 30 <= len(bundle.examples) <= 50
    categories = {item.category for item in bundle.examples}
    assert categories == {"named_entity", "date", "numeric", "location", "general_fact"}
    assert any(item.needs_review for item in bundle.examples)


def test_pilot_dataset_loads_case_insensitive_and_with_extension() -> None:
    path = resolve_dataset_path("pilot")
    assert path.name == "pilot.json"
    bundle_lower = load_dataset("pilot")
    bundle_upper = load_dataset("PILOT")
    bundle_ext = load_dataset("pilot.json")
    assert bundle_lower.name == "pilot"
    assert bundle_upper.name == "pilot"
    assert bundle_ext.name == "pilot"


def test_empty_dataset_name_rejected() -> None:
    with pytest.raises(DatasetError, match="Dataset name cannot be empty."):
        load_dataset("")
    with pytest.raises(DatasetError, match="Dataset name cannot be empty."):
        load_dataset("   ")


def test_truthfulqa_missing_is_explicit() -> None:
    with pytest.raises(DatasetError, match="TruthfulQA is not bundled"):
        load_dataset("truthfulqa")
    with pytest.raises(DatasetError, match="TruthfulQA is not bundled"):
        load_dataset("truthful_qa")


def test_nonexistent_dataset_rejected_without_path_leak() -> None:
    with pytest.raises(DatasetError, match=r"Dataset 'missing_dataset' was not found\.$"):
        load_dataset("missing_dataset")


def test_relative_path_traversal_rejected() -> None:
    with pytest.raises(DatasetError, match="Access denied: dataset must reside within the approved datasets directory."):
        load_dataset("../../app/main.py")
    with pytest.raises(DatasetError, match="Access denied: dataset must reside within the approved datasets directory."):
        load_dataset("..\\..\\app\\main.py")
    with pytest.raises(DatasetError, match="Access denied: dataset must reside within the approved datasets directory."):
        load_dataset("../../../etc/passwd.json")


def test_absolute_path_outside_directory_rejected(tmp_path: Path) -> None:
    outside_file = tmp_path / "outside.json"
    outside_file.write_text('{"name": "outside", "examples": []}', encoding="utf-8")
    with pytest.raises(DatasetError, match="Access denied: dataset must reside within the approved datasets directory."):
        load_dataset(outside_file)


def test_windows_drive_letter_rejected_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    # On POSIX systems, Windows-style paths must be defensively rejected
    monkeypatch.setattr(os, "name", "posix")
    with pytest.raises(DatasetError, match="Access denied: dataset must reside within the approved datasets directory."):
        _resolve_dataset_path("C:\\Windows\\system32\\file.json")


def test_symlink_resolving_outside_rejected(tmp_path: Path) -> None:
    outside_target = tmp_path / "target.json"
    outside_target.write_text('{"name": "target", "examples": []}', encoding="utf-8")
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    symlink_path = sandbox_dir / "linked.json"
    try:
        os.symlink(outside_target, symlink_path)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not supported in current environment.")

    with pytest.raises(DatasetError, match="Access denied: dataset must reside within the approved datasets directory."):
        _resolve_dataset_path("linked.json", base_dir=sandbox_dir)


def test_unsupported_file_extension_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)
    bad_ext = tmp_path / "notes.txt"
    bad_ext.write_text("hello", encoding="utf-8")
    with pytest.raises(DatasetError, match="Unsupported dataset format: .txt"):
        load_dataset("notes.txt")


def test_malformed_json_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)
    path = tmp_path / "bad.json"
    path.write_text('{"name": "bad", "examples": [{"id": "x"}]}', encoding="utf-8")
    with pytest.raises(DatasetError, match="Rejected malformed"):
        load_dataset(path)


def test_duplicate_ids_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)
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


def test_csv_loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)
    path = tmp_path / "mini.csv"
    path.write_text(
        "id,question,reference_answer,category,source,aliases,needs_review\n"
        "q1,What is the capital of France?,Paris,location,curated,,false\n",
        encoding="utf-8",
    )
    bundle = load_dataset(path)
    assert len(bundle.examples) == 1
    assert bundle.examples[0].reference_answer == "Paris"
