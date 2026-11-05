# Evaluation Datasets & Ground-Truth Benchmarks

This directory contains the formal research benchmark datasets and ground-truth specifications used by VeriFact's offline evaluation module (`backend/app/evaluation/`) to measure hallucination detection accuracy against curated and standardized reference facts.

> **Important Notice:** The legacy 40-question development dataset (`pilot.json` and `pilot.manifest.json`) has been **permanently retired and removed** as part of Task 3.1.1. The **550-question formal benchmark** described below is the **sole authorized evaluation dataset** for the VeriFact research framework and paper.

---

## Table of Contents

- [Overview & Formal Benchmark](#overview--formal-benchmark)
- [Benchmark Composition & Architecture](#benchmark-composition--architecture)
  - [1. TruthfulQA-Enhanced (400 items)](#1-truthfulqa-enhanced-400-items)
  - [2. FreshQA (150 items)](#2-freshqa-150-items)
- [Dataset Splits & Stratification](#dataset-splits--stratification)
- [Dataset Format Specifications](#dataset-format-specifications)
  - [1. JSON Benchmark Schema](#1-json-benchmark-schema)
  - [2. Manifest Schema](#2-manifest-schema)
- [Ground-Truth Resolution & Precedence Hierarchy](#ground-truth-resolution--precedence-hierarchy)
- [Evaluation Workflow & Execution](#evaluation-workflow--execution)
- [Persistence & Export](#persistence--export)
- [Distinction: Offline Benchmarks vs. Live Detection](#distinction-offline-benchmarks-vs-live-detection)
- [Historical Benchmark Results & Run Status](#historical-benchmark-results--run-status)

---

## Overview & Formal Benchmark

VeriFact's evaluation engine measures whether the MetaQA hallucination detector accurately identifies fact-conflicting statements when evaluated against standardized gold-standard questions.

Active dataset files in this directory:
- **`hallucination_benchmark.json`**: Active formal benchmark containing 550 questions with adjudicated ground truth, enriched metadata, and stratified splits.
- **`hallucination_benchmark.manifest.json`**: Manifest documenting dataset provenance, category distributions, splits, and checksums.
- **`hallucination_benchmark_frozen.json`**: Cryptographically frozen, immutable version of the 550-question formal benchmark for research reproducibility.
- **`hallucination_benchmark_frozen.manifest.json`**: Cryptographically frozen manifest with SHA-256 verification hash.

---

## Benchmark Composition & Architecture

The formal benchmark combines static fact-conflicting misconceptions and dynamic temporal queries into a single unified 550-question benchmark:

### 1. TruthfulQA-Enhanced (400 items)
- **Source**: TruthfulQA (Lin et al., ACL 2022) with standardized corrections and fact-checking references.
- **Target**: Evaluates model susceptibility to common human falsehoods, superstitions, logical fallacies, and misconceptions.
- **Volume**: 400 curated questions across diverse categories (misconceptions, science, history, law, psychology, etc.).

### 2. FreshQA (150 items)
- **Source**: FreshQA (Vu et al., 2023) dynamic evaluation benchmark.
- **Target**: Evaluates model awareness of dynamic, time-sensitive, and false-premise world knowledge.
- **Volume**: 150 questions across 4 core temporal categories:
  1. `fast-changing`: Frequently updating world facts (e.g., current officeholders, recent champions).
  2. `slow-changing`: Facts that evolve over multi-year horizons (e.g., population milestones, infrastructure projects).
  3. `never-changing`: Timeless historical and scientific ground-truth facts.
  4. `false-premise`: Questions presupposing a false claim, requiring explicit premise refutation.

---

## Dataset Splits & Stratification

- **Total Examples**: 550
- **Random Seed**: 42 (fixed for strict reproducibility)
- **Split Ratio**: 80% Development / 20% Test
  - **Development Set (`split: "dev"`)**: 440 questions (320 TruthfulQA, 120 FreshQA). Used for prompt refinement, threshold calibration, and error analysis.
  - **Test Set (`split: "test"`)**: 110 questions (80 TruthfulQA, 30 FreshQA). Held out exclusively for formal benchmark evaluation.
- **Stratification**: Balanced across source categories where category counts permit.

---

## Dataset Format Specifications

### 1. JSON Benchmark Schema

Each item in `hallucination_benchmark.json` and `hallucination_benchmark_frozen.json` adheres to the following structure:

```json
{
  "id": "tqa_001",
  "question": "What is the capital of Australia?",
  "reference_answer": "Canberra",
  "aliases": ["Canberra, Australia", "City of Canberra"],
  "ground_truth_label": "Reliable",
  "ground_truth_source": "Adjudicated",
  "ground_truth_reasoning": "Adjudicated unanimous agreement across gold reference and human consensus.",
  "category": "location",
  "source": "truthfulqa",
  "split": "dev",
  "temporal_category": "never-changing",
  "needs_review": false
}
```

### 2. Manifest Schema

The companion manifest (`hallucination_benchmark_frozen.manifest.json`) defines verification parameters:
- `name`: Dataset identifier (`hallucination_benchmark_frozen`).
- `version`: Canonical release version (`1.0.0`).
- `checksum`: SHA-256 integrity hash of the frozen JSON file.
- `splits`: Breakdown of dev (440) and test (110) counts.
- `sources`: Source-specific question counts and provenance URLs.

---

## Ground-Truth Resolution & Precedence Hierarchy

Ground-truth resolution follows a formal 4-tiered precedence hierarchy in [`backend/app/evaluation/ground_truth.py`](backend/app/evaluation/ground_truth.py):

1. **Review Flag (`needs_review: true`)**: If an item is flagged for human review or exhibits ambiguity, it is categorized as `NEEDS_REVIEW` and excluded from precision/recall calculations.
2. **Adjudicated (`ADJUDICATED`)**: High-confidence labels synthesized from concordant multi-judge consensus and expert adjudication.
3. **Manual Human Annotation (`MANUAL`)**: Gold-standard labels verified directly by domain expert annotators.
4. **Validated Machine Label (`VALIDATED`)**: High-confidence LLM judge evaluations (e.g. Gemini 3.8 Flash) with structured rationales.
5. **Unvalidated Fallback (`UNVALIDATED`)**: In formal evaluation mode, unadjudicated benchmark items without explicit labels are rejected rather than falling back to naive reference string matching.

---

## Evaluation Workflow & Execution

Formal evaluations are initiated via the REST API or programmatic runners:

```bash
# Run formal evaluation on the frozen 550-question test split
curl -X POST http://127.0.0.1:8000/api/evaluations/run \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "hallucination_benchmark_frozen",
    "split": "test",
    "threshold": 0.5,
    "name": "Formal Test Benchmark @ 0.50",
    "generator_model": "gemma4:26b",
    "verifier_model": "gemini-3.8-flash"
  }'
```

Execution pipeline:
1. Load dataset split via `load_dataset()`.
2. Generator (Gemma 4:26B) produces candidate answers.
3. Independent Gemini Research Judge evaluates candidate answers against reference facts.
4. MetaQA generates synonym and antonym metamorphic mutations.
5. Verifiers score mutations using Eq. 5 deterministic scoring matrix.
6. Predictions ($H \ge \theta \implies \text{Hallucinated}$) populate the confusion matrix.

---

## Persistence & Export

- **Database Models**:
  - `EvaluationRun`: Run metadata, configuration snapshot, execution mode, and category performance.
  - `EvaluationResult`: Question-level traces, candidate answers, ground-truth labels, predicted classifications, and MetaQA scores.
  - `EvaluationMetric`: Accuracy, precision, recall, F1, specificity, FPR, FNR across thresholds.
- **CSV Export**:
  - Download complete item-level results: `GET /api/evaluations/{id}/export`.

---

## Distinction: Offline Benchmarks vs. Live Detection

| Aspect | Offline Evaluation Module | Live Detect Feature |
| :--- | :--- | :--- |
| **Objective** | Measure detector accuracy against known ground-truth labels. | Provide real-time explainable hallucination analysis for arbitrary user questions. |
| **Input** | Static formal benchmark (`hallucination_benchmark_frozen.json`). | Ad-hoc user-submitted question. |
| **Ground Truth** | Curated reference answers, adjudicated labels, and source metadata. | **Reference-free**: No ground-truth answer exists or is consulted. |
| **Verification** | MetaQA metamorphic testing over dataset answers. | **Three-branch**: MetaQA metamorphic testing + Direct-Answer Multi-Model Peer Review + real-time Tavily Web Evidence search. |
| **Output** | Precision, Recall, F1, confusion matrix, threshold curves. | Candidate answer, mutation breakdowns, peer review consensus, web source cards, Overall VeriFact Assessment. |

---

## Historical Benchmark Results & Run Status

- **Locked Research Run**:
  - Run ID: `58baff20-fb86-4f43-b20e-895a086ceb6b` (documented in [`docs/final_results_lock.md`](docs/final_results_lock.md)).
  - **Status**: Executed in **`mock` mode (DEMO / MOCK DATA)** on 40 questions from the legacy pilot dataset using synthetic client fixtures (`model-a`, `model-b`).
  - **Notice**: The legacy 40-question pilot dataset used in that initial mock run has been permanently retired and removed.
- **Stopped / Unexecuted Live Experiment**:
  - Intended live 2×2 experiment configuration (`experiments/config/final_experiment.yaml` for `gpt-4o-mini` vs. `gpt-4o`) was **frozen as NOT EXECUTED** due to missing live API credentials.
  - Formal live research experiments will be executed exclusively on `hallucination_benchmark_frozen.json`.
