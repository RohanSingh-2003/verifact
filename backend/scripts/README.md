# VeriFact Backend Scripts & Maintenance Utilities

> **Operational Scripts for Database Management, Dataset Preparation, Cryptographic Freezing, and Smoke Testing**

This directory contains standalone CLI scripts and maintenance utilities supporting the VeriFact backend. These scripts are executed directly using Python from the `backend/` directory.

---

## Table of Contents

- [Script Inventory & Overview](#script-inventory--overview)
- [Database Management Scripts](#database-management-scripts)
  - [`backup_db.py`](#backup_dbpy)
  - [`restore_db.py`](#restore_dbpy)
- [Benchmark & Dataset Scripts](#benchmark--dataset-scripts)
  - [`prepare_benchmark_datasets.py`](#prepare_benchmark_datasetspy)
  - [`freeze_benchmark_dataset.py`](#freeze_benchmark_datasetpy)
- [Diagnostic & Smoke Testing Scripts](#diagnostic--smoke-testing-scripts)
  - [`check_api.py`](#check_apipy)
  - [`live_smoke.py`](#live_smokepy)
  - [`smoke_model_routing.py`](#smoke_model_routingpy)
- [Execution Guidelines & Environment](#execution-guidelines--environment)

---

## Script Inventory & Overview

| Script Name | Category | Primary Purpose | Required Arguments / Inputs |
| :--- | :--- | :--- | :--- |
| **`backup_db.py`** | Database | Creates a timestamped backup copy of `verifact.db` with a SHA-256 integrity checksum. | Optional `--output-dir` |
| **`restore_db.py`** | Database | Restores `verifact.db` from a specified backup snapshot with integrity validation. | Backup file path |
| **`prepare_benchmark_datasets.py`** | Datasets | Samples canonical TruthfulQA and FreshQA into the standardized 550-question benchmark using `sha256_stratified_v1`. | Raw CSV datasets |
| **`freeze_benchmark_dataset.py`** | Datasets | Cryptographically freezes benchmark files by calculating SHA-256 hashes and generating companion manifests. | Input JSON dataset |
| **`check_api.py`** | Diagnostics | Quick HTTP probe testing local FastAPI endpoint responsiveness. | None (targets `127.0.0.1:8000`) |
| **`live_smoke.py`** | Diagnostics | Live end-to-end smoke test validating configured cloud API keys and inference endpoints. | Valid `.env` with live keys |
| **`smoke_model_routing.py`** | Diagnostics | Validates model registry mapping and verifier pool resolution. | None |

---

## Database Management Scripts

### `backup_db.py`
Creates an atomic, timestamped snapshot of the active SQLite database (`data/verifact.db`):
- Uses SQLite's online backup API to ensure safety while FastAPI is running.
- Calculates and writes a companion `.sha256` checksum file.

```bash
# Run from backend/
python -m scripts.backup_db
```

### `restore_db.py`
Restores the database from a backup snapshot:
- Validates the backup file's SHA-256 checksum before restoration.
- Creates a pre-restore backup of the current database to prevent accidental data loss.

```bash
# Run from backend/
python -m scripts.restore_db --backup-file data/backups/verifact_20261105_120000.db
```

---

## Benchmark & Dataset Scripts

### `prepare_benchmark_datasets.py`
Builds the formal 550-question research benchmark from raw upstream sources:
- Samples 400 questions from TruthfulQA using proportional category balance.
- Samples 150 questions from FreshQA partitioned across temporal tiers (`never-changing`, `slow-changing`, `fast-changing`, `false-premise`).
- Implements the versioned **`sha256_stratified_v1`** deterministic algorithm:
  $$\text{Seed} = \text{base\_seed} + (\text{SHA-256}(\text{base\_seed} \parallel \text{key})[:8] \pmod{2^{31} - 1})$$
- Generates exact 80% Dev (440 items) / 20% Test (110 items) splits.

```bash
# Run from backend/
python -m scripts.prepare_benchmark_datasets
```

### `freeze_benchmark_dataset.py`
Locks a dataset for formal research publication:
- Computes canonical SHA-256 digest of the dataset file.
- Generates the immutable frozen file (e.g. `hallucination_benchmark_frozen.json`).
- Generates the companion `.manifest.json` containing cryptographic provenance.

```bash
# Run from backend/
python -m scripts.freeze_benchmark_dataset \
  --input data/datasets/hallucination_benchmark.json \
  --output data/datasets/hallucination_benchmark_frozen.json
```

---

## Diagnostic & Smoke Testing Scripts

### `check_api.py`
Performs a fast HTTP connectivity check to ensure the local FastAPI server is healthy:

```bash
# Run from backend/
python -m scripts.check_api
```

### `live_smoke.py`
Executes live, real-world queries against configured cloud providers to verify that API keys, quotas, and endpoints are active:
- Tests Gemma 4:26B on Ollama Cloud.
- Tests Microsoft Phi-4, GLM-4.7, Qwen-2.5, and Liquid LFM on their respective cloud APIs.
- Tests Tavily Search API retrieval.

> [!CAUTION]
> This script consumes live cloud API credits. Ensure `LLM_MODE=live` and your `.env` contains valid credentials before running.

```bash
# Run from backend/
python -m scripts.live_smoke
```

### `smoke_model_routing.py`
Validates that `MODEL_REGISTRY` resolves all model identifiers correctly and ensures that Gemma 4:26B is strictly excluded from the verifier pool:

```bash
# Run from backend/
python -m scripts.smoke_model_routing
```

---

## Execution Guidelines & Environment

Always execute scripts as modules (`python -m scripts.<script_name>`) from the `backend/` directory to ensure Python resolves the parent `app/` package correctly:

```bash
cd backend
.\.venv\Scripts\Activate.ps1
python -m scripts.<script_name> [args]
```

