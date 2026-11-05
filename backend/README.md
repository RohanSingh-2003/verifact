# VeriFact Backend Service

> **FastAPI Asynchronous Engine for Dual-Branch Hallucination Detection, Multi-Model Verification, and Empirical Benchmarking**

The VeriFact backend is a high-performance Python service built on **FastAPI**, **SQLAlchemy 2.0**, and **Pydantic v2**. It coordinates candidate answer generation, cross-model MetaQA metamorphic testing, independent Web Evidence fact-checking, multi-model consensus synthesis, and offline dataset evaluation.

---

## Table of Contents

- [Core Capabilities & Architecture](#core-capabilities--architecture)
- [Directory Organization](#directory-organization)
- [Dual Verification Pipelines](#dual-verification-pipelines)
  - [1. Engine A: MetaQA Metamorphic Testing Pipeline](#1-engine-a-metaqa-metamorphic-testing-pipeline)
  - [2. Engine B: Web Evidence Grounding Pipeline](#2-engine-b-web-evidence-grounding-pipeline)
  - [3. Direct-Answer Multi-Model Peer Review](#3-direct-answer-multi-model-peer-review)
- [API Endpoints Reference](#api-endpoints-reference)
  - [Detection & Generation (`/api/detect`)](#detection--generation-apidetect)
  - [Run Lifecycle & State (`/api/runs`)](#run-lifecycle--state-apiruns)
  - [Offline Evaluation & Benchmarks (`/api/evaluations`)](#offline-evaluation--benchmarks-apievaluations)
  - [Health & Diagnostics (`/api/health`)](#health--diagnostics-apihealth)
  - [Settings & Configuration (`/api/settings`)](#settings--configuration-apisettings)
- [Database Architecture & Persistence](#database-architecture--persistence)
  - [SQLite Engine with WAL Mode](#sqlite-engine-with-wal-mode)
  - [ORM Models & JSON Blob Strategy](#orm-models--json-blob-strategy)
- [LLM Provider Integration & Model Registry](#llm-provider-integration--model-registry)
  - [Fixed Generator & Mutator (Gemma 4:26B)](#fixed-generator--mutator-gemma-426b)
  - [Independent Verifier Pool](#independent-verifier-pool)
  - [Deterministic Mock Adapter](#deterministic-mock-adapter)
- [Configuration & Environment Variables](#configuration--environment-variables)
- [Installation & Setup](#installation--setup)
- [Running the Backend Service](#running-the-backend-service)
- [Running Automated Tests](#running-automated-tests)
- [Troubleshooting & Common Errors](#troubleshooting--common-errors)

---

## Core Capabilities & Architecture

- **Decoupled Asynchronous Lifecycle**: The backend synchronously generates the candidate answer using Gemma 4:26B on Ollama Cloud, persists the run to SQLite with status `RUNNING`, and immediately delivers the answer text to the client. Verification pipelines run concurrently in the background via FastAPI `BackgroundTasks`.
- **Parallel Independent Branches**: Background tasks execute two non-blocking engines in parallel:
  1. **MetaQA Metamorphic Testing**: Mutation generation + multi-model prompt-blind verification.
  2. **Web Evidence Grounding**: Claim extraction + domain classification + 2-pass Tavily search + NLI entailment.
- **100% Cloud-Based Model Inference**: No local LLM weights, daemons, or GPU hardware are required. All inference routes over HTTPS to official provider APIs (Ollama Cloud, Hyperbolic, SiliconFlow, Groq, DeepInfra).
- **Deterministic Mock Mode**: Setting `LLM_MODE=mock` substitutes all external HTTP requests with fast, deterministic fixtures, allowing the full 607-test test suite to execute in seconds without network access or live API credits.

---

## Directory Organization

```text
backend/
├── app/
│   ├── api/                            # REST API route controllers
│   │   ├── routes_detect.py            # POST /api/detect/stream
│   │   ├── routes_runs.py              # GET/DELETE /api/runs, GET /api/runs/{id}
│   │   ├── routes_evaluations.py       # POST /api/evaluations/run, CSV export
│   │   ├── routes_health.py            # GET /api/health
│   │   ├── routes_settings.py          # GET /api/settings
│   │   ├── routes_annotations.py       # Annotation CRUD routes
│   │   └── routes_review.py            # Evaluation item review routes
│   ├── database/                       # Relational persistence layer
│   │   ├── db.py                       # SQLAlchemy engine & SessionLocal factory
│   │   ├── models.py                   # Run, Mutation, Claim, Evidence, Evaluation models
│   │   ├── backup.py                   # Automated database snapshot utility
│   │   └── restore.py                  # Database restore utility
│   ├── evaluation/                     # Offline benchmarking engine
│   │   ├── evaluator.py                # Batch evaluation runner
│   │   ├── dataset_loader.py           # JSON/CSV dataset loader
│   │   ├── ground_truth.py             # Reference answer comparison & aliasing
│   │   └── metrics.py                  # P/R/F1, confusion matrix, threshold sweeps
│   ├── llm/                            # Cloud LLM client adapters
│   │   ├── base.py                     # BaseLLMClient abstract interface
│   │   ├── registry.py                 # Multi-model registry & verifier pool
│   │   ├── providers.py                # OllamaCloudClient, OpenAIAdapter, GroqClient, etc.
│   │   ├── cloudflare.py               # Cloudflare Workers AI client
│   │   ├── gemini.py                   # Legacy Gemini client adapter
│   │   ├── prompts.py                  # Structured system & user prompt templates
│   │   └── mock.py                     # Deterministic mock fixtures for testing
│   ├── metaqa/                         # Engine A: MetaQA Metamorphic Testing
│   │   ├── detector.py                 # MetaQA pipeline coordinator
│   │   ├── mutation.py                 # 3 Synonym + 3 Antonym mutation generator
│   │   ├── verifier.py                 # Single-model mutation verification runner
│   │   ├── multi_verifier.py           # Multi-model prompt-blind verification pool
│   │   └── scoring.py                  # Equation 5 arithmetic mean penalty scoring
│   ├── web_evidence/                   # Engine B: Web Evidence Grounding
│   │   ├── pipeline.py                 # Web evidence coordinator
│   │   ├── claims.py                   # Atomic claim extraction & pronoun resolution
│   │   ├── classifier.py               # 8-category question domain classifier
│   │   ├── strategies.py               # 2-pass search router (whitelist vs. open)
│   │   ├── authority.py                # Domain authority tiers & whitelist definitions
│   │   ├── source_quality.py           # Source credibility tiering logic
│   │   ├── relevance.py                # Jaccard/overlap topical filter (>= 0.20)
│   │   ├── verifier.py                 # NLI claim entailment evaluation
│   │   ├── scoring.py                  # Web Consistency Score calculation
│   │   └── types.py                    # Data classes & verdict enums
│   ├── web_search/                     # External search client
│   │   ├── tavily_client.py            # Tavily Search API client adapter
│   │   └── rate_limiter.py             # Sliding-window rate limiter
│   ├── services/                       # Application service layer
│   │   ├── run_service.py              # Run lifecycle & background task coordinator
│   │   ├── independent_verifiers.py    # Direct-answer peer review service
│   │   ├── verification_summary.py     # Combined risk calculation & verdict fusion
│   │   └── evaluation_service.py       # Batch evaluation service
│   ├── schemas/                        # Pydantic request & response schemas
│   ├── middleware/                     # Error-handling & logging middleware
│   ├── config.py                       # Pydantic BaseSettings loading .env
│   └── main.py                         # FastAPI application factory & CORS configuration
├── data/
│   └── datasets/                       # Benchmark datasets (hallucination_benchmark_frozen.json)
├── scripts/                            # Maintenance and dataset preparation scripts
├── tests/                              # Automated Pytest suite (607 tests)
├── pyproject.toml                      # Backend dependencies and tool configurations
├── requirements.txt                    # Pinned Python package dependencies
└── README.md                           # Backend developer guide (this file)
```

---

## Dual Verification Pipelines

### 1. Engine A: MetaQA Metamorphic Testing Pipeline
Implemented in `app/metaqa/`:
1. **Mutation Generation (`mutation.py`)**:
   - The answer-generating model (Gemma 4:26B) parses its own answer into claims and outputs **3 synonym mutations** (paraphrased, meaning-preserving) and **3 antonym mutations** (negated or entity-inverted, meaning-reversing).
   - Sentence lengths are bounded strictly between 5 and 35 words.
2. **Generator Exclusion**:
   - Gemma is strictly excluded from verifying mutations.
3. **Prompt-Blind Verification (`multi_verifier.py`)**:
   - Mutations are passed blindly to the non-Gemma verifier pool (Microsoft Phi-4, GLM-4.7-Flash, Qwen-2.5-32B, Liquid LFM-2.5).
   - Verifiers receive only the mutated statement without the original question, context, or expected outcome.
   - Verifiers respond with `YES`, `NO`, or `NOT SURE`.
4. **Equation 5 Penalty Scoring (`scoring.py`)**:
   - Synonym: `YES` = 0.0 penalty, `NO` = 1.0 penalty, `NOT SURE` = 0.5 penalty.
   - Antonym: `NO` = 0.0 penalty, `YES` = 1.0 penalty, `NOT SURE` = 0.5 penalty.
   - $H = \frac{1}{N} \sum_{i=1}^N \text{Penalty}(m_i) \in [0.0, 1.0]$.
   - If $H < 0.50 \implies \text{Reliable}$; if $H \ge 0.50 \implies \text{Hallucinated}$.

---

### 2. Engine B: Web Evidence Grounding Pipeline
Implemented in `app/web_evidence/`:
1. **Claim Extraction (`claims.py`)**:
   - Extracts up to `WEB_MAX_CLAIMS` (default 3) discrete, testable assertions.
2. **Domain Classification (`classifier.py`)**:
   - Categorizes queries into 8 domains: Medical, Legal, Financial, Scientific, Historical, Technology, Entertainment, and General.
3. **2-Pass Search Strategy (`strategies.py`)**:
   - **Pass 1**: Restricts Tavily search queries to domain-specific authoritative whitelists (`.gov`, `.edu`, PubMed, Nature, Reuters).
   - **Pass 2 (Fallback)**: If Pass 1 yields 0 results, issues an open web search.
4. **Topical Relevance Filtering (`relevance.py`)**:
   - Tokenizes claim and snippet into alphanumeric token sets, filters English stopwords, and calculates overlap ratio:
     $$\text{Relevance} = \frac{|T(C) \cap T(S)|}{|T(C)|}$$
   - Discards snippets with $\text{Relevance} < 0.20$.
5. **Compound-Claim Check**:
   - Decomposes multi-clause claims into constituent parts; if evidence fails to confirm all parts, the verdict is downgraded to `INSUFFICIENT_EVIDENCE`.
6. **NLI Verification (`verifier.py`)**:
   - Phi-4 evaluates whether retrieved evidence entails or contradicts the claim.
   - Verdicts: `SUPPORTED` (weight 1.0), `INSUFFICIENT_EVIDENCE` (weight 0.5), `CONTRADICTED` (weight 0.0), `NOT_ASSESSED_NO_RELEVANT_SOURCE` (excluded).
7. **Web Consistency Score (`scoring.py`)**:
   - Computed as the arithmetic mean of assessed claim weights ($W \in [0.0, 1.0]$).

---

### 3. Direct-Answer Multi-Model Peer Review
Implemented in `app/services/independent_verifiers.py`:
- Concurrently with MetaQA and Web Evidence, peer verifiers directly review Gemma's full answer text.
- Context provided: question, answer, extracted claims, and web snippets.
- Each model outputs: verdict (`Correct`, `Incorrect`, `Uncertain`), confidence, qualitative reasoning, and disputed claims.
- Quorum consensus is synthesized: `Consensus: Correct`, `Consensus: Incorrect`, `Disagreement Detected`, or `Uncertain Consensus`.
- This qualitative review does **not** alter the quantitative MetaQA or Web Consistency scores.

---

## API Endpoints Reference

### Detection & Generation (`/api/detect`)
- **`POST /api/detect/stream`**:
  - **Body**: `{"question": str, "model": "gemma4:26b"}`
  - **Action**: Enforces Gemma 4:26B, generates base answer, inserts `Run` into SQLite with status `RUNNING`, enqueues background verification tasks, and returns the initial run object.

### Run Lifecycle & State (`/api/runs`)
- **`GET /api/runs/{id}`**:
  - **Action**: Returns full run entity including status, answer, mutations, claims, evidence, scores, and peer reviews. Polled by the frontend.
- **`GET /api/runs`**:
  - **Query Params**: `skip` (default 0), `limit` (default 20), `status` (optional filter).
  - **Action**: Returns paginated list of previous runs for the History view.
- **`DELETE /api/runs/{id}`**:
  - **Action**: Deletes a run and all associated mutations, claims, and evidence records.

### Offline Evaluation & Benchmarks (`/api/evaluations`)
- **`POST /api/evaluations/run`**:
  - **Body**: `{"dataset": "hallucination_benchmark_frozen", "limit": 50, "threshold": 0.5}`
  - **Action**: Executes batch evaluation over benchmark questions.
- **`GET /api/evaluations/{id}`**:
  - **Action**: Returns evaluation metrics (Accuracy, Precision, Recall, F1, Confusion Matrix).
- **`GET /api/evaluations/{id}/export`**:
  - **Action**: Generates and downloads a CSV export of evaluated question rows and scores.

### Health & Diagnostics (`/api/health`)
- **`GET /api/health`**:
  - **Action**: Returns backend service health, database status, and individual cloud LLM provider readiness.

### Settings & Configuration (`/api/settings`)
- **`GET /api/settings`**:
  - **Action**: Returns active model configurations and masked provider credentials.

---

## Database Architecture & Persistence

### SQLite Engine with WAL Mode
The database connection is established in `app/database/db.py`:
- Database file: `backend/data/verifact.db`.
- Configured with `PRAGMA journal_mode=WAL;` to enable concurrent reads during background task writes.

### ORM Models & JSON Blob Strategy
Implemented in `app/database/models.py`:
- **`Run`**: Primary audit entity (`id`, `question`, `answer`, `status`, `metaqa_score`, `web_score`, `combined_risk`, `created_at`, `completed_at`).
  - Serializes multi-model peer reviews as JSON in `ai_verdicts_json`.
- **`Mutation`**: Child table referencing `Run.id` (`mutation_type`, `original_statement`, `mutated_statement`, `penalty`).
  - Serializes individual verifier model votes as JSON in `verdicts_json`.
- **`Claim`**: Extracted atomic claims referencing `Run.id` (`claim_text`, `verdict`, `confidence`).
- **`Evidence`**: Retrieved web search snippets referencing `Claim.id` (`snippet`, `url`, `title`, `relevance_score`, `source_tier`).
- **`EvaluationRun`, `EvaluationResult`, `EvaluationMetric`**: Tables storing offline benchmark evaluation runs and metrics.

---

## LLM Provider Integration & Model Registry

Implemented in `app/llm/registry.py` and `app/llm/providers.py`:

### Fixed Generator & Mutator (Gemma 4:26B)
- **Model**: `gemma4:26b`
- **Client**: `OllamaCloudClient` (`https://ollama.com/api`)
- **Parameters**: `think: false`, `temperature: 0.2`, `max_tokens: 350`
- **Role**: Designated permanent answer generator and mutation synthesiser.

### Independent Verifier Pool
- **Microsoft Phi-4 Reasoning**: Primary reasoning verifier (`microsoft/phi-4-reasoning` via Hyperbolic or OpenRouter).
- **GLM-4.7-Flash**: High-speed verifier (`glm-4.7-flash` via Cloudflare Workers AI or SiliconFlow).
- **Qwen-2.5-32B**: High-throughput reasoning verifier (`qwen-2.5-32b` via Groq Cloud).
- **Liquid LFM-2.5**: Non-transformer architecture verifier (`liquid/lfm-2.5-1.2b` via DeepInfra).
- **Gemini 3.8 Flash**: Disabled / legacy adapter (`routes_health.py` reports `ready: false`; aliased to Phi).

### Deterministic Mock Adapter
- When `LLM_MODE=mock`, `MockLLMClient` intercepts all calls and returns deterministic answers, mutations, and verdicts based on seeded hash keys.

---

## Configuration & Environment Variables

Create `backend/.env` based on `backend/.env.example`:

```env
# Application
ENVIRONMENT=development
FRONTEND_ORIGIN=http://localhost:5173
DATABASE_URL=sqlite:///./data/verifact.db
LLM_MODE=live

# Gemma 4:26B Generator (Ollama Cloud)
OLLAMA_CLOUD_BASE_URL=https://ollama.com/api
OLLAMA_API_KEY=your_ollama_cloud_api_key
OLLAMA_CLOUD_MODEL=gemma4:26b

# Verifier 1: Microsoft Phi-4 Reasoning
OPENROUTER_API_KEY=your_openrouter_api_key
PHI_MODEL=microsoft/phi-4-reasoning:free

# Verifier 2: GLM-4.7-Flash (Cloudflare)
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id
CLOUDFLARE_MODEL=@cf/zai-org/glm-4.7-flash

# Verifier 3: Qwen-2.5-32B (Groq)
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=qwen-2.5-32b

# Verifier 4: Liquid LFM-2.5
OPENROUTER_MODEL=liquid/lfm-2.5-2.6b:free

# Web Evidence (Tavily Search API)
TAVILY_API_KEY=your_tavily_api_key
WEB_EVIDENCE_ENABLED=true
WEB_MAX_CLAIMS=3

# MetaQA Parameters
SYNONYM_COUNT=3
ANTONYM_COUNT=3
THRESHOLD=0.5
LLM_TIMEOUT_SECONDS=60
```

---

## Installation & Setup

1. **Create Virtual Environment**:
   ```bash
   cd backend
   python -m venv .venv
   ```

2. **Activate Virtual Environment**:
   - **Windows (PowerShell)**:
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS**:
     ```bash
     source .venv/bin/activate
     ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Configuration**:
   ```bash
   copy .env.example .env
   # Linux/macOS: cp .env.example .env
   ```

---

## Running the Backend Service

Start the development server with Uvicorn:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc API Reference**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Service Health Check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## Running Automated Tests

VeriFact includes 607 unit and integration tests. Tests run offline against deterministic mock clients:

```bash
# Run the complete test suite
pytest

# Run tests with verbose output
pytest -v

# Run tests in a specific module
pytest tests/test_metaqa_scoring.py
pytest tests/test_web_evidence_relevance.py
```

---

## Troubleshooting & Common Errors

| Issue / Error | Probable Cause | Resolution |
| :--- | :--- | :--- |
| **`503 Service Unavailable: Live LLM mode is not configured`** | `LLM_MODE=live` is set but `OLLAMA_API_KEY` is missing. | Provide your Ollama Cloud API key in `backend/.env` or set `LLM_MODE=mock`. |
| **`504 Gateway Timeout`** | Upstream cloud provider exceeded `LLM_TIMEOUT_SECONDS`. | Increase `LLM_TIMEOUT_SECONDS=90` in `backend/.env`. |
| **Web Evidence displays `UNAVAILABLE`** | `TAVILY_API_KEY` is missing or invalid. | Obtain a free key from [tavily.com](https://tavily.com) and add it to `backend/.env`. |
| **`OperationalError: database is locked`** | SQLite file is locked by a long write transaction. | Ensure WAL mode is active (`PRAGMA journal_mode=WAL;`). |
| **CORS blocked by browser** | `FRONTEND_ORIGIN` does not match the frontend dev server URL. | Ensure `FRONTEND_ORIGIN=http://localhost:5173` in `.env`. |
