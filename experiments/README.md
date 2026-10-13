# Experiment Artifacts & Historical Research Archive

> **Archival Notice:**
> This directory is a **historical research archive**. The original 2×2 same-model versus cross-model experiment execution engine, batch runner service (`experiment_service.py`), and associated endpoints (`/api/experiments/*`) have been **retired and removed from the active codebase**.
> The interactive VeriFact product focuses on real-time, three-branch hallucination detection (MetaQA, Direct-Answer Multi-Model Review, and Web Evidence Grounding) across cloud-hosted models, alongside a standalone dataset evaluation API (`/api/evaluations/*`).

---

## Table of Contents

- [Archival Status & Research Purpose](#archival-status--research-purpose)
- [The Historical 2×2 Research Question](#the-historical-22-research-question)
- [Locked Historical Mock Run (`58baff20`)](#locked-historical-mock-run-58baff20)
- [Unexecuted Live Experiment Configuration (`final_experiment.yaml`)](#unexecuted-live-experiment-configuration-final_experimentyaml)
- [Archived Directory Organization](#archived-directory-organization)
- [Scientific Caution & Methodological Limitations](#scientific-caution--methodological-limitations)
- [Related Research Documentation](#related-research-documentation)

---

## Archival Status & Research Purpose

During earlier research phases of VeriFact, an offline 2×2 experimental harness was built to test whether Large Language Models exhibit systematic self-confirmation bias when verifying mutations of their own answers.

Following completion and auditing of that baseline research:
1. The batch experiment runner service and experiment API routes were **permanently retired**.
2. Automated test run residues were cleaned from the repository.
3. The baseline mock study traces and design-time live configuration were preserved in this directory as **immutable research records** to ensure auditability and scientific reproducibility.

---

## The Historical 2×2 Research Question

The 2×2 factorial study evaluated whether a model verifying mutations of its own answer exhibits systematic self-confirmation bias compared to an independent cross-model verifier:

- **Condition $A \to A$**: Model A generates answer and mutations; Model A verifies.
- **Condition $A \to B$**: Model A generates answer and mutations; Model B verifies.
- **Condition $B \to A$**: Model B generates answer and mutations; Model A verifies.
- **Condition $B \to B$**: Model B generates answer and mutations; Model B verifies.

### Invariance Protocol
To isolate verifier calibration confounds from answer generation differences, the protocol enforced strict invariance:
- The base generated answer, extracted factual claims, and exact mutation statements were generated once and held constant.
- Only the verifier identity was swapped across experimental conditions.

---

## Locked Historical Mock Run (`58baff20`)

The primary historical artifact preserved in this repository is:

- **Run ID**: `58baff20-fb86-4f43-b20e-895a086ceb6b`
- **Execution Mode**: **`mock` (DEMO / MOCK DATA)**
- **Execution Timestamp**: Started `2026-09-04T11:25:23.102104+00:00`, completed in 0.61s.
- **Dataset Evaluated**: `backend/data/datasets/pilot.json` (40 curated factual questions across 5 categories).
- **Models Used**: Deterministic mock identifiers `model-a` and `model-b`.
- **Review Exclusions**: 2 items (`q032`, `q039`) flagged with `needs_review: true` are excluded from automated metrics, evaluating across the remaining 38 labeled items.
- **Audit Lock Specification**: Formally recorded in [`docs/final_results_lock.md`](../docs/final_results_lock.md).

---

## Unexecuted Live Experiment Configuration (`final_experiment.yaml`)

- **Configuration File**: [`experiments/config/final_experiment.yaml`](config/final_experiment.yaml)
- **Status**: **FROZEN, NOT EXECUTED**
- **Intended Models**: Generator A & Verifier A = `gpt-4o-mini`; Generator B & Verifier B = `gpt-4o`.
- **Reason Not Run**: The execution environment operated under `LLM_MODE=mock` and live cloud credentials were not configured. To uphold academic integrity and prevent unbudgeted API consumption, the intended live run was frozen as not executed.
- **Academic Standard**: **No live 2×2 benchmark was ever run.** The locked mock run records must **never** be cited or represented as empirical findings about live LLM self-verification behavior.

---

## Archived Directory Organization

Following the repository cleanup, this directory contains exclusively the locked historical artifacts:

```text
experiments/
├── README.md               # Historical research archive guide (this file)
├── charts/                 # Empty placeholder directory
├── config/
│   └── final_experiment.yaml # Frozen design-time live configuration (not executed)
├── raw/
│   └── 58baff20-fb86-4f43-b20e-895a086ceb6b/
│       ├── experiment_config.json
│       └── generation_traces.json
├── processed/
│   └── 58baff20-fb86-4f43-b20e-895a086ceb6b/
│       ├── category_analysis.csv
│       ├── classification_flips.csv
│       ├── condition_summary.csv
│       ├── exclusions.json
│       ├── experiment_config.json
│       ├── paired_comparisons.csv
│       ├── question_level_results.csv
│       └── threshold_sweep.csv
└── results/
    └── 58baff20-fb86-4f43-b20e-895a086ceb6b/
        ├── chart1_condition_means.png
        ├── chart2_score_difference.png
        ├── chart3_flip_rate.png
        ├── chart4_threshold_sweep.png
        ├── chart5_category.png
        ├── experiment_config.json
        └── results_summary.md
```

| Path | Preserved Content & Purpose |
| :--- | :--- |
| **`config/`** | Contains `final_experiment.yaml` (design-time intended live configuration frozen at design time). |
| **`raw/58baff20.../`** | Raw per-question generation traces, atomic claims, and mutation sets for the 40 pilot questions. |
| **`processed/58baff20.../`** | Processed condition tables, paired score differences, and threshold sweep data. |
| **`results/58baff20.../`** | High-resolution condition comparison charts, config snapshot, and markdown results summary. |
| **`charts/`** | Preserved directory structure; active figures for the locked run are organized inside `results/58baff20.../` and [`analysis/output/`](../analysis/output/). |

---

## Scientific Caution & Methodological Limitations

Within the locked mock run (`58baff20-fb86-4f43-b20e-895a086ceb6b`), hallucination scores tracked **verifier identity**:
- Verifier A assigned score `0.0` in both $A \to A$ and $B \to A$.
- Verifier B assigned score `1.0` in both $A \to B$ and $B \to B$.
- This caused paired differences to equal $-1.0$ for Generator A and $+1.0$ for Generator B.

This pattern is a deterministic calibration characteristic of the mock test fixtures, **not** empirical evidence of LLM self-verification behavior in the real world. The core scientific question regarding live LLM self-confirmation bias remains open for future empirical study.

---

## Related Research Documentation

- [`docs/final_results_lock.md`](../docs/final_results_lock.md): Full audit lock of the frozen 40-question mock run.
- [`analysis/output/`](../analysis/output/): Standalone copy of the locked mock study tables and charts.
- [`backend/data/datasets/README.md`](../backend/data/datasets/README.md): Documentation of the 40-question curated `pilot.json` benchmark dataset.
