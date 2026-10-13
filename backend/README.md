# VeriFact Backend Service

FastAPI service powering VeriFact's explainable hallucination detection system. It coordinates candidate answer generation, cross-model MetaQA metamorphic testing, independent Web Evidence fact-checking, and offline dataset evaluation.

---

## Table of Contents

- [Core Capabilities & Architecture](#core-capabilities--architecture)
- [Main Features Implementation](#main-features-implementation)
  - [1. Answer Generation](#1-answer-generation)
  - [2. MetaQA-Based Hallucination Detection](#2-metaqa-based-hallucination-detection)
  - [3. Direct-Answer Multi-Model Verification](#3-direct-answer-multi-model-verification)
  - [4. Web Evidence Grounding](#4-web-evidence-grounding)
  - [5. Performance Evaluation & Benchmark Module](#5-performance-evaluation--benchmark-module)
- [Overall Assessment & Combined Risk](#overall-assessment--combined-risk)
- [Setup & Installation](#setup--installation)
  - [Prerequisites](#prerequisites)
  - [Virtual Environment & Dependencies](#virtual-environment--dependencies)
  - [Environment Variables Configuration](#environment-variables-configuration)
- [Running the Backend](#running-the-backend)
- [Running Automated Tests](#running-automated-tests)
- [API Endpoints Reference](#api-endpoints-reference)
- [Architecture & Directory Organization](#architecture--directory-organization)
- [Troubleshooting & Common Errors](#troubleshooting--common-errors)

---

## Core Capabilities & Architecture

- **Progressive Detection Pipeline**: Synchronously generates the candidate answer, writes the record to SQLite with status `answer_ready`, returns the answer to the client immediately, and launches verification as concurrent background tasks via `asyncio.gather(..., return_exceptions=True)` across three distinct branches:
  1. **MetaQA Metamorphic Testing** (Gemma mutant generation + internal multi-model mutation verification pool)
  2. **Direct-Answer Multi-Model Review** (independent peer-model direct evaluation of Gemma's full answer)
  3. **Web Evidence Grounding** (external Tavily search retrieval + claim-level fact-checking)
  None of the background verification branches block each other.
- **100% Cloud-Based Model Inference**: All inference runs through official cloud provider APIs (Ollama Cloud, Cloudflare Workers AI, Groq, OpenRouter, Google Gemini). **No local Ollama daemon or local GPU inference is used.**
- **Deterministic Offline Mock Mode**: Setting `LLM_MODE=mock` replaces all external LLM and search calls with deterministic fixtures, enabling the automated test suite (458 test items collected at time of audit) to run in seconds without network access or live API credits.

---

## Main Features Implementation

### 1. Answer Generation

- **Fixed Answer Generator**:
  - **Model**: **Gemma 4:26B** (`gemma4:26b`).
  - **Provider**: Official **Ollama Cloud API** (`https://ollama.com/api`) accessed via dedicated HTTP client `OllamaCloudClient` (`app/llm/providers.py`).
  - **Design Decision**: Gemma 4:26B is permanently designated as the sole answer-generating model across VeriFact. The frontend model-selection dropdown has been removed, and API requests default to Gemma.
  - **Reasoning Suppression (`think: false`)**: Gemma reasoning models are configured with `think: false` to eliminate hidden reasoning chain overhead and deliver clean, deterministic answers within `LLM_ANSWER_MAX_TOKENS=350`.
- **Verifier Pool Models**:
  - The model registry in [`app/llm/registry.py`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/llm/registry.py) defines the remaining cloud-hosted models as independent verifiers:
    1. `gemini`: Gemini Flash 3.8 via Google Gemini API (`GEMINI_API_KEY`)
    2. `glm`: GLM-4.7-Flash via Cloudflare Workers AI (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`)
    3. `qwen`: Qwen-2.5-32B via Alibaba / Groq (`GROQ_API_KEY`)
    4. `openrouter`: Liquid LFM-2.5 via OpenRouter (`OPENROUTER_API_KEY`)
- **Immediate Return Flow**:
  - Answer generation records latency (`answer_ms`) and persists the initial run with status `answer_ready`.
  - The answer text is returned immediately to the frontend, allowing users to inspect the response while verification proceeds in the background.

---

### 2. MetaQA-Based Hallucination Detection

Implemented in [`backend/app/metaqa/`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/metaqa/).

- **Generator–Verifier Exclusion Guarantee**:
  - The model that generated the candidate answer (Gemma) is **strictly excluded** from its own verifier pool:
    $$\text{Verifier Pool} = \text{AllConfiguredModels} \setminus \{\text{Gemma 4:26B}\}$$
  - Other configured models (`gemini`, `glm`, `qwen`, `openrouter`) act as independent cross-model verifiers.
- **Metamorphic Mutations**:
  - Rather than rewriting the entire answer, atomic factual claims are parsed from the answer.
  - Generates paired mutations in a single, token-capped request (`LLM_MUTATION_MAX_TOKENS=300`):
    - **Synonym Mutations (Meaning-Preserving)**: Paraphrased assertions retaining identical truth conditions using alternate phrasing. Expected verdict: **`YES`**.
    - **Antonym Mutations (Meaning-Reversing)**: Negated or entity-inverted assertions contradicting the original answer. Expected verdict: **`NO`**.
  - Default: 3 synonyms and 3 antonyms per Detect run (`SYNONYM_COUNT=3`, `ANTONYM_COUNT=3`).
- **Internal Multi-Model Verifier Pool (`multi_verifier.py`)**:
  - Mutation verification is handled by [`app/metaqa/multi_verifier.py::verify_all_mutations_multi_model`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/metaqa/multi_verifier.py).
  - Each mutation statement is verified across the configured verifiers concurrently without leaking mutation type or expected verdict.
- **Verifier Context Isolation**:
  - Verifier models receive strictly: the question, candidate answer, and the single mutated statement.
  - Verifiers are **never told** whether the mutation is a synonym or antonym, nor the expected verdict or ground truth.
- **Observed Verdicts & Error Handling**:
  - **`YES`**: Supported / consistent with the candidate answer.
  - **`NO`**: Contradicts / unsupported by the candidate answer.
  - **`NOT SURE`**: Relationship is ambiguous or indeterminate from the text.
  - **Technical Errors**: JSON parse failures or HTTP timeouts are marked `parse_failed=True` and isolated as technical errors—they are **never** counted as legitimate `NOT SURE` judgments. If no verifier is configured, MetaQA reports `UNAVAILABLE`.
- **Deterministic Python Scoring Table**:
  Scoring is computed directly in Python code ([`app/metaqa/scoring.py`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/metaqa/scoring.py)):

  | Mutation Type | Observed: `YES` | Observed: `NO` | Observed: `NOT SURE` |
  | :--- | :---: | :---: | :---: |
  | **Synonym** (Expected `YES`) | **0.0** (Consistent) | **1.0** (Violation) | **0.5** (Uncertain) |
  | **Antonym** (Expected `NO`) | **1.0** (Violation) | **0.0** (Consistent) | **0.5** (Uncertain) |

  $$\text{MetaQA Score } H = \frac{1}{N} \sum_{i=1}^N c_i \quad \text{clamped to } [0.0, 1.0]$$

  - Classification threshold $\theta = 0.5$:
    - $H < \theta \implies \textbf{Reliable}$
    - $H \ge \theta \implies \textbf{Hallucinated}$
- **Limitations**:
  - MetaQA measures internal semantic stability, not real-world factual ground truth. If an LLM consistently reinforces a popular misconception under synonym and antonym perturbations, MetaQA records it as consistent.

---

### 3. Direct-Answer Multi-Model Verification

Implemented in [`backend/app/services/independent_verifiers.py`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/services/independent_verifiers.py).

- **Direct Answer Evaluation**:
  - Concurrently with MetaQA and Web Evidence, all non-Gemma configured models evaluate Gemma's original complete answer.
  - Verifiers receive enriched contextual input: the original user question, Gemma's generated answer, extracted atomic claims, generated mutations, and retrieved web evidence snippets.
- **Structured Peer Verdicts**:
  - Each independent verifier returns a structured assessment:
    - **`verdict`**: `Correct`, `Incorrect`, or `Uncertain`
    - **`confidence`**: Numerical confidence rating ($0.0 \dots 1.0$)
    - **`reasoning`**: Detailed explanation justifying the verdict
    - **`contradictory_claims`**: Specific claims in Gemma's answer identified as factually inaccurate or disputed
- **Consensus & Disagreement Synthesis**:
  - Produces an executive consensus summary (`multi_model_summary`):
    - **Consensus Badge**: `Consensus: Correct`, `Disagreement Detected`, `Consensus: Incorrect`, `Uncertain Consensus`, or `No Reviews Available`.
    - **Agreement Count**: Formatted as `X/Y agreed` across all responding peer models.
    - **Contradictory Claims Registry**: Highlights peer-identified errors in the UI.
- **Strict Metric Separation**:
  - Direct-Answer review provides transparent peer consensus and qualitative warnings; it **never modifies or overwrites** the mathematical MetaQA Score or Web Consistency Score.

---

### 4. Web Evidence Grounding

Implemented in [`backend/app/web_evidence/`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/web_evidence/) and [`backend/app/web_search/`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/web_search/).

- **Claim Extraction**: Extracts independent testable claims from the candidate answer while stripping greetings, styling, and opinions (`WEB_MAX_CLAIMS=3`).
- **Domain Classification & Targeted Routing**:
  - A rule-based classifier categorizes the question (e.g., General Facts, Science, Government, Current Events, Statistics, Medicine, Academic Research).
  - Guides search queries toward authoritative domains (e.g., `.gov`, `.edu`, Britannica, WHO, NASA). If preferred domains yield empty results, search automatically broadens.
- **Tavily Search API**:
  - Dispatches targeted search queries per claim using Tavily Basic Search.
  - Budgeted by `WEB_MAX_SEARCHES=3` and `WEB_RESULTS_PER_CLAIM=2`.
- **Claim-Relevant Evidence Extraction**:
  - Automatically cleans navigation bars, boilerplate markdown, and citation brackets (`[1]`).
  - Extracts the 1–2 sentences directly relevant to the claim (`evidenceSummary`) and returns source domain, title, URL, and verifier rationale.
- **Claim Verdicts & Consistency Score**:
  - Verdicts: **`SUPPORTED`**, **`CONTRADICTED`**, or **`INSUFFICIENT_EVIDENCE`**.
  - **Invariance**: Insufficient evidence is **never** treated as a hallucination.
  - **Web Consistency Score**: Average claim contribution (`SUPPORTED` = 1.0, `INSUFFICIENT_EVIDENCE` = 0.5, `CONTRADICTED` = 0.0).
  - **Strict Metric Separation**: Web Evidence is an external retrieval audit; its score is kept strictly independent and is never merged into the MetaQA score.

---

### 5. Performance Evaluation & Benchmark Module

Implemented in [`backend/app/evaluation/`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/evaluation/).

- **Datasets**:
  - Curated evaluation datasets in [`backend/data/datasets/`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/data/datasets/).
  - Bundled dataset: `pilot.json` (40 hand-selected questions across 5 categories: `named_entity`, `location`, `date`, `numeric`, `general_fact`, 8 each) with `pilot.manifest.json`.
- **Ground Truth & Review Handling**:
  - Answers are compared against gold-standard reference answers and acceptable aliases.
  - Ambiguous items are flagged `needs_review=True` (e.g., items `q032` and `q039`). They are retained in the database for auditing but excluded from automated Precision, Recall, and F1 calculations (leaving 38 labeled items).
- **Metrics Computed**:
  - Accuracy, Precision, Recall, F1, Specificity, False Positive Rate (FPR), False Negative Rate (FNR).
  - Full confusion matrix: TP, TN, FP, FN.
  - Category-by-category breakdown and threshold sweeps ($\theta \in [0.10, 0.90]$).
- **Persistence & Export**:
  - Stored in SQLite across `EvaluationRun`, `EvaluationResult`, and `EvaluationMetric` tables.
  - Exportable as CSV via `GET /api/evaluations/{id}/export`.
- **Difference from Live Detection**:
  - **Live Detection**: Interactive, end-to-end question answering and verification.
  - **Benchmark Evaluation**: Offline batch auditing of static datasets against gold-standard labels to measure classifier accuracy.
- **Historical Benchmark Status**:
  - Locked run `58baff20-fb86-4f43-b20e-895a086ceb6b` was executed in **`mock` mode (DEMO / MOCK DATA)**.
  - The planned live 2×2 experiment in `experiments/config/final_experiment.yaml` (`gpt-4o-mini` vs. `gpt-4o`) was **frozen as NOT EXECUTED** due to missing live API credentials.

---

## Overall Assessment & Combined Risk

The application-level synthesis layer in [`backend/app/services/verification_summary.py`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/services/verification_summary.py) provides a unified verdict and heuristic risk score:

- **Executive Verdicts**: `Likely Reliable`, `Potentially Hallucinated`, `Needs Verification`, `Insufficient Evidence`, `Unavailable`.
- **Combined Hallucination Risk**:
  $$\text{Web Risk} = 1.0 - \text{Web Consistency Score}$$
  $$\text{Combined Risk} = 0.5 \times \text{MetaQA Score} + 0.5 \times \text{Web Risk}$$
- **Heuristic Notice**: This combined value is an application-level engineering heuristic, not a mathematically calibrated probability of truth.

---

## Setup & Installation

### Prerequisites
- Python 3.11, 3.12, or 3.14 (64-bit)
- `pip` package manager

### Virtual Environment & Dependencies

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment configuration
copy .env.example .env
# (On macOS/Linux: cp .env.example .env)
```

### Environment Variables Configuration

Edit `backend/.env` with your settings:

```env
ENVIRONMENT=development
FRONTEND_ORIGIN=http://localhost:5173
DATABASE_URL=sqlite:///./data/verifact.db

# Execution Mode: "live" (Cloud APIs) or "mock" (offline test fixtures)
LLM_MODE=live

# 1. Ollama Cloud (Gemma 4:26B — Fixed Generator)
OLLAMA_CLOUD_BASE_URL=https://ollama.com/api
OLLAMA_API_KEY=your_ollama_cloud_api_key_here
OLLAMA_CLOUD_MODEL=gemma4:26b

# 2. Google Gemini (Gemini Flash 3.8 — Primary Cross-Model Verifier)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_VERIFIER_MODEL=gemini-3.8-flash
GEMINI_VERIFY_CONCURRENCY=3

# 3. Optional Additional Cloud Providers (Verifier Pool & Peer Review)
CLOUDFLARE_API_TOKEN=your_cloudflare_token_here
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id_here
GROQ_API_KEY=your_groq_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# 4. Web Evidence Verification (Tavily Search API)
TAVILY_API_KEY=your_tavily_api_key_here
TAVILY_BASE_URL=https://api.tavily.com
TAVILY_SEARCH_DEPTH=basic
WEB_EVIDENCE_ENABLED=true
WEB_MAX_CLAIMS=3
WEB_MAX_SEARCHES=3
WEB_RESULTS_PER_CLAIM=2

# 5. MetaQA Parameters
SYNONYM_COUNT=3
ANTONYM_COUNT=3
THRESHOLD=0.5
VERIFY_CONCURRENCY=3
LLM_TIMEOUT_SECONDS=60
LLM_ANSWER_MAX_TOKENS=350
LLM_MUTATION_MAX_TOKENS=300
```

---

## Running the Backend

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- System health check: `GET http://127.0.0.1:8000/api/health`
- Runtime public settings: `GET http://127.0.0.1:8000/api/settings`
- Interactive OpenAPI documentation: `http://127.0.0.1:8000/docs`

---

## Running Automated Tests

The backend includes a comprehensive automated test suite (458 test items collected at the time of the audit) covering all pipelines, scoring functions, mutation edge cases, independent peer verifiers, error handlers, and summary fusion rules:

```bash
# Run the complete test suite
pytest

# Run tests with concise output
pytest -q
```

All tests execute offline using deterministic test fixtures in ~7-8 seconds without requiring external network access or live API credits.

---

## API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/models` | Returns available cloud models and verification provider status (Gemma 4:26B is fixed generator; other models form the verifier pool). |
| `POST` | `/api/detect` | Starts detection: generates answer via Gemma 4:26B, schedules MetaQA, Direct Review, and Web Evidence tasks. |
| `GET` | `/api/runs/{id}` | Returns run state, mutations, peer verdicts, evidence sources, and overall assessment. |
| `GET` | `/api/runs` | Returns paginated list of previous detection runs. |
| `DELETE` | `/api/runs/{id}` | Deletes a specific run from the SQLite database. |
| `GET` | `/api/health` | System health check, active providers, and feature readiness. |
| `GET` | `/api/settings` | Non-sensitive public runtime settings for UI rendering. |
| `POST` | `/api/evaluations/run` | Runs offline benchmark evaluation over curated question datasets. |
| `GET` | `/api/evaluations` | Returns list of completed evaluation runs. |
| `GET` | `/api/evaluations/{id}` | Retrieves full evaluation metrics and confusion breakdown. |
| `GET` | `/api/evaluations/{id}/export` | Downloads evaluation result rows as CSV. |

---

## Architecture & Directory Organization

```text
backend/app/
├── api/                       # Route handlers:
│   ├── deps.py                # Database and client dependency injection
│   ├── routes_detect.py       # Detection lifecycle, fixed Gemma generator & 3 concurrent background branches
│   ├── routes_evaluations.py  # Offline dataset benchmarking
│   ├── routes_health.py       # Health check
│   ├── routes_runs.py         # History & run retrieval
│   └── routes_settings.py     # Public runtime settings
├── database/                  # SQLite persistence:
│   ├── db.py                  # SQLAlchemy engine & session factory
│   └── models.py              # Run, Mutation, Evaluation models
├── evaluation/                # Benchmark evaluation engine:
│   ├── dataset_loader.py      # JSON and CSV dataset loading
│   ├── evaluator.py           # Benchmark runner
│   ├── ground_truth.py        # Reference answer comparison
│   ├── metrics.py             # Accuracy, P/R/F1, confusion matrix
│   └── schemas.py             # Evaluation schemas
├── llm/                       # Multi-model cloud abstraction:
│   ├── base.py                # Abstract LLM client & exceptions
│   ├── providers.py           # OllamaCloudClient, GeminiAdapter, etc.
│   ├── registry.py            # Model registry & dynamic verifier pool
│   └── mock.py                # Deterministic test fixtures
├── metaqa/                    # MetaQA metamorphic testing core:
│   ├── detector.py            # Analysis orchestration & callbacks
│   ├── mutation.py            # Mutation generation & validation
│   ├── multi_verifier.py      # Multi-model concurrent mutation verification pool
│   ├── verifier.py            # Single-model mutation verification runner
│   └── scoring.py             # Deterministic Python scoring matrix
├── web_evidence/              # Web factual grounding:
│   ├── pipeline.py            # Async search & verification coordinator
│   ├── classifier.py          # Question-type classification
│   ├── strategies.py          # Authoritative domain recommendations
│   ├── evidence_extractor.py  # Snippet cleaner & sentence extractor
│   └── scoring.py             # Web Consistency Score calculation
├── web_search/                # Tavily search client & concurrency controls
├── services/                  # Business logic services:
│   ├── run_service.py         # Stage-by-stage DB updates
│   ├── independent_verifiers.py # Direct-Answer multi-model peer review
│   └── verification_summary.py # Overall Assessment fusion & heuristic risk
├── config.py                  # Pydantic BaseSettings (.env loading)
└── main.py                    # Application entry point & CORS middleware
```

---

## Troubleshooting & Common Errors

- **`503 Service Unavailable`** (`"Selected answer model is not configured"`):
  - Ensure API credentials are set in `backend/.env` for the chosen model (e.g., `OLLAMA_API_KEY` for Gemma, `GEMINI_API_KEY` for Gemini).
  - To test without API keys, set `LLM_MODE=mock` in `backend/.env`.
- **`502 Bad Gateway`** (`"The language model request failed"`):
  - The upstream cloud API returned an error or rejected authentication. Check key validity and quota balance in the provider console.
- **`504 Gateway Timeout`** (`"The language model timed out"`):
  - The model took longer than `LLM_TIMEOUT_SECONDS` (default 60s). Increase the timeout in `backend/.env`.
- **`CORS Error` on frontend requests**:
  - Verify that `FRONTEND_ORIGIN` in `backend/.env` matches the frontend URL (`http://localhost:5173`).
- **Database Locked / Write Failures**:
  - Ensure the `backend/data/` directory exists and has write permissions.
