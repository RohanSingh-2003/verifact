# VeriFact Backend

FastAPI service for MetaQA-based fact-conflicting hallucination detection and controlled 2×2 model experimentation.

## Key Capabilities

- **Live Local Inference**: Native integration with [Ollama](https://ollama.com) (`LLM_PROVIDER=ollama`) using models such as **Gemma 4:26b** (`gemma4:26b`).
- **OpenAI-Compatible Support**: Connect to any OpenAI-compatible API (`LLM_PROVIDER=openai_compatible`).
- **Mock Mode**: Deterministic fixtures for unit testing and CI pipelines (`LLM_MODE=mock`).
- **Progressive Detection**: Answers return immediately upon generation (`answer_ready`), with MetaQA mutation and verification continuing in the background on the same run.
- **Reference-Free**: Operates without external web retrieval, Google Search, Wikipedia, or vector databases.

---

## Setup & Installation

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
```

### Live Ollama Setup
1. Install and start Ollama (`http://localhost:11434`).
2. Pull the configured model:
   ```bash
   ollama pull gemma4:26b
   ```
3. Ensure `.env` contains:
   ```env
   LLM_MODE=live
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434/v1
   OLLAMA_API_KEY=ollama
   OLLAMA_ALLOWED_MODELS=gemma4:26b
   OLLAMA_KEEP_ALIVE=30m
   GENERATOR_MODEL=gemma4:26b
   VERIFIER_MODEL=gemma4:26b
   SYNONYM_COUNT=3
   ANTONYM_COUNT=3
   VERIFY_CONCURRENCY=3
   LLM_TIMEOUT_SECONDS=300
   ```
   *(A real OpenAI API key is not required for Ollama. Live mode never silently falls back to Mock.)*

---

## Starting the Service

```bash
uvicorn app.main:app --reload --port 8000
```

- Health check: `GET http://localhost:8000/api/health`
- Settings check: `GET http://localhost:8000/api/settings`

---

## Environment Variables Reference

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `LLM_MODE` | `mock` \| `live` | `mock` | Runtime execution mode. |
| `LLM_PROVIDER` | `ollama` \| `openai_compatible` | `openai_compatible` | LLM backend client. |
| `OLLAMA_BASE_URL` | string | `http://localhost:11434/v1` | Ollama service endpoint. |
| `OLLAMA_ALLOWED_MODELS` | string | `gemma4:26b` | Comma-delimited allowlist of Ollama model IDs. |
| `OLLAMA_KEEP_ALIVE` | string | `30m` | Duration model remains resident in memory. |
| `GENERATOR_MODEL` | string | `gpt-4o-mini` | Generator model ID for interactive Detect. |
| `VERIFIER_MODEL` | string | `gpt-4o-mini` | Verifier model ID for interactive Detect. |
| `SYNONYM_COUNT` | int | `5` (env sets `3` for Detect) | Target meaning-preserving mutations. |
| `ANTONYM_COUNT` | int | `5` (env sets `3` for Detect) | Target meaning-reversing mutations. |
| `THRESHOLD` | float | `0.5` | Classification threshold $\theta$. |
| `VERIFY_CONCURRENCY` | int | `5` (env sets `3` for Detect) | Max concurrent verifier calls. |
| `DATABASE_URL` | string | `sqlite:///./data/verifact.db` | SQLAlchemy SQLite connection URI. |
| `FRONTEND_ORIGIN` | string | `http://localhost:5173` | Allowed CORS origin. |

---

## API Routes

### Interactive Detection
- **`POST /api/detect`**: Generates the base answer, stores the run with status `answer_ready`, schedules background MetaQA analysis, and returns immediately.
- **`GET /api/runs/{run_id}`**: Retrieves the progressively updated run state (used by the frontend poll loop).
- **`GET /api/runs`**: Paginated run history.

### Experiments & Evaluation
- **`POST /api/experiments/estimate`**: Returns cost and query estimates for a 2×2 run.
- **`POST /api/experiments/run`**: Executes a 2×2 study across generator and verifier pairs with frozen mutation controls.
- **`GET /api/experiments/{id}`**: Retrieves stored 2×2 metrics and CSV/JSON export artifacts.
- **`GET /api/experiments/latest`**: Returns the most recently completed experiment.
- **`POST /api/evaluations/run`**: Offline ground-truth evaluation over curated datasets.

---

## Testing & Quality

```bash
# Run backend pytest test suite (162 tests)
pytest

# Run linter
ruff check .
```

*All unit tests use the internal `MockLLMClient` and do not invoke external network endpoints or local Ollama instances.*
