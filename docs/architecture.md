# System Architecture

VeriFact is a research-oriented hallucination detection system. It comprises a modern React single-page application, a high-performance FastAPI backend service, an SQLite persistence layer, and a multi-provider LLM abstraction layer.

The core **MetaQA** detection engine is **reference-free** (zero-resource): it evaluates internal answer consistency without web search. VeriFact also runs an independent **Web Evidence** pipeline (Tavily) that checks extracted claims against retrieved snippets. The two signals are not collapsed into one score.

---

## High-Level Component Topology

```text
┌─────────────────────────────────────────────────────────────┐
│                 Frontend UI (React 19 + Vite)               │
│                                                             │
│   DetectPage        HistoryPage       MetaQAPage            │
│   (Progressive UI)  (Run Traces)      (Methodology)         │
│   SettingsPage                                              │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP REST / JSON (Vite proxy)
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend Service                  │
│                                                             │
│   Routing Layer (`app.api`):                                │
│   ├── routes_detect.py        (POST /api/detect, async task)│
│   ├── routes_runs.py          (GET /api/runs, GET /runs/{id}│
│   ├── routes_health.py        (GET /api/health)             │
│   ├── routes_settings.py      (Public configuration)        │
│   ├── routes_experiments.py   (Isolated study endpoints)    │
│   └── routes_evaluations.py   (Offline evaluation API)      │
│                                                             │
│   Core MetaQA Engine (`app.metaqa`):                        │
│   ├── detector.py             (Orchestrator & stage timings)│
│   ├── mutation.py             (Claim extraction & mutations)│
│   ├── verifier.py             (YES / NO / NOT SURE parser)  │
│   └── scoring.py              (Deterministic scoring table) │
│                                                             │
│   Web Evidence (`app.web_evidence`, `app.web_search`):      │
│   ├── classifier / strategies / claims / search_query       │
│   ├── dedupe / source_quality / verifier / pipeline         │
│   └── TavilyClient + MockTavilyClient + in-memory cache     │
│                                                             │
│   Service & Persistence Layer (`app.services`, `app.database│
│   ├── run_service.py          (Stage-by-stage DB updates)   │
│   ├── verification_summary.py (MetaQA ↔ Web compare, no %)  │
│   ├── experiment_service.py   (Offline study orchestration) │
│   └── db.py                   (SQLAlchemy SQLite engine)    │
│                                                             │
│   LLM Abstraction Layer (`app.llm`):                        │
│   ├── OllamaClient            (Generation: answer + mutants)│
│   ├── GeminiClient            (Cross-model MetaQA verifier) │
│   ├── OpenAICompatibleClient  (Standard /chat/completions)  │
│   └── MockLLMClient           (Deterministic test fixtures) │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
    ┌──────────────────┐ ┌───────────┐ ┌──────────────────┐
    │ SQLite Database  │ │ Local     │ │ Google Gemini    │
    │ data/verifact.db │ │ Ollama    │ │ API (Verifier)   │
    │ - runs           │ │ Gemma     │ │ gemini-2.5-flash │
    │ - mutations      │ │ 4:26b     │ └──────────────────┘
    └──────────────────┘ └───────────┘
