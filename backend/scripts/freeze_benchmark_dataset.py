#!/usr/bin/env python3
"""Freeze benchmark dataset by deterministically enriching it with human annotations.

This script implements deterministic, audit-compliant ground-truth enrichment:
1. Loads the base benchmark dataset (e.g. hallucination_benchmark.json).
2. Connects to the VeriFact database to query finalized HumanAnnotation records.
3. Matches records strictly by stable question_id (never heuristic substring matching).
4. Injects adjudicated_label, sets ground_truth_source='adjudicated', and clears needs_review.
5. Preserves unadjudicated questions as unvalidated (Gemini verdicts NEVER auto-promote).
6. Calculates the SHA-256 checksum and produces a frozen, version-locked JSON release artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.db import SessionLocal, init_db
from app.database.models import HumanAnnotation
from app.evaluation.dataset_loader import DATASETS_DIR, write_manifest
from app.evaluation.schemas import DatasetBundle, DatasetExample, GroundTruthSource
from app.metaqa.scoring import Classification

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verifact.freeze_benchmark")


def get_current_git_commit() -> str:
    """Retrieve current Git commit hash if in a Git repository."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=True,
        )
        return res.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def enrich_and_freeze(
    base_dataset_path: Path,
    output_path: Path,
    db: Session | None = None,
    custom_annotations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deterministically enrich base dataset with human annotations and write a frozen release."""
    if not base_dataset_path.exists():
        raise FileNotFoundError(f"Base dataset not found: {base_dataset_path}")

    raw_payload = json.loads(base_dataset_path.read_text(encoding="utf-8"))
    examples_raw = raw_payload.get("examples", [])
    if not examples_raw:
        raise ValueError(f"Base dataset {base_dataset_path} contains no examples.")

    logger.info("Loaded base dataset '%s' with %d examples", raw_payload.get("name"), len(examples_raw))

    # Retrieve adjudicated human annotations
    adjudicated_map: dict[str, dict[str, Any]] = {}
    
    if custom_annotations is not None:
        # Programmatic injection (used in tests or offline workflows)
        for annot in custom_annotations:
            q_id = annot.get("question_id")
            if not q_id:
                continue
            if q_id in adjudicated_map:
                raise ValueError(f"Ambiguous / duplicate annotation for question_id '{q_id}'")
            adjudicated_map[q_id] = annot
    else:
        # Query from database
        close_db_after = False
        if db is None:
            init_db()
            db = SessionLocal()
            close_db_after = True

        try:
            stmt = select(HumanAnnotation).where(
                HumanAnnotation.adjudicated_label.is_not(None),
                HumanAnnotation.validation_status == "adjudicated",
            )
            rows = db.scalars(stmt).all()
            logger.info("Found %d finalized human adjudication records in database", len(rows))

            for r in rows:
                q_id = r.question_id
                if q_id in adjudicated_map:
                    prev = adjudicated_map[q_id]
                    if prev["adjudicated_label"] != r.adjudicated_label:
                        raise ValueError(
                            f"Ambiguous conflicting human annotations for question_id '{q_id}': "
                            f"'{prev['adjudicated_label']}' vs '{r.adjudicated_label}'"
                        )
                adjudicated_map[q_id] = {
                    "question_id": r.question_id,
                    "adjudicated_label": r.adjudicated_label,
                    "adjudicator_id": r.adjudicator_id,
                    "adjudication_notes": r.adjudication_notes,
                    "adjudication_evidence": r.adjudication_evidence,
                    "reviewer1_label": r.reviewer1_label,
                    "reviewer2_label": r.reviewer2_label,
                    "disagreement": r.disagreement,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
        finally:
            if close_db_after and db is not None:
                db.close()

    enriched_examples: list[DatasetExample] = []
    adjudicated_count = 0
    unvalidated_count = 0

    for item in examples_raw:
        ex = DatasetExample.model_validate(item)
        q_id = ex.id

        if q_id in adjudicated_map:
            ann = adjudicated_map[q_id]
            raw_label = str(ann["adjudicated_label"]).strip().capitalize()
            if raw_label in {Classification.RELIABLE.value, Classification.HALLUCINATED.value}:
                ex.ground_truth_label = Classification(raw_label)
                ex.ground_truth_source = GroundTruthSource.ADJUDICATED.value
                # Successful adjudication satisfies and clears the review flag
                ex.needs_review = False
                ex.metadata["adjudication"] = {
                    "adjudicator_id": ann.get("adjudicator_id"),
                    "notes": ann.get("adjudication_notes"),
                    "evidence": ann.get("adjudication_evidence"),
                    "reviewer1_label": ann.get("reviewer1_label"),
                    "reviewer2_label": ann.get("reviewer2_label"),
                    "disagreement": ann.get("disagreement", False),
                    "frozen_at": datetime.now(UTC).isoformat(),
                }
                adjudicated_count += 1
            else:
                # If human adjudicator marked it as unresolvable / needs review
                ex.ground_truth_label = None
                ex.ground_truth_source = GroundTruthSource.NEEDS_REVIEW.value
                ex.needs_review = True
                unvalidated_count += 1
        else:
            # Unadjudicated items remain strictly unvalidated
            if ex.ground_truth_label is None:
                ex.ground_truth_source = GroundTruthSource.UNVALIDATED.value
                unvalidated_count += 1
            else:
                adjudicated_count += 1

        enriched_examples.append(ex)

    frozen_bundle = DatasetBundle(
        name=output_path.stem,
        version="1.0-frozen",
        description=f"Frozen research benchmark release enriched from {base_dataset_path.name}",
        license=raw_payload.get("license", "Apache-2.0"),
        source=raw_payload.get("source", "VeriFact Human Adjudication Pipeline"),
        examples=enriched_examples,
    )

    git_hash = get_current_git_commit()
    timestamp = datetime.now(UTC).isoformat()

    frozen_dict = {
        "name": frozen_bundle.name,
        "version": frozen_bundle.version,
        "base_dataset": base_dataset_path.name,
        "frozen_timestamp": timestamp,
        "git_commit": git_hash,
        "item_count": len(enriched_examples),
        "adjudicated_examples_count": adjudicated_count,
        "unvalidated_examples_count": unvalidated_count,
        "coverage": round(adjudicated_count / len(enriched_examples), 4) if enriched_examples else 0.0,
        "split_summary": {
            "dev_total": sum(1 for e in enriched_examples if e.split == "dev"),
            "dev_adjudicated": sum(1 for e in enriched_examples if e.split == "dev" and e.ground_truth_label is not None),
            "test_total": sum(1 for e in enriched_examples if e.split == "test"),
            "test_adjudicated": sum(1 for e in enriched_examples if e.split == "test" and e.ground_truth_label is not None),
        },
        "examples": [e.model_dump() for e in enriched_examples],
    }

    output_bytes = json.dumps(frozen_dict, indent=2).encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output_bytes)

    sha256 = hashlib.sha256(output_bytes).hexdigest()
    logger.info("Successfully wrote frozen benchmark to %s (%d bytes)", output_path, len(output_bytes))
    logger.info("SHA-256 Checksum: %s", sha256)

    # Write companion manifest
    write_manifest(frozen_bundle, output_path.with_suffix(".manifest.json"))

    return {
        "output_path": str(output_path),
        "sha256": sha256,
        "total_count": len(enriched_examples),
        "adjudicated_count": adjudicated_count,
        "unvalidated_count": unvalidated_count,
        "git_commit": git_hash,
        "timestamp": timestamp,
        "dev_total": frozen_dict["split_summary"]["dev_total"],
        "dev_adjudicated": frozen_dict["split_summary"]["dev_adjudicated"],
        "test_total": frozen_dict["split_summary"]["test_total"],
        "test_adjudicated": frozen_dict["split_summary"]["test_adjudicated"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze benchmark dataset with human annotations")
    parser.add_argument(
        "--input",
        type=Path,
        default=DATASETS_DIR / "hallucination_benchmark.json",
        help="Input base benchmark dataset path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DATASETS_DIR / "hallucination_benchmark_frozen.json",
        help="Output frozen release dataset path",
    )
    args = parser.parse_args()

    logger.info("Freezing benchmark dataset from %s -> %s", args.input, args.output)
    result = enrich_and_freeze(args.input, args.output)

    print("\n" + "=" * 70)
    print("VERIFACT FROZEN BENCHMARK RELEASE REPORT")
    print("=" * 70)
    print(f"Release Artifact:     {Path(result['output_path']).name}")
    print(f"Total Examples:       {result['total_count']}")
    print(f"Adjudicated Examples: {result['adjudicated_count']} ({result['adjudicated_count'] / result['total_count'] * 100:.1f}%)")
    print(f"Unvalidated Examples: {result['unvalidated_count']} ({result['unvalidated_count'] / result['total_count'] * 100:.1f}%)")
    print(f"Dev Split:            {result['dev_total']} total ({result['dev_adjudicated']} adjudicated)")
    print(f"Test Split:           {result['test_total']} total ({result['test_adjudicated']} adjudicated)")
    print(f"Git Commit Hash:      {result['git_commit']}")
    print(f"SHA-256 Checksum:     {result['sha256']}")
    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

