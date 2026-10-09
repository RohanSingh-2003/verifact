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

### Cloud Providers Setup

VeriFact uses cloud/API-based LLM inference. Gemma 4:26B is accessed through Ollama Cloud; no local Ollama installation is required.

Configure cloud provider API keys in `backend/.env`:
```env
LLM_MODE=live

# 1. Ollama Cloud (Gemma 4:26B)
OLLAMA_CLOUD_BASE_URL=https://ollama.com/api
OLLAMA_API_KEY=your_ollama_cloud_key_here

# 2. Cloudflare Workers AI (GLM-4.7-Flash)
CLOUDFLARE_API_TOKEN=your_cloudflare_token_here
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id_here
CLOUDFLARE_BASE_URL=https://api.cloudflare.com/client/v4
CLOUDFLARE_MODEL=@cf/zai-org/glm-4.7-flash

# 3. Groq (Qwen)
GROQ_API_KEY=your_groq_api_key_here
GROQ_BASE_URL=https://api.groq.com/openai/v1

# 4. OpenRouter (Liquid AI LFM 2.5)
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=liquid/lfm-2.5-2.6b:free

# 5. Google Gemini (Gemini Flash 3.8)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_VERIFIER_MODEL=gemini-3.8-flash

# Web Evidence (Tavily Search)
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
| `SYNONYM_COUNT` | int | `3` | Number of meaning-preserving mutations per Detect run. |
| `ANTONYM_COUNT` | int | `3` | Number of meaning-reversing mutations per Detect run. |
| `THRESHOLD` | float | `0.5` | Classification threshold $\theta$ ($H \ge \theta \implies \text{Hallucinated}$). |
| `LLM_TIMEOUT_SECONDS` | float | `60.0` | Timeout per LLM generation request. |
| `LLM_ANSWER_MAX_TOKENS` | int | `350` | Output token cap for candidate answer generation. |
| `OLLAMA_API_KEY` | string | `""` | Ollama Cloud API key for cloud inference (`https://ollama.com/api`). |
| `OLLAMA_CLOUD_BASE_URL` | string | `https://ollama.com/api` | Ollama Cloud API endpoint (local daemon not used). |
| `OLLAMA_CLOUD_MODEL` | string | `gemma4:26b` | Cloud model identifier for Gemma 4:26B. |
| `CLOUDFLARE_API_TOKEN` | string | `""` | Cloudflare API token with Workers AI access. |
| `CLOUDFLARE_ACCOUNT_ID` | string | `""` | Cloudflare account identifier. |
| `CLOUDFLARE_BASE_URL` | string | `https://api.cloudflare.com/client/v4` | Cloudflare API base URL. |
| `CLOUDFLARE_MODEL` | string | `@cf/zai-org/glm-4.7-flash` | GLM-4.7-Flash model identifier on Cloudflare Workers AI. |
| `GROQ_API_KEY` | string | `""` | Groq API key for Qwen model. |
| `GROQ_BASE_URL` | string | `https://api.groq.com/openai/v1` | Groq API endpoint. |
| `GROQ_MODEL` | string | `qwen-2.5-32b` | Qwen model ID on Groq. |
| `OPENROUTER_API_KEY` | string | `""` | OpenRouter API key. |
| `OPENROUTER_BASE_URL` | string | `https://openrouter.ai/api/v1` | OpenRouter API endpoint. |
| `OPENROUTER_MODEL` | string | `liquid/lfm-2.5-2.6b:free` | OpenRouter model ID. |
| `GEMINI_API_KEY` | string | `""` | Google Gemini API key. |
| `GEMINI_VERIFIER_MODEL` | string | `gemini-3.8-flash` | Gemini model ID for verification or generation. |
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
- `GET /api/models`: Returns list of available Answer Models (Gemini Flash 3.8, Gemma 4:26B, GLM-4.7-Flash, Qwen, OpenRouter), their cloud providers, configuration readiness, and default selection.
- `POST /api/detect`: Accepts `{ "question": "...", "answer_model": "gemma" }`, generates the base answer using the selected model, dynamically assigns all remaining models as the independent verifier pool (strictly excluding the answer generator), and schedules parallel background verification.
- `GET /api/runs/{id}`: Returns the live state of the run, including candidate answer, selected answer model, verifiers, MetaQA mutation verdicts and score, Web Evidence claims and sources, and the Overall VeriFact Assessment.
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
