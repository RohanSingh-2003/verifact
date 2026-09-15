from __future__ import annotations

import csv
import json
from pathlib import Path

from pydantic import ValidationError

from app.evaluation.schemas import DatasetBundle, DatasetExample
from app.metaqa.scoring import Classification

DATASETS_DIR = Path(__file__).resolve().parents[2] / "data" / "datasets"

TRUTHFULQA_HINT = (
    "TruthfulQA is not bundled with VeriFact. Place a curated JSON or CSV file at "
    "data/datasets/truthfulqa.json (or .csv) using the evaluation schema. "
    "Do not invent TruthfulQA items."
)


class DatasetError(ValueError):
    """Raised when an evaluation dataset cannot be loaded or validated."""


def default_dataset_path(name: str) -> Path:
    cleaned = name.strip().lower()
    if not cleaned:
        raise DatasetError("Dataset name cannot be empty.")
    for suffix in (".json", ".csv"):
        candidate = DATASETS_DIR / f"{cleaned}{suffix}"
        if candidate.exists():
            return candidate
    return DATASETS_DIR / f"{cleaned}.json"


def load_dataset(name_or_path: str | Path) -> DatasetBundle:
    path = Path(name_or_path)
    if path.suffix.lower() in {".json", ".csv"} and path.exists():
        return _load_path(path)
    name = str(name_or_path).strip().lower()
    if name in {"truthfulqa", "truthful_qa"}:
        path = default_dataset_path("truthfulqa")
        if not path.exists():
            raise DatasetError(TRUTHFULQA_HINT)
        return _load_path(path)
    path = default_dataset_path(name)
    if not path.exists():
        raise DatasetError(f"Dataset '{name}' was not found at {path}.")
    return _load_path(path)


def _load_path(path: Path) -> DatasetBundle:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _load_json(path)
    if suffix == ".csv":
        return _load_csv(path)
    raise DatasetError(f"Unsupported dataset format: {path.suffix}")


def _load_json(path: Path) -> DatasetBundle:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetError(f"Dataset JSON is malformed: {exc}") from exc
    if isinstance(payload, list):
        payload = {
            "name": path.stem,
            "version": "1.0",
            "examples": payload,
        }
    if not isinstance(payload, dict):
        raise DatasetError("Dataset JSON must be an object or a list of examples.")
    raw_examples = payload.get("examples")
    if not isinstance(raw_examples, list):
        raise DatasetError("Dataset JSON must contain an examples list.")
    examples = _validate_examples(raw_examples)
    try:
        return DatasetBundle(
            name=str(payload.get("name") or path.stem),
            version=str(payload.get("version") or "1.0"),
            description=str(payload.get("description") or ""),
            license=str(payload.get("license") or ""),
            source=str(payload.get("source") or ""),
            examples=examples,
        )
    except ValidationError as exc:
        raise DatasetError(_format_validation(exc)) from exc


def _load_csv(path: Path) -> DatasetBundle:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DatasetError("CSV dataset has no header row.")
        rows = list(reader)
    examples = _validate_examples([_csv_row(row, index) for index, row in enumerate(rows)])
    return DatasetBundle(name=path.stem, version="1.0", examples=examples)


def _csv_row(row: dict[str, str | None], index: int) -> dict[str, object]:
    aliases_raw = (row.get("aliases") or "").strip()
    aliases = [item.strip() for item in aliases_raw.split("|") if item.strip()] if aliases_raw else []
    needs = (row.get("needs_review") or "").strip().lower() in {"1", "true", "yes"}
    label_raw = (row.get("ground_truth_label") or "").strip()
    label: str | None
    if not label_raw:
        label = None
    elif label_raw in {Classification.RELIABLE.value, Classification.HALLUCINATED.value}:
        label = label_raw
    else:
        raise DatasetError(f"CSV row {index + 2}: invalid ground_truth_label '{label_raw}'.")
    return {
        "id": (row.get("id") or "").strip() or f"row-{index + 1}",
        "question": row.get("question") or "",
        "reference_answer": row.get("reference_answer") or "",
        "ground_truth_label": label,
        "category": (row.get("category") or "general_fact").strip() or "general_fact",
        "source": (row.get("source") or "curated").strip() or "curated",
        "aliases": aliases,
        "needs_review": needs,
        "mock_base_answer": (row.get("mock_base_answer") or "").strip() or None,
        "mock_scenario": (row.get("mock_scenario") or "").strip() or None,
    }


def _validate_examples(raw_items: list[object]) -> list[DatasetExample]:
    examples: list[DatasetExample] = []
    errors: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items):
        try:
            example = DatasetExample.model_validate(item)
        except ValidationError as exc:
            errors.append(f"Row {index}: {_format_validation(exc)}")
            continue
        if example.id in seen:
            errors.append(f"Row {index}: duplicate id '{example.id}'.")
            continue
        seen.add(example.id)
        examples.append(example)
    if errors:
        preview = "; ".join(errors[:8])
        raise DatasetError(f"Rejected malformed dataset rows ({len(errors)}): {preview}")
    if not examples:
        raise DatasetError("Dataset contains no valid examples.")
    return examples


def build_manifest(bundle: DatasetBundle) -> dict:
    """Evaluation-layer metadata. Ground truth is never sent into MetaQA prompts."""
    return {
        "dataset_name": bundle.name,
        "dataset_version": bundle.version,
        "description": bundle.description,
        "license": bundle.license or "Original curated items for VeriFact research. Not TruthfulQA.",
        "source": bundle.source or "curated",
        "item_count": len(bundle.examples),
        "ground_truth_policy": (
            "Reliable means the generated answer is factually supported by the reference. "
            "Hallucinated means the generated answer conflicts with the reference. "
            "Question-level labels are not assumed to describe generated-answer correctness. "
            "Ambiguous cases are marked Needs Review and excluded from automatic P/R/F1. "
            "Reference answers stay in the evaluation layer and never enter MetaQA prompts."
        ),
        "items": [
            {
                "question_id": item.id,
                "category": item.category,
                "reference_answer": item.reference_answer,
                "aliases": item.aliases,
                "needs_review": item.needs_review,
                "source": item.source,
            }
            for item in bundle.examples
        ],
    }


def write_manifest(bundle: DatasetBundle, path: Path | None = None) -> Path:
    dest = path or (DATASETS_DIR / f"{bundle.name}.manifest.json")
    dest.write_text(json.dumps(build_manifest(bundle), indent=2), encoding="utf-8")
    return dest


def _format_validation(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors()[:4]:
        location = ".".join(str(item) for item in error.get("loc", ()))
        parts.append(f"{location}: {error.get('msg')}")
    return "; ".join(parts) or str(exc)