```

---

## 1. Frontend Architecture

- **Framework**: React 19, TypeScript, Vite.
- **Styling**: Tailwind CSS (Tailwind v4 with `@tailwindcss/vite`).
- **Icons & Navigation**: `lucide-react`, `react-router-dom`.
- **Pages**:
  - `DetectPage` (`/`): Progressive detection dashboard. As soon as the base answer is generated, it renders. The client then polls `GET /api/runs/{id}` to display newly generated mutations, live verification verdicts, Web Evidence claims and sources, and the final Verification Summary.
  - `HistoryPage` (`/history`): Paginated run history with filtering, search capabilities, and audit traces.
  - `MetaQAPage` (`/metaqa`): Interactive explanation of MetaQA metamorphic methodology and scoring tables.
  - `SettingsPage` (`/settings`): Inspection of active runtime configuration parameters.
- **Truthful Status Banners**:
  - Displays **Live Mode — Local Ollama · Model: gemma4:26b** when running against Ollama.
  - Displays **Demo / Mock Mode** when running with synthetic test fixtures.

---

## 2. Backend Architecture

- **Framework**: FastAPI with Pydantic v2 schemas and validation settings (`pydantic-settings`).
- **Asynchronous Execution**: Uses FastAPI's `BackgroundTasks` to return the answer immediately, then runs MetaQA and Web Evidence **concurrently** inside one background task via `asyncio.gather(..., return_exceptions=True)`:
  1. `POST /api/detect` accepts the question and invokes `generate_answer()`.
  2. The initial run is persisted to SQLite with status `answer_ready`.
  3. The response is returned to the client immediately (`overall_status: running`).
  4. `_continue_metaqa_analysis()` and `_continue_web_evidence()` run in parallel with independent DB sessions, LLM clients, and exception handling — a failure in one branch never cancels the other.
  5. When both branches reach a terminal state, `overall_status` becomes `completed` (both succeeded) or `partial` (one or both verification branches failed/unavailable). Overall `failed` is reserved for missing AI answers.
- **Stage-by-Stage Callbacks (MetaQA)**:
  - `on_stage(stage)`: Records transition (`generating_mutations`, `verifying_mutations`, `calculating_score`).
  - `on_mutations_ready(mutations)`: Saves mutation statements to SQLite with status `mutations_ready`.
  - `on_mutation_verified(position, scored)`: Streams completed verification results into the database as individual mutations finish.
- **Web Evidence stages** progress independently (`classifying_question` → `extracting_claims` → `searching_web` → `verifying_evidence` → `completed` / `failed` / `unavailable`). Claim searches and claim verifications are concurrent within configured budgets.

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
   - Responsible for: AI answer generation and MetaQA mutation generation.
2. **`GeminiClient`** (`app/llm/gemini.py`):
   - Interfaces with Google Gemini API via the official `google-genai` SDK.
   - Responsible for: MetaQA mutation verification ONLY (never answer generation or mutation generation).
   - Returns structured JSON (`{"verdict": "YES" | "NO" | "NOT SURE", "rationale": "..."}`).
   - Never leaks expected verdicts or ground truth to the verifier.
   - No silent fallback: if Gemini fails or is unconfigured, MetaQA reports verification unavailable rather than falling back to Ollama.
   - Configured via `GEMINI_API_KEY`, `GEMINI_VERIFIER_MODEL`, and `GEMINI_VERIFY_CONCURRENCY`.
3. **`MockGeminiClient`** (`app/llm/gemini.py`):
   - Mock verifier client implementing `LLMClient` for tests and mock mode without API keys.
4. **`OpenAICompatibleClient`** (`app/llm/client.py`):
   - Calls OpenAI-compatible chat completion endpoints (`/chat/completions`).
   - Supports exponential backoff and retry handling.
5. **`MockLLMClient`** (`app/llm/mock.py`):
   - Returns deterministic, fixture-based responses for tests and CI without external dependencies.

### Why Cross-Model Verification Exists

The cross-model configuration allows the same generated answer and mutation set to be verified by a different LLM, enabling comparison between same-model and cross-model verifier behavior.

- **Same-model setup**: Gemma generates answer and mutations → Gemma verifies mutations.
- **Cross-model setup**: Gemma generates answer and mutations → Gemini verifies mutations.

The mutation set remains fixed when comparing verifiers, ensuring that the same question and same mutations can be evaluated by different models. This enables the experiment; the results determine what conclusions can be drawn.

---

## 5. Persistence & Storage (`app.database`, `app.services`)

- **Engine**: SQLite via SQLAlchemy ORM (default path `backend/data/verifact.db`).
- **Models**:
  - `Run`: Stores question, generated base answer, generator model, hallucination score, classification, stage timings, and status.
  - `MutationRecord`: Stores individual mutation statements, mutation type, verifier model, verdict, contribution, and rationale.
  - `ExperimentRecord` & `ConditionRecord`: Retained in database schema for offline research evaluation and automated reproducibility testing.

---

## 6. Research Boundary & Parallel Verification

- **MetaQA zero-resource constraint**: MetaQA itself operates without live web retrieval, Google Search, Wikipedia, or RAG.
- **Parallel Web Evidence**: After the AI answer is generated, MetaQA and Web Evidence execute as **independent parallel verification pipelines**. Either pipeline may complete, fail, or become unavailable without blocking the other. The AI answer is always displayed independently of verification.
- **Separate scores**: MetaQA score and Web Evidence consistency score remain separate. No combined hallucination percentage is produced. Partial verification is a valid state. Verification failure is not equivalent to hallucination.
