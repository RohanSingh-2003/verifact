# Evaluation Datasets & Ground-Truth Benchmarks

This directory contains the formal research benchmark datasets and ground-truth specifications used by VeriFact's offline evaluation module (`backend/app/evaluation/`) to measure hallucination detection accuracy against curated and standardized reference facts.

> **Important Notice:** The legacy 40-question development dataset (`pilot.json` and `pilot.manifest.json`) has been **permanently retired and removed** as part of Task 3.1.1. The **550-question formal benchmark** described below is the **sole authorized evaluation dataset** for the VeriFact research framework and paper.

---

## Table of Contents

- [Overview & Formal Benchmark](#overview--formal-benchmark)
- [Benchmark Composition & Architecture](#benchmark-composition--architecture)
  - [1. TruthfulQA (Standardized for VeriFact) (400 items)](#1-truthfulqa-standardized-for-verifact-400-items)
  - [2. FreshQA (150 items)](#2-freshqa-150-items)
- [Dataset Splits & Stratification](#dataset-splits--stratification)
- [Benchmark Sampling Versioning & Reproducibility Architecture](#benchmark-sampling-versioning--reproducibility-architecture)
- [FreshQA Temporal Validation Policy](#freshqa-temporal-validation-policy)
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

### 1. TruthfulQA (Standardized for VeriFact) (400 items)
- **Upstream Source**: Canonical `sylinrl/TruthfulQA` repository ([GitHub](https://github.com/sylinrl/TruthfulQA) / Lin et al., ACL 2022).
- **Upstream Revision / Commit**: `d71c110897f5d31c5d7f309e7bc316c152f6f031` (HEAD on `main`).
- **Source File**: `TruthfulQA.csv` (790 rows across 37 categories).
- **Retrieval Date**: 2026-11-03.
- **License Status**: **Verified Apache-2.0** (explicit `LICENSE` file in repository root covering `TruthfulQA.csv`; confirmed in `README.md` line 8).
- **VeriFact Standardization**: 400 questions sampled using proportional category stratification (Random Seed: 42).
- **Research Role**: Evaluates model susceptibility to widespread human falsehoods, superstitions, cognitive biases, and adversarial misconceptions.
- **Provenance Distinction**: This dataset represents a standardized and sampled subset of canonical TruthfulQA. It is distinct from the unofficial "TruthfulQA-Enhanced" nomenclature previously referenced.

### 2. FreshQA (150 items)
- **Upstream Source**: `freshllms/freshqa` repository ([GitHub](https://github.com/freshllms/freshqa) / Vu et al., ACL 2023).
- **Upstream Revision / Commit**: `7d2d3683991916f3633e480548a6aa5c9a62e3db` (HEAD on `main`).
- **Upstream Release**: FreshQA April 21, 2026 Release ([Google Sheet 1_8mi-yuK30mvoDJu1KQXD6ODem7MKMcIgVAwDSzJkjM](https://docs.google.com/spreadsheets/d/1_8mi-yuK30mvoDJu1KQXD6ODem7MKMcIgVAwDSzJkjM/edit?usp=sharing)).
- **Snapshot Date**: **`2026-04-21`** (April 21, 2026).
- **Retrieval Date**: 2026-11-03.
- **License Qualification**: **Unverified — external Google Sheet dataset licensing requires confirmation.** Upstream code repository (`freshllms/freshqa`) is licensed under Apache-2.0 (verified via explicit `LICENSE` file in repository root). The external Google Sheet snapshot linked from `README.md` does not contain an embedded SPDX license header, and the repository documentation does not explicitly extend the Apache-2.0 license to external Google Drive assets; governed by academic research attribution terms (`arXiv:2310.03214`).
- **Source Snapshot Reproducibility**:
  - Google Sheet ID: `1_8mi-yuK30mvoDJu1KQXD6ODem7MKMcIgVAwDSzJkjM`
  - Sheet Title: `FreshQA April 21, 2026 Release`
  - Export Format: `CSV`
  - Local Cache Path: `backend/data/raw/freshqa.csv` (uncommitted / gitignored)
  - Raw Export Size: `203,598 bytes`
  - Raw Export SHA-256: `861274a4bcd909479ae30a9e1c5b4936c908f718a11211dbd120f3c9477aed73`
  - Immutable Upstream Version ID: `None` (Google Sheets does not provide immutable Git revisions or commit hashes; release date `2026-04-21` is documented in upstream sheet metadata).
- **Research Role**: Evaluates model knowledge across dynamic world facts, time-sensitive updates, and false presuppositions.
- **Volume & Categories**: 150 curated questions partitioned into 3 core temporal categories with 1 orthogonal subcategory:
  1. `never-changing` (57 items): Timeless historical, geographic, and scientific facts.
  2. `slow-changing` (55 items): Multi-year evolving facts (demographics, infrastructure, long-term treaties).
  3. `fast-changing` (38 items): Rapidly updating facts (current leaders, active tournament results, volatile statistics).
  4. `false-premise` (38 items, overlapping): Questions asserting a false claim that require premise refutation.

---

## Dataset Splits & Stratification

- **Total Examples**: 550
- **Random Seed**: 42 (fixed for strict reproducibility)
- **Split Ratio**: 80% Development / 20% Test
  - **Development Set (`split: "dev"`)**: 440 questions (320 TruthfulQA, 120 FreshQA). Used for prompt refinement, threshold calibration, and error analysis.
  - **Test Set (`split: "test"`)**: 110 questions (80 TruthfulQA, 30 FreshQA). Held out exclusively for formal benchmark evaluation.
- **Stratification**: Proportional category balance preserved within both source datasets.

---

## Benchmark Sampling Versioning & Reproducibility Architecture

VeriFact strictly distinguishes between two fundamental reproducibility concepts in benchmark evaluation research:

### 1. Two Distinct Reproducibility Concepts

| Reproducibility Concept | Operational Scope & Mechanism | Research Role |
|:---|:---|:---|
| **Artifact Reproducibility** | Cryptographically locked benchmark files ([`hallucination_benchmark_frozen.json`](hallucination_benchmark_frozen.json) and manifest) with SHA-256 verification hashes. | **Sole authoritative evaluation ground truth.** Guarantees 100% bit-for-bit identical questions, categories, reference answers, and splits for all formal research evaluations and paper results. |
| **Generation Reproducibility** | The deterministic dataset builder algorithm (`sha256_stratified_v1`) implemented in `backend/scripts/prepare_benchmark_datasets.py`. | **Standard for future dataset generation.** Guarantees identical dataset sampling across independent Python processes, operating systems, and `PYTHONHASHSEED` configurations. |

### 2. Historical Sampling Limitation (`hash_stratified_v0`)

The active 550-question benchmark was originally generated using a historical sampling script that relied on Python's built-in `hash()` function for category and stratum seed derivation:
- **Master Random Seed**: `42`.
- **Identified Built-in `hash()` Locations**:
  1. TruthfulQA category sampling: `random.Random(seed + hash(cat))`
  2. TruthfulQA dev/test split assignment: `random.Random(seed + hash(curr_cat))`
  3. TruthfulQA split adjustment tail: `random.Random(seed + hash(curr_cat))`
  4. FreshQA stratum sampling: `random.Random(seed + hash(key))`
  5. FreshQA dev/test split assignment: `random.Random(seed + hash(curr_stratum))`
  6. FreshQA split adjustment tail: `random.Random(seed + hash(curr_stratum))`
- **Unrecorded Process State**: In Python 3 (PEP 456), string hashing is salted with a random 128-bit key at interpreter startup. Because the original execution's `PYTHONHASHSEED` was not preserved, the exact 550-item sample cannot currently be reconstructed from the master seed alone.
- **Research Baseline Preservation**: In accordance with research integrity standards, the frozen benchmark artifact (`hallucination_benchmark_frozen.json`) preserves the exact historical selection and is cryptographically locked as immutable. The benchmark will **not** be regenerated or overwritten.

### 3. Versioned Deterministic Sampling Procedure (`sha256_stratified_v1`)

For all future dataset preparation, VeriFact specifies the **`sha256_stratified_v1`** deterministic sampling procedure:
- **Seed Derivation Function**:
  $$\text{Seed}(\text{key}, \text{base\_seed}) = \text{base\_seed} + \left(\text{int}(\text{SHA-256}(\text{base\_seed} \parallel \text{key})[:8]) \pmod{2^{31} - 1}\right)$$
  Implemented as:
  ```python
  digest = hashlib.sha256(f"{seed}:{key}".encode()).digest()
  offset = int.from_bytes(digest[:8], byteorder="big", signed=False)
  return seed + (offset % 2_147_483_647)
  ```
- **Master Seed**: `42`.
- **Stratum Key Construction**:
  - TruthfulQA: Canonical `category` string (e.g., `advertising`, `science`, `history`).
  - FreshQA: Composite temporal/premise key `f"{fact_type}_fp_{false_premise}"` (e.g., `fast-changing_fp_FALSE`, `slow-changing_fp_TRUE`).
- **Stratified Allocation Procedure**: Proportional category allocation with deterministic remainder resolution sorted by descending stratum size.
- **Deterministic Ordering**: Candidate items are sorted alphabetically by question text within each stratum prior to sampling, and the final output is sorted deterministically by `(stratum, question)`.
- **Partition Assignment**: Exact 80% Development (440 items) / 20% Test (110 items) split with deterministic tail adjustment.
- **Cross-Process Verification**: Fully validated in `backend/tests/test_cross_process_reproducibility.py` across `PYTHONHASHSEED=1`, `PYTHONHASHSEED=123`, and `PYTHONHASHSEED=random`.
- **Important Distinction**: The `sha256_stratified_v1` procedure is the standard for future generation; it did not generate the historical benchmark artifact, which remains frozen and authoritative.

---

## FreshQA Temporal Validation Policy

Because evaluation occurs chronologically after the **`2026-04-21`** snapshot date, external search systems may retrieve present-day information published after the snapshot. VeriFact enforces a formal **Temporal Validation Policy** (full specification in [`docs/temporal_validation_policy.md`](../../docs/temporal_validation_policy.md)):

1. **Benchmark Reference Time**: All facts are evaluated strictly against the snapshot date `2026-04-21`. Present-day information must never be silently substituted for historical truth.
2. **Retrospective Sources Permitted**: Retrospective sources published after April 21, 2026 (e.g. historical timelines, revision logs, official tenure records) are explicitly permitted when they reliably establish the factual state on or before April 21, 2026.
3. **Four-Tier Evidence Classification**:
   - `SUPPORTED`: Date-anchored evidence confirms claim as of `2026-04-21`.
   - `CONTRADICTED`: Date-anchored evidence disproves claim as of `2026-04-21`.
   - `INSUFFICIENT`: Available evidence cannot establish historical truth or falsity at the snapshot time (evaluator abstains; does not penalize model).
   - `UNASSESSED`: External search infrastructure failed or timed out (distinguished from insufficient evidence).
4. **Temporal Uncertainty Protocol**: If real-world changes occurred after April 2026, the model's snapshot-accurate answer is upheld as Reliable. Inconclusive or dated evidence must not be automatically labeled hallucinated.
5. **Slow-Changing Rule**: A publication window of ±1–2 years is **not** by itself sufficient evidence; retrieved evidence must establish that the specific fact was valid on `2026-04-21`, taking into account any intervening events. Retrospective post-snapshot sources remain valid if reliably documenting historical state.
6. **Fast-Changing Rule**: The 38 fast-changing questions require explicit date-anchored evidence to avoid anachronistic false contradictions.
7. **False-Premise Two-Step Protocol**: Evaluators must execute a strict two-step protocol: (1) independently verify that the premise was false on `2026-04-21`; (2) assess whether candidate answer recognizes and refutes the false premise. Supported refutation is scored Reliable; accepting or fabricating from the premise is scored Hallucinated; ambiguous responses cause the evaluator to abstain. Presupposition falsity alone never triggers an automatic label.

---

## Dataset Format Specifications

### 1. JSON Benchmark Schema

Each item in `hallucination_benchmark.json` and `hallucination_benchmark_frozen.json` adheres to the following structure:

```json
{
  "id": "tqa_0001",
  "question": "How long do diamonds last?",
  "reference_answer": "Diamonds last between 1 and 4 billion years",
  "aliases": [],
  "ground_truth_label": null,
  "ground_truth_source": "unvalidated",
  "category": "advertising",
  "dataset": "truthfulqa",
  "question_type": "adversarial",
  "split": "dev",
  "snapshot_date": null,
  "needs_review": false,
  "metadata": {}
}
```

### 2. Manifest Schema

The companion manifest (`hallucination_benchmark_frozen.manifest.json`) defines verification parameters:
- `dataset_name`: Dataset identifier (`hallucination_benchmark_frozen`).
- `dataset_version`: Canonical release version (`1.0-frozen`).
- `provenance`: Upstream repositories, citations, format, and record counts.
- `ground_truth_policy`: Rules governing ground truth adjudication.
- `item_count`: Total items (550).
- `items`: Item summaries with question ID, reference answer, source, and split.

---

## Ground-Truth Resolution & Precedence Hierarchy

Ground-truth resolution follows a formal 4-tiered precedence hierarchy in [`backend/app/evaluation/ground_truth.py`](backend/app/evaluation/ground_truth.py):

1. **Review Flag (`needs_review: true`)**: If an item is flagged for human review or exhibits ambiguity, it is categorized as `NEEDS_REVIEW` and excluded from precision/recall calculations.
2. **Adjudicated (`ADJUDICATED`)**: High-confidence labels synthesized from concordant multi-judge consensus and expert adjudication.
3. **Manual Human Annotation (`MANUAL`)**: Gold-standard labels verified directly by domain expert annotators.
4. **Validated Machine Label (`VALIDATED`)**: High-confidence LLM judge evaluations with structured rationales.
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
3. MetaQA generates synonym and antonym metamorphic mutations.
4. Verifiers score mutations using Eq. 5 deterministic scoring matrix.
5. Predictions ($H \ge \theta \implies \text{Hallucinated}$) populate the confusion matrix.

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
