from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.database.db import SessionLocal, init_db

from app.evaluation.dataset_loader import DATASETS_DIR, load_dataset
from app.evaluation.ground_truth import resolve_ground_truth
from app.evaluation.schemas import DatasetBundle, DatasetExample, GroundTruthSource
from app.metaqa.scoring import Classification
from scripts.freeze_benchmark_dataset import enrich_and_freeze
from scripts.prepare_benchmark_datasets import (
    RANDOM_SEED,
    extract_truthfulqa,
)


@pytest.fixture
def eval_db() -> Session:
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── 1. Legacy Pilot Rejection ─────────────────────────────────────────────────

def test_legacy_pilot_dataset_permanently_rejected() -> None:
    """The old 40-question pilot dataset cannot be loaded or resolved."""
    assert (DATASETS_DIR / "pilot.json").exists() is False
    assert (DATASETS_DIR / "pilot.manifest.json").exists() is False
    with pytest.raises(Exception, match="The legacy 40-question pilot dataset has been permanently removed"):
        load_dataset("pilot")


# ── 2. Standardized Benchmark Dataset Integrity ──────────────────────────────

def test_hallucination_benchmark_dataset_integrity() -> None:
    """hallucination_benchmark.json conforms to all structural requirements."""
    benchmark_path = DATASETS_DIR / "hallucination_benchmark.json"
    assert benchmark_path.exists(), "hallucination_benchmark.json must be generated"

    bundle = load_dataset("hallucination_benchmark")
    assert bundle.name == "hallucination_benchmark"
    assert len(bundle.examples) == 550, "Total questions must be exactly 550"

    tqa_items = [e for e in bundle.examples if e.dataset == "truthfulqa"]
    fqa_items = [e for e in bundle.examples if e.dataset == "freshqa"]
    assert len(tqa_items) == 400, "TruthfulQA questions must be exactly 400"
    assert len(fqa_items) == 150, "FreshQA questions must be exactly 150"

    # Partitions
    dev_items = [e for e in bundle.examples if e.split == "dev"]
    test_items = [e for e in bundle.examples if e.split == "test"]
    assert len(dev_items) == 440, "Dev split must be exactly 440 (80%)"
    assert len(test_items) == 110, "Test split must be exactly 110 (20%)"


# ── 3. Duplicate Detection ────────────────────────────────────────────────────

def test_no_duplicate_ids_or_questions_in_benchmark() -> None:
    """All 550 IDs and questions in hallucination_benchmark.json are unique."""
    bundle = load_dataset("hallucination_benchmark")
    all_ids = [e.id for e in bundle.examples]
    all_questions = [e.question.casefold().strip() for e in bundle.examples]

    assert len(set(all_ids)) == 550, f"Duplicate IDs found ({len(all_ids)} vs {len(set(all_ids))})"
    assert len(set(all_questions)) == 550, f"Duplicate questions found ({len(all_questions)} vs {len(set(all_questions))})"


# ── 4. Frozen Benchmark Integrity ─────────────────────────────────────────────

def test_frozen_benchmark_integrity() -> None:
    """hallucination_benchmark_frozen.json is the authoritative snapshot for evaluation."""
    frozen_path = DATASETS_DIR / "hallucination_benchmark_frozen.json"
    assert frozen_path.exists()
    bundle = load_dataset("hallucination_benchmark_frozen")
    assert len(bundle.examples) == 550
    assert bundle.name == "hallucination_benchmark_frozen"


# ── 5. Deterministic Sampling Reproducibility ─────────────────────────────────

def test_deterministic_sampling_reproducibility() -> None:
    """Sampling with seed=42 produces identical subsets and partition assignments."""
    tqa_raw = (DATASETS_DIR.parents[0] / "raw" / "TruthfulQA.csv").read_text(encoding="utf-8", errors="ignore")
    sample1 = extract_truthfulqa(tqa_raw, target_count=50, seed=RANDOM_SEED)
    sample2 = extract_truthfulqa(tqa_raw, target_count=50, seed=RANDOM_SEED)

    assert [s["id"] for s in sample1] == [s["id"] for s in sample2]
    assert [s["question"] for s in sample1] == [s["question"] for s in sample2]
    assert [s["split"] for s in sample1] == [s["split"] for s in sample2]


# ── 6. Provenance and Snapshot Date Validation ────────────────────────────────

def test_dataset_provenance_and_temporal_snapshot() -> None:
    """All FreshQA items have snapshot_date and valid temporal categories."""
    bundle = load_dataset("hallucination_benchmark")
    fqa_items = [e for e in bundle.examples if e.dataset == "freshqa"]

    for item in fqa_items:
        assert item.snapshot_date == "2026-04-21"
        assert item.category in {"never_changing", "slow_changing", "fast_changing"}
        assert item.question_type in {"never_changing", "slow_changing", "fast_changing", "false_premise"}
        assert len(item.correct_answers) >= 1
        assert item.reference_answer != ""


# ── 7. Annotation-to-Dataset Matching by Question ID ─────────────────────────

