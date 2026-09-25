# System Architecture

VeriFact is a research-oriented hallucination detection system and experimentation platform. It comprises a modern React single-page application, a high-performance FastAPI backend service, an SQLite persistence layer, and a multi-provider LLM abstraction layer.

The core detection engine is strictly **reference-free** (zero-resource), evaluating answer consistency without external web search, Wikipedia, or retrieval-augmented generation (RAG).

---

## High-Level Component Topology

```text
┌─────────────────────────────────────────────────────────────┐
│                 Frontend UI (React 19 + Vite)               │
│                                                             │
│   DetectPage        ExperimentsPage   HistoryPage           │
│   (Progressive UI)  (2×2 Matrix)      (Run Traces)          │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP REST / JSON (Vite proxy)
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend Service                  │
│                                                             │
│   Routing Layer (`app.api`):                                │
│   ├── routes_detect.py        (POST /api/detect, async task)│
│   ├── routes_runs.py          (GET /api/runs, GET /runs/{id}│
│   ├── routes_experiments.py   (2×2 experiment endpoints)    │
│   ├── routes_evaluations.py   (Ground-truth evaluation API) │
│   ├── routes_health.py        (GET /api/health)             │
│   └── routes_settings.py      (Public configuration)        │
│                                                             │
│   Core MetaQA Engine (`app.metaqa`):                        │
│   ├── detector.py             (Orchestrator & stage timings)│
│   ├── mutation.py             (Claim extraction & mutations)│
│   ├── verifier.py             (YES / NO / NOT SURE parser)  │
│   └── scoring.py              (Deterministic scoring table) │
│                                                             │
│   Service & Persistence Layer (`app.services`, `app.database│
│   ├── run_service.py          (Stage-by-stage DB updates)   │
│   ├── experiment_service.py   (Frozen 2×2 study orchestration│
│   └── db.py                   (SQLAlchemy SQLite engine)    │
│                                                             │
│   LLM Abstraction Layer (`app.llm`):                        │
│   ├── OllamaClient            (Native /api/chat, think=false│
│   ├── OpenAICompatibleClient  (Standard /chat/completions)  │
│   └── MockLLMClient           (Deterministic test fixtures) │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
    ┌──────────────────────┐        ┌──────────────────────┐
    │  SQLite Database     │        │  Local Ollama Daemon │
    │  data/verifact.db    │        │  http://localhost:   │
    │  - runs              │        │  11434               │
    │  - mutations         │        │  (Model: gemma4:26b) │
    │  - experiments       │        │                      │
    └──────────────────────┘        └──────────────────────┘
```

---

## 1. Frontend Architecture

- **Framework**: React 19, TypeScript, Vite.
- **Styling**: Tailwind CSS (Tailwind v4 with `@tailwindcss/vite`).
- **Icons & Navigation**: `lucide-react`, `react-router-dom`.
- **Pages**:
  - `DetectPage`: Progressive detection dashboard. As soon as the answer is generated, it renders. The client then polls `GET /api/runs/{id}` to display newly generated mutations, live verification verdicts, and the final classification.
  - `ExperimentsPage`: 2×2 research interface for configuring and executing same-model vs. cross-model studies.
  - `HistoryPage`: Paginated run history with filtering and search capabilities.
  - `MetaQAPage`: Interactive explanation of MetaQA methodology and scoring tables.
  - `SettingsPage`: Inspection of active non-secret runtime configuration.
- **Truthful Status Banners**:
  - Displays **Live Mode — Local Ollama · Model: gemma4:26b** when running against Ollama.
  - Displays **Demo / Mock Mode** when running with synthetic test fixtures.

---

## 2. Backend Architecture

- **Framework**: FastAPI with Pydantic v2 schemas and validation settings (`pydantic-settings`).
- **Asynchronous Execution**: Uses FastAPI's `BackgroundTasks` to decouple answer generation from metamorphic testing:
  1. `POST /api/detect` accepts the question and synchronously invokes `generate_answer()`.
  2. The initial run is persisted to SQLite with status `answer_ready`.
  3. The response is returned to the client immediately.
  4. `_continue_metaqa_analysis()` runs asynchronously on the event loop with its own dedicated database session and LLM client instance.
- **Stage-by-Stage Callbacks**:
  - `on_stage(stage)`: Records transition (`generating_mutations`, `verifying_mutations`, `calculating_score`).
  - `on_mutations_ready(mutations)`: Saves mutation statements to SQLite with status `mutations_ready`.
  - `on_mutation_verified(position, scored)`: Streams completed verification results into the database as individual mutations finish.

---

## 3. MetaQA Engine (`app.metaqa`)

- **`detector.py`**:
  - Coordinates answer generation, mutation generation, concurrent verification, and score computation.
  - Measures high-resolution stage timings (`answer_ms`, `mutation_ms`, `verify_ms`, `total_ms`).
- **`mutation.py`**:
  - Extracts 3–4 atomic factual claims using `extract_core_claims()` (falls back to deterministic sentence splitting if the model fails).
  - Generates balanced synonym (meaning-preserving) and antonym (meaning-reversing) mutations.
  - Enforces syntactic heuristics: rejects fragments, incomplete sentences, duplicate phrases, questions, and no-op copies.
  - Partial retry loop: only requests missing mutations across up to 4 rounds rather than throwing away valid ones.
- **`verifier.py`**:
  - Sends individual mutated statements to the verifier LLM with the prompt *"Does the answer support this statement?"*.
  - Strict parsing: parses `YES`, `NO`, or `NOT SURE`. Robust fallback converts ambiguous or unparseable outputs to `NOT SURE`.
- **`scoring.py`**:
  - Evaluates each verdict deterministically:
    - Synonym: `YES` = 0.0, `NO` = 1.0, `NOT SURE` = 0.5
    - Antonym: `YES` = 1.0, `NO` = 0.0, `NOT SURE` = 0.5
  - Aggregates the mean contribution score bounded to $[0.0, 1.0]$.
  - Classifies as **Hallucinated** ($H \ge 0.5$) or **Reliable** ($H < 0.5$).

---

## 4. LLM Abstraction Layer (`app.llm`)

All LLM clients inherit from the abstract base class `LLMClient` (`complete_text` and `complete_json`):

1. **`OllamaClient`** (`app/llm/ollama.py`):
   - Interfaces directly with native Ollama `/api/chat`.
   - Forces `think: false` to disable hidden reasoning loops that exhaust token budgets.
   - Enforces persistent connection pooling and keep-alive (`OLLAMA_KEEP_ALIVE=30m`).
2. **`OpenAICompatibleClient`** (`app/llm/client.py`):
   - Calls OpenAI-compatible chat completion endpoints (`/chat/completions`).
   - Supports exponential backoff and retry handling.
3. **`MockLLMClient`** (`app/llm/mock.py`):
   - Returns deterministic, fixture-based responses for tests and CI without external dependencies.

---

## 5. Persistence & Storage (`app.database`, `app.services`)

- **Engine**: SQLite via SQLAlchemy ORM (default path `backend/data/verifact.db`).
- **Models**:
  - `Run`: Stores question, generated base answer, generator model, hallucination score, classification, stage timings, and status.
  - `MutationRecord`: Stores individual mutation statements, mutation type, verifier model, verdict, contribution, and rationale.
  - `ExperimentRecord` & `ConditionRecord`: Stores 2×2 experiment matrices, frozen mutation hashes, and paired evaluation metrics.

---

## 6. Research Boundary & Future Extensions

- **Zero-Resource Constraint**: The active system operates entirely without live web retrieval, Google Search, Wikipedia, or RAG.
- **Future Work**: A planned future extension will introduce an external Web Evidence pipeline (source search, claim extraction, and document-level verification). In the current release, this is strictly future work.
