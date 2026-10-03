# VeriFact Backend

FastAPI service for MetaQA-based fact-conflicting hallucination detection, independent Web Evidence verification, and application-level overall assessment synthesis.

---

## Key Capabilities

- **Progressive Detection Pipeline**: Returns the generated answer immediately (`answer_ready`), then runs **MetaQA** and **Web Evidence** concurrently as background tasks via `asyncio.gather`. Neither pipeline blocks the other; failure in one branch does not cancel the other, and the candidate answer remains available.
- **Cross-Model MetaQA Verification**:
  - **Answer & Mutation Generation**: Local [Ollama](https://ollama.com) running Google's **Gemma 4:26B** (`gemma4:26b`).
  - **Mutation Verification**: Cloud-based **Google Gemini** (`gemini-3.8-flash`) via the official `google-genai` SDK.
  - **Zero Silent Fallback**: If Gemini credentials are missing or the API is unavailable, the MetaQA verifier reports `UNAVAILABLE` rather than silently substituting the local generator model.
  - **Failure Isolation**: API errors, rate limits, and JSON parse failures are explicitly recorded as technical errors (`parse_failed=True`) and are **never** counted as legitimate `NOT SURE` judgments.
- **Optimized Mutation Generation**:
  - Replaces separate claim-extraction LLM requests with 0ms deterministic string parsing (`fallback_claims_from_answer`).
  - Generates both synonym (meaning-preserving) and antonym (meaning-reversing) mutations together in a single structured LLM call with a 300-token cap.
  - Employs `OLLAMA_KEEP_ALIVE=30m` so weights remain resident in memory between requests.
- **Targeted Web Evidence Pipeline**:
  - Rule-based question-type classification and category-specific authoritative domain routing.
  - Focused queries via Tavily Basic Search with credit and concurrency caps (`WEB_MAX_CLAIMS=3`, `WEB_MAX_SEARCHES=3`, `WEB_RESULTS_PER_CLAIM=2`).
  - **Claim-Relevant Evidence Extraction**: Automatically cleans navigation boilerplate, headers, and noise, extracting the 1–2 sentences most relevant to the claim.
  - Claim verdicts: `SUPPORTED`, `CONTRADICTED`, and `INSUFFICIENT_EVIDENCE`.
  - Invariance: Evidence insufficiency is **never** treated as a hallucination.
- **Overall VeriFact Assessment Synthesis**:
  - Deterministically evaluates branch signals into unified assessment labels (`Likely Reliable`, `Potentially Hallucinated`, `Needs Verification`, `Insufficient Evidence`).
  - Calculates application-level **Combined Hallucination Risk**:
    $$\text{Combined Risk} = 0.5 \times \text{MetaQA Score} + 0.5 \times (1.0 - \text{Web Consistency Score})$$
- **Mock Mode for Development & Testing**: Complete deterministic fixtures for LLM calls and web search (`LLM_MODE=mock`), enabling comprehensive local automated testing without live credentials or local GPU dependencies.

---

## Setup & Installation

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment file
copy .env.example .env
```

### Live Ollama Setup
1. Install and start Ollama (`http://localhost:11434`).
2. Pull the configured model:
   ```bash
   ollama pull gemma4:26b
   ```
3. Set in `.env`:
   ```env
   LLM_MODE=live
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434/v1
   OLLAMA_ALLOWED_MODELS=gemma4:26b
   OLLAMA_KEEP_ALIVE=30m
   GENERATOR_MODEL=gemma4:26b
   VERIFIER_MODEL=gemma4:26b
   SYNONYM_COUNT=3
   ANTONYM_COUNT=3
   ```

### Live Cloud Verifiers & Web Search
Add your API keys to `backend/.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_VERIFIER_MODEL=gemini-3.8-flash
TAVILY_API_KEY=your_tavily_api_key_here
```

---

## Running the Backend

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Health check: `GET http://127.0.0.1:8000/api/health`
- Settings check: `GET http://127.0.0.1:8000/api/settings`

---

## Environment Variables Reference

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | string | `development` | Environment mode (`development`, `production`, `test`). |
| `DATABASE_URL` | string | `sqlite:///./data/verifact.db` | SQLAlchemy SQLite database connection string. |
| `FRONTEND_ORIGIN` | string | `http://localhost:5173` | Allowed CORS frontend origin. |
| `LLM_MODE` | `mock` \| `live` | `mock` | Execution mode. `mock` uses local deterministic fixtures. |
| `LLM_PROVIDER` | `ollama` \| `openai_compatible` | `openai_compatible` | Generator model provider. |
| `OLLAMA_BASE_URL` | string | `http://localhost:11434/v1` | Ollama API endpoint. |
| `OLLAMA_ALLOWED_MODELS` | string | `gemma4:26b` | Comma-delimited allowlist of model IDs. |
| `OLLAMA_KEEP_ALIVE` | string | `30m` | Time model weights stay resident in memory. |
| `GENERATOR_MODEL` | string | `gemma4:26b` | Local model for answering questions. |
| `MUTATION_MODEL` | string | `""` | Optional override model for mutations (defaults to generator). |
| `SYNONYM_COUNT` | int | `3` | Number of meaning-preserving mutations per Detect run. |
| `ANTONYM_COUNT` | int | `3` | Number of meaning-reversing mutations per Detect run. |
| `THRESHOLD` | float | `0.5` | Classification threshold $\theta$ ($H \ge \theta \implies \text{Hallucinated}$). |
| `LLM_TIMEOUT_SECONDS` | float | `60.0` | Timeout per LLM generation request. |
| `LLM_ANSWER_MAX_TOKENS` | int | `350` | Output token cap for candidate answer generation. |
| `LLM_MUTATION_MAX_TOKENS` | int | `300` | Output token cap for mutation generation. |
| `GEMINI_API_KEY` | string | `""` | Google Gemini API key for cross-model verification. |
| `GEMINI_VERIFIER_MODEL` | string | `gemini-3.8-flash` | Gemini model ID for MetaQA mutation verification. |
| `GEMINI_VERIFY_CONCURRENCY`| int | `3` | Max concurrent verifier requests to Gemini API. |
| `TAVILY_API_KEY` | string | `""` | Tavily API key for Web Evidence. |
| `TAVILY_SEARCH_DEPTH` | string | `basic` | Tavily search depth (`basic` or `advanced`). |
| `WEB_EVIDENCE_ENABLED` | bool | `true` | Master switch for the Web Evidence pipeline. |
| `WEB_MAX_CLAIMS` | int | `3` | Maximum claims extracted per Detect run. |
| `WEB_MAX_SEARCHES` | int | `3` | Maximum Tavily searches per Detect run. |
| `WEB_RESULTS_PER_CLAIM` | int | `2` | Number of search results retained per claim. |

---

## API Routes

### Interactive Detection & History
- `POST /api/detect`: Accepts `{ "question": "..." }`, generates the base answer, creates a run record with status `answer_ready`, schedules parallel background verification tasks, and returns immediately.
- `GET /api/runs/{id}`: Returns the live state of the run, including candidate answer, MetaQA mutation verdicts and score, Web Evidence claims and sources, and the Overall VeriFact Assessment.
- `GET /api/runs`: Returns a paginated list of previous detection runs.
- `DELETE /api/runs/{id}`: Deletes a specific run record and associated mutations.
- `GET /api/health`: System health status, provider readiness, and active model names.
- `GET /api/settings`: Non-sensitive configuration metadata for UI display.

### Offline Evaluation & Experiments
- `POST /api/evaluations/run`: Runs offline ground-truth evaluation over curated benchmark datasets in `data/datasets/`.
- `POST /api/experiments/run`: Runs 2×2 same-model vs. cross-model research experiments.
- `GET /api/experiments/{id}`: Returns experiment analysis and condition comparisons.

---

## Architecture & Module Organization

```text
backend/app/
├── api/                   # FastAPI route endpoints
├── core/                  # Logging, error types, and system utilities
├── database/              # SQLAlchemy schema models and session management
├── llm/                   # LLM clients: OllamaClient, GeminiClient, MockLLMClient
├── metaqa/                # MetaQA metamorphic testing:
│   ├── mutation.py        # Optimized single-request mutation generator
│   ├── verifier.py        # Independent verifier orchestration & error isolation
│   └── scoring.py         # Deterministic contribution matrix & score computation
├── web_evidence/          # Web Evidence pipeline:
│   ├── pipeline.py        # Async coordination of search, extraction, and verification
│   ├── classifier.py      # Question categorization
│   ├── evidence_extractor.py # Claim-relevant snippet cleaner & extractor
│   ├── strategies.py      # Authoritative domain recommendations
│   └── scoring.py         # Claim-level evidence consistency scoring
├── web_search/            # Tavily search client & mock search provider
├── schemas/               # Pydantic request and response schemas
├── services/              # Run orchestration & verification summary fusion
├── config.py              # Pydantic settings definition
└── main.py                # FastAPI app initialization and CORS middleware
```

---

## Testing

The backend includes a comprehensive automated test suite with **339 tests** covering all pipelines, scoring functions, mutation edge cases, error handlers, and summary fusion rules:

```bash
# Run the complete test suite
pytest

# Run tests with short progress output
pytest -q
```

All unit tests execute offline using deterministic test fixtures in ~7-8 seconds without requiring external network access or running local models.
