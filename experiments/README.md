# Experiment Artifacts & Research Reference

This directory preserves offline research artifacts, frozen configuration snapshots, raw generation traces, processed tables, and visual charts from the 2×2 same-model versus cross-model verifier investigation ($A \to A, A \to B, B \to A, B \to B$).

---

## Table of Contents

- [Overview & Research Question](#overview--research-question)
- [Locked Research Run (`58baff20`)](#locked-research-run-58baff20)
- [Unexecuted Live Experiment (`final_experiment.yaml`)](#unexecuted-live-experiment-final_experimentyaml)
- [Directory Organization](#directory-organization)
- [Relationship to Primary Product](#relationship-to-primary-product)
- [Key Findings & Scientific Caution](#key-findings--scientific-caution)
- [Related Documentation](#related-documentation)

---

## Overview & Research Question

The 2×2 experiment investigated whether a model verifying mutations of its own answer exhibits systematic self-confirmation bias compared to an independent cross-model verifier:
- **Condition $A \to A$**: Model A generates answer and mutations; Model A verifies.
- **Condition $A \to B$**: Model A generates answer and mutations; Model B verifies.
- **Condition $B \to A$**: Model B generates answer and mutations; Model A verifies.
- **Condition $B \to B$**: Model B generates answer and mutations; Model B verifies.

The experimental protocol held the generated answer, extracted claims, and mutation sets strictly constant while swapping the verifier model.

---

## Locked Research Run (`58baff20`)

The primary historical artifact preserved in this repository is:
- **Run ID**: `58baff20-fb86-4f43-b20e-895a086ceb6b`
- **Execution Mode**: **`mock` (DEMO / MOCK DATA)**
- **Timestamp**: Started `2026-09-04T11:25:23.102104+00:00`, completed in 0.61s.
- **Dataset**: `backend/data/datasets/pilot.json` (40 curated questions, 8 per category).
- **Models Used**: Deterministic mock identifiers `model-a` and `model-b`.
- **Exclusions**: 2 items (`q032`, `q039`) flagged as `needs_review` are excluded from automatic Precision/Recall/F1 metrics, leaving 38 labeled items.
- **Stored Artifact Path**: `experiments/results/58baff20-fb86-4f43-b20e-895a086ceb6b/`.

---

## Unexecuted Live Experiment (`final_experiment.yaml`)

- **Configuration File**: [`experiments/config/final_experiment.yaml`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/experiments/config/final_experiment.yaml)
- **Status**: **FROZEN, NOT EXECUTED**
- **Intended Models**: Generator A & Verifier A = `gpt-4o-mini`; Generator B & Verifier B = `gpt-4o`.
- **Reason Not Run**: The runtime environment operated with `LLM_MODE=mock` and live API keys were not configured. To preserve academic integrity and avoid unbudgeted API consumption, the intended live run was frozen as not executed.
- **Academic Standard**: No live 2×2 benchmark was ever run. The locked results are mock demonstration data only and must **never** be cited as empirical findings about live LLM self-verification.

---

## Directory Organization

| Directory | Purpose |
| :--- | :--- |
| **`config/`** | Contains `final_experiment.yaml` (intended live configuration frozen at design time). |
| **`raw/`** | Raw per-question generation traces, mutation sets, and verifier payloads. |
| **`processed/`** | Structured condition tables, paired score differences, and threshold sweep data. |
| **`results/`** | Subdirectories per experiment ID containing `results_summary.md`, `experiment_config.json`, and charts. |
| **`charts/`** | Visual figures illustrating mean scores, paired differences, flip rates, and threshold curves. |

---

## Relationship to Primary Product

- **Independent from Interactive Detect UI**: The 2×2 study was an offline research investigation. The main user-facing application focuses on live, interactive hallucination detection across current cloud models (Gemma 4:26B, Gemini Flash 3.8, GLM-4.7-Flash, Qwen-2.5-32B, OpenRouter).
- **Preserved Research Records**: Historical experiment runs and analysis tables are retained as frozen research records, while the interactive application and live evaluation APIs operate independently.

---

## Key Findings & Scientific Caution

Within the locked mock run (`58baff20-fb86-4f43-b20e-895a086ceb6b`), hallucination scores tracked **verifier identity**:
- Verifier A assigned score `0.0` in both $A \to A$ and $B \to A$.
- Verifier B assigned score `1.0` in both $A \to B$ and $B \to B$.
- This caused paired differences to equal $-1.0$ for Generator A and $+1.0$ for Generator B.

This pattern is a deterministic calibration characteristic of the mock fixtures, not empirical evidence of LLM self-verification behavior. The core scientific question regarding live LLMs remains open.

---

## Related Documentation

- [`docs/final_results_lock.md`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/docs/final_results_lock.md): Full audit lock of the frozen 40-question mock run.
