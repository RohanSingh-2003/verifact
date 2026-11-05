# VeriFact Backend Test Suite Guide

> **Comprehensive Architecture, Execution Guide, and Mocking Strategy for Backend Automated Tests**

This directory contains the automated test suite for the VeriFact backend. It comprises **607 unit, regression, integration, and property-based tests** covering API routes, database persistence, metamorphic mutation validation, deterministic scoring formulas, model provider adapters, and web evidence verification.

---

## Table of Contents

- [Test Suite Overview](#test-suite-overview)
- [Running Automated Tests](#running-automated-tests)
  - [Prerequisites](#prerequisites)
  - [Basic Execution](#basic-execution)
  - [Targeted Test Execution](#targeted-test-execution)
  - [Running with Coverage](#running-with-coverage)
- [Mocking Strategy & External Service Isolation](#mocking-strategy--external-service-isolation)
  - [Deterministic Mock Clients](#deterministic-mock-clients)
  - [Zero External Network Calls](#zero-external-network-calls)
  - [Test Fixtures (`conftest.py` & `fakes.py`)](#test-fixtures-conftestpy--fakespy)
- [Test Organization by Functional Domain](#test-organization-by-functional-domain)
  - [1. MetaQA Metamorphic Testing Core](#1-metaqa-metamorphic-testing-core)
  - [2. Web Evidence Grounding & Relevance](#2-web-evidence-grounding--relevance)
  - [3. LLM Providers & Model Routing](#3-llm-providers--model-routing)
  - [4. API Endpoints & Run Lifecycle](#4-api-endpoints--run-lifecycle)
  - [5. Database Persistence & Backup/Restore](#5-database-persistence--backuprestore)
  - [6. Evaluation Engine & Reproducibility](#6-evaluation-engine--reproducibility)
- [Adding New Tests](#adding-new-tests)
- [Troubleshooting Test Failures](#troubleshooting-test-failures)

---

## Test Suite Overview

- **Test Framework**: `pytest` (`^8.1.1`) with `pytest-asyncio`.
- **Total Tests**: **607 unit and integration tests** collected across 40 test files.
- **Execution Speed**: ~10–15 seconds for the complete suite (under `LLM_MODE=mock`).
- **Dependencies**: Uses an in-memory SQLite database (`sqlite:///:memory:`) and deterministic mocked LLM clients by default.

---

## Running Automated Tests

### Prerequisites
Ensure your Python virtual environment is activated and backend dependencies are installed:

```bash
cd backend

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate
```

### Basic Execution
```bash
# Run all 607 tests
pytest

# Run with verbose output showing individual test names
pytest -v

# Run with short summary of passes/failures
pytest -q
```

### Targeted Test Execution
```bash
# Run tests for MetaQA scoring only
pytest tests/test_scoring.py

# Run tests for Web Evidence retrieval and relevance filtering
pytest tests/test_web_evidence.py tests/test_web_evidence_relevance_regression.py

# Run tests for API route controllers
pytest tests/test_detect.py tests/test_evaluations_api.py tests/test_health.py

# Run tests matching a keyword expression
pytest -k "mutation"
pytest -k "relevance"
```

### Running with Coverage
```bash
pytest --cov=app --cov-report=term-missing
```

---

## Mocking Strategy & External Service Isolation

### Deterministic Mock Clients
VeriFact enforces **100% offline test execution** to ensure tests run fast, reliably, and without consuming paid cloud API credits:
- When running tests, `conftest.py` sets `LLM_MODE=mock`.
- Calls to `OllamaCloudClient`, `OpenAIAdapter`, `GroqClient`, or `CloudflareWorkersAIClient` are intercepted by `MockLLMClient` (`backend/app/llm/mock.py`).
- Responses are generated deterministically using hashed seeds based on the input text, ensuring that identical questions always return identical answers, claims, and mutations.

### Zero External Network Calls
- **Tavily Search API**: Intercepted in tests by fake search clients (`tests/fakes.py`) returning predefined HTML/text snippets.
- **Cloud LLM APIs**: All network requests via `httpx` or the `openai` SDK are mocked. Tests pass even in completely air-gapped environments.

### Test Fixtures (`conftest.py` & `fakes.py`)
- **`db_session`**: Creates an isolated in-memory SQLite database session per test, automatically rolled back upon completion.
- **`mock_llm_registry`**: Injects deterministic mock client adapters for `gemma`, `phi`, `glm`, `qwen`, and `openrouter`.
- **`sample_run_payload`**: Preconfigured test dictionary simulating user questions.

---

## Test Organization by Functional Domain

### 1. MetaQA Metamorphic Testing Core
- `test_mutations.py`: Validates parsing of base answers into factual claims; checks generation of 3 synonym and 3 antonym mutations; enforces 5–35 word length bounds.
- `test_detector.py`: Tests the `MetaQADetector` orchestration engine, ensuring generator exclusion and verifier pooling.
- `test_verifier.py` & `test_reviewer_blinding.py`: Verifies prompt blindness (verifiers receive only mutated statements without question or expected verdict context).
- `test_scoring.py`: Tests Equation 5 penalty calculations (Synonym YES=0.0/NO=1.0, Antonym NO=0.0/YES=1.0, NOT SURE=0.5).
- `test_fixed_gemma_multi_model.py`: Asserts that Gemma 4:26B is fixed as the generator and excluded from verifying its own mutations.

### 2. Web Evidence Grounding & Relevance
- `test_web_evidence.py`: End-to-end testing of claim extraction, 2-pass search routing, and NLI claim entailment.
- `test_web_evidence_relevance_regression.py`: Tests topical token overlap filtering against known positive and negative snippet pairs ($\ge 0.20$ threshold).
- `test_web_evidence_scoring.py`: Validates calculation of the Web Consistency Score and categorical verdicts (`SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT`).
- `test_rate_limiter.py`: Tests sliding-window rate limiting on search API requests.

### 3. LLM Providers & Model Routing
- `test_model_routing.py`: Validates dynamic model lookup from `MODEL_REGISTRY`.
- `test_ollama_provider.py`: Tests `OllamaCloudClient` request payload construction, auth headers, and `think: false` suppression.
- `test_cloudflare.py`, `test_openrouter_provider.py`, `test_gemini_provider.py`: Tests provider-specific serialization, timeouts, and error handling.
- `test_multi_model_quorum.py`: Validates synthesis of consensus verdicts (`Consensus: Correct`, `Disagreement Detected`).

### 4. API Endpoints & Run Lifecycle
- `test_detect.py` & `test_ai_detect_flow.py`: Tests `POST /api/detect/stream` request validation, immediate answer delivery, and background dispatch.
- `test_parallel_pipeline.py`: Tests concurrent execution of MetaQA, Web Evidence, and Peer Review via `asyncio.gather`.
- `test_verification_summary.py` & `test_history_combined_risk.py`: Tests calculation of Combined Hallucination Risk ($0.5 \times \text{MetaQA} + 0.5 \times (1.0 - \text{WebScore})$).
- `test_health.py`: Validates `GET /api/health` status reporting.

### 5. Database Persistence & Backup/Restore
- `test_database_backup.py`: Tests automated creation of SQLite database snapshots.
- `test_database_restore.py`: Tests database restoration and schema integrity verification.

### 6. Evaluation Engine & Reproducibility
- `test_dataset_loader.py`: Tests parsing and loading of benchmark JSON and CSV files.
- `test_dataset_standardization.py`: Validates schema conformance of the 550-question formal benchmark.
- `test_cross_process_reproducibility.py`: Verifies deterministic sampling across varying `PYTHONHASHSEED` settings using `sha256_stratified_v1`.
- `test_metrics.py`: Validates Accuracy, Precision, Recall, F1, Specificity, FPR, and FNR calculations.
- `test_ground_truth.py`: Tests ground-truth resolution hierarchy and `needs_review` exclusion.

---

## Adding New Tests

1. Create a new test file named `test_<feature>.py` in this directory (`backend/tests/`).
2. Use `pytest` function naming conventions: `def test_<behavior>():`.
3. Use async def for tests requiring async execution (`@pytest.mark.asyncio`).
4. Example test template:

```python
import pytest
from app.metaqa.scoring import calculate_metaqa_score

def test_custom_scoring_rule():
    # Setup test inputs
    mutations = [
        {"mutation_type": "synonym", "penalty": 0.0},
        {"mutation_type": "antonym", "penalty": 0.0},
    ]
    
    # Execute function under test
    score = calculate_metaqa_score(mutations)
    
    # Assert expected outcomes
    assert score == 0.0
```

---

## Troubleshooting Test Failures

| Symptom | Root Cause | Fix |
| :--- | :--- | :--- |
| **`ModuleNotFoundError: No module named 'app'`** | Python path does not include `backend/`. | Run pytest from the `backend/` directory: `cd backend && pytest`. |
| **`ConnectionRefusedError` or timeout** | A test attempted to call a live cloud API. | Ensure `LLM_MODE=mock` is set or check that external clients are properly mocked. |
| **`OperationalError: no such table: runs`** | Database schema was not initialized in test fixture. | Ensure the test imports and uses the `db_session` fixture from `conftest.py`. |