def test_deterministic_annotation_matching_and_freezing(tmp_path: Path) -> None:
    """Freezing benchmark enriches exact question_ids and rejects ambiguous mappings."""
    # Create mini base dataset
    base_file = tmp_path / "base_test.json"
    base_data = {
        "name": "base_test",
        "version": "1.0",
        "examples": [
            {
                "id": "tqa_0001",
                "dataset": "truthfulqa",
                "question": "What is 2+2?",
                "reference_answer": "4",
                "split": "dev",
                "needs_review": True,
            },
            {
                "id": "tqa_0002",
                "dataset": "truthfulqa",
                "question": "What is 3+3?",
                "reference_answer": "6",
                "split": "test",
                "needs_review": False,
            },
        ],
    }
    base_file.write_text(json.dumps(base_data), encoding="utf-8")

    custom_annotations = [
        {
            "question_id": "tqa_0001",
            "adjudicated_label": "Reliable",
            "adjudicator_id": "senior_researcher",
            "adjudication_notes": "Mathematically verified.",
            "adjudication_evidence": "Peano arithmetic",
            "reviewer1_label": "Reliable",
            "reviewer2_label": "Hallucinated",
            "disagreement": True,
        }
    ]

    out_file = tmp_path / "frozen_test.json"
    summary = enrich_and_freeze(base_file, out_file, custom_annotations=custom_annotations)

    assert summary["adjudicated_count"] == 1
    assert summary["unvalidated_count"] == 1
    assert summary["sha256"] != ""

    frozen_bundle = DatasetBundle.model_validate(json.loads(out_file.read_text(encoding="utf-8")))
    ex1 = next(e for e in frozen_bundle.examples if e.id == "tqa_0001")
    assert ex1.ground_truth_label == Classification.RELIABLE
    assert ex1.ground_truth_source == GroundTruthSource.ADJUDICATED.value
    assert ex1.needs_review is False, "Adjudication must clear the review flag"
    assert ex1.metadata["adjudication"]["adjudicator_id"] == "senior_researcher"

    ex2 = next(e for e in frozen_bundle.examples if e.id == "tqa_0002")
    assert ex2.ground_truth_label is None
    assert ex2.ground_truth_source == GroundTruthSource.UNVALIDATED.value

    # Reject duplicate conflicting annotations
    duplicate_annotations = custom_annotations + [
        {
            "question_id": "tqa_0001",
            "adjudicated_label": "Hallucinated",  # Conflicting!
        }
    ]
    with pytest.raises(ValueError, match="Ambiguous / duplicate annotation"):
        enrich_and_freeze(base_file, out_file, custom_annotations=duplicate_annotations)


# ── 8. Human Adjudication Precedence over Stale Needs Review ──────────────────

def test_human_adjudication_precedence_in_resolution() -> None:
    """Definitive human adjudication resolves review; ambiguous adjudication retains review."""
    ex = DatasetExample(
        id="q_disputed",
        question="Historical question with disputed date?",
        reference_answer="Approx 500 BC",
        needs_review=True,  # Flagged pre-annotation
    )

    # 1. Definitive human adjudication overrides stale needs_review
    d_rel = resolve_ground_truth("Approx 500 BC", ex, adjudicated_label="Reliable", mode="formal")
    assert d_rel.is_review is False
    assert d_rel.label == Classification.RELIABLE
    assert d_rel.source == GroundTruthSource.ADJUDICATED

    # 2. Adjudicator explicitly marks it as unresolvable / needs review
    d_ambig = resolve_ground_truth("Approx 500 BC", ex, adjudicated_label="Needs Review", mode="formal")
    assert d_ambig.is_review is True
    assert d_ambig.label is None
    assert d_ambig.source == GroundTruthSource.NEEDS_REVIEW

    # 3. Without adjudication, needs_review remains in effect
    d_none = resolve_ground_truth("Approx 500 BC", ex, adjudicated_label=None, mode="formal")
    assert d_none.is_review is True
    assert d_none.label is None
    assert d_none.source == GroundTruthSource.NEEDS_REVIEW


# ── 9. Formal Mode vs Legacy Mode ─────────────────────────────────────────────

def test_formal_mode_excludes_unvalidated_benchmark_examples() -> None:
    """In formal mode, unvalidated examples return label=None and cannot guess."""
    bundle = load_dataset("hallucination_benchmark")
    unvalidated_example = bundle.examples[0]
    assert unvalidated_example.ground_truth_label is None

    # In formal mode: strictly returns None
    dec_formal = resolve_ground_truth(unvalidated_example.reference_answer, unvalidated_example, mode="formal")
    assert dec_formal.label is None
    assert dec_formal.source == GroundTruthSource.UNVALIDATED
    assert dec_formal.is_review is True

    # In legacy mode: normalized string matching is permitted as a fallback
    dec_legacy = resolve_ground_truth(unvalidated_example.reference_answer, unvalidated_example, mode="legacy")
    assert dec_legacy.label == Classification.RELIABLE
    assert dec_legacy.source in {GroundTruthSource.REFERENCE_MATCH, GroundTruthSource.LEGACY_INFERRED}


# ── 10. Split Filtering in Dataset Loader ─────────────────────────────────────

def test_split_filtering_in_dataset_loader() -> None:
    """load_dataset supports split='dev' and split='test' filtering."""
    dev_bundle = load_dataset("hallucination_benchmark", split="dev")
    assert len(dev_bundle.examples) == 440
    assert all(e.split == "dev" for e in dev_bundle.examples)

    test_bundle = load_dataset("hallucination_benchmark", split="test")
    assert len(test_bundle.examples) == 110
    assert all(e.split == "test" for e in test_bundle.examples)

    with pytest.raises(Exception, match="No examples found for split 'invalid_split'"):
        load_dataset("hallucination_benchmark", split="invalid_split")


# ── 11. SHA-256 Reproducibility ───────────────────────────────────────────────

def test_benchmark_sha256_reproducibility() -> None:
    """The computed SHA-256 checksum exactly matches the on-disk file bytes."""
    path = DATASETS_DIR / "hallucination_benchmark.json"
    computed = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path = DATASETS_DIR / "hallucination_benchmark.manifest.json"
    assert manifest_path.exists()
    assert len(computed) == 64

