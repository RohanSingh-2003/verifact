# VeriFact

**Verify what AI says.**

VeriFact is a MetaQA-based framework for detecting **fact-conflicting hallucinations** in Large Language Models (LLMs). It applies metamorphic testing using meaning-preserving (synonym) and meaning-reversing (antonym) mutations to evaluate whether a model's generated answer remains semantically consistent under controlled restatements. Higher inconsistency yields a higher hallucination score and classifies the answer as **Hallucinated** or **Reliable**.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-frontend-3178C6?logo=typescript&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-000000)
![pytest](https://img.shields.io/badge/pytest-162%20passed-0A9EDC?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## Overview

Large language models frequently generate confident, fluent text that contradicts established facts. Detecting these hallucinations is challenging:

- **Why self-reflection fails:** Simply asking an LLM *"Is your previous answer correct?"* is unreliable. Models exhibit strong self-confirmation bias, sycophancy, and recurrent agreement with their own past generations.
- **The metamorphic testing alternative:** Rather than asking for a direct self-evaluation, **MetaQA** restates core claims from the generated answer into controlled variations:
  - **Synonym mutations** (meaning-preserving): The verifier is expected to agree (**YES**).
  - **Antonym mutations** (meaning-reversing): The verifier is expected to disagree (**NO**).
- **Inconsistency reveals hallucination:** If an LLM agrees with contradictory restatements of its own claims or rejects valid paraphrases, it reveals underlying semantic fragility and inconsistency—signaling a fact-conflicting hallucination.

VeriFact provides a complete, reference-free software implementation of this methodology, coupled with a progressive interactive web interface, local LLM execution via Ollama, and controlled 2×2 experiment infrastructure.

---

## Why VeriFact?

1. **Zero-Resource / Reference-Free**: Evaluates answer consistency without requiring Google, Wikipedia, RAG pipelines, vector databases, embeddings, or external search APIs.
2. **Progressive Responsiveness**: Users see the generated AI answer immediately. Metamorphic mutation generation, independent verification, and scoring proceed in the background on the same run.
3. **Local & Private Execution**: Runs locally using **Ollama** and **Gemma 4:26b**, eliminating mandatory external API keys and cloud dependencies.
4. **Deterministic Scoring**: Scoring is calculated strictly by VeriFact’s mathematical engine—not judged by an LLM prompt.
5. **Auditable Traces**: Every core claim, mutation text, verifier label, and intermediate contribution is persisted in SQLite for inspectability.

---

## Key Features

- **Local LLM Inference**: Direct integration with [Ollama](https://ollama.com) via native `/api/chat` with reasoning controls (`think=false`).
- **Gemma 4:26b Support**: Configured for local generation and verification using Google's Gemma 4:26b model.
- **MetaQA Metamorphic Engine**: Automated core claim extraction followed by meaning-preserving and meaning-reversing statement generation.
- **Independent Verification**: Evaluates restatements without revealing mutation types, expected verdicts, or reference answers to the verifier.
- **Deterministic MetaQA Scoring**: Mathematical averaging of contribution scores mapped to a configurable decision threshold ($\theta = 0.5$).
- **Progressive Detection**: Answers display immediately (`answer_ready`), while mutation generation and verification update live via polling.
- **Dual Operating Modes**:
  - **Live Mode**: Real model generations via Ollama (`LLM_PROVIDER=ollama`) or hosted OpenAI-compatible APIs (`LLM_PROVIDER=openai_compatible`).
  - **Mock Mode**: Fast, deterministic fixture-based execution for local UI testing, development, and automated CI pipelines.
- **Controlled 2×2 Experiments**: Separate research runner for comparing same-model versus cross-model verifier behaviors ($A \to A, A \to B, B \to A, B \to B$) with frozen mutation sets.
- **Run History & Persistence**: SQLite-backed storage for individual detection runs, stage timings, and mutation records.

*(Note: External web search, Tavily integration, and live internet retrieval are planned future extensions and are not implemented in the current repository.)*

---

## How VeriFact Works

```text
       User Question
             ↓
     FastAPI Backend
             ↓
  Gemma 4:26b (via Ollama)
             ↓
         AI Answer ──────────────────────► Answer displayed immediately
             ↓
   MetaQA Background Analysis (same run_id)
             ↓
  Extract Core Claims (3-4 claims)
             ↓
   Generate Mutations ───────────────────► Mutations displayed when ready
   ├── Synonym Mutations (meaning-preserving)
   └── Antonym Mutations (meaning-reversing)
             ↓
   Verify Mutations (YES / NO / NOT SURE) ─► Verdicts displayed as received
             ↓
  Deterministic Scoring Engine (mean contribution)
             ↓
  Final Classification (Reliable vs. Hallucinated)
```

### The Pipeline Stages

1. **Answer Generation**: The generator model (`gemma4:26b`) produces a concise factual answer. The API saves the run and returns the answer immediately (`status: answer_ready`).
2. **Core Claim Extraction**: VeriFact extracts 3–4 short, atomic factual claims from the answer (or falls back to deterministic sentence splitting if needed).
3. **Mutation Generation**: For each claim, meaning-preserving (synonym) and meaning-reversing (antonym) variations are created and filtered against syntax, fragment, and length heuristics.
4. **Mutation Verification**: The verifier evaluates each mutated statement independently given the original question and answer. Allowed labels are **YES**, **NO**, or **NOT SURE** (malformed outputs safely fall back to NOT SURE).
5. **Deterministic Scoring**: Each verdict produces a numeric contribution according to the MetaQA contribution matrix.
6. **Classification**: The aggregate hallucination score is compared against the threshold ($\theta = 0.5$) to classify the run as **Reliable** or **Hallucinated**.

---

## System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                 Frontend (React 19 + Vite)                  │
│       Detect UI  ·  Experiments  ·  History  ·  Settings    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / JSON (Vite proxy /api)
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend Service                  │
│   app.api.routes_detect        app.api.routes_experiments   │
│   app.api.routes_runs          app.api.routes_health        │
│   app.api.routes_evaluations   app.api.routes_settings      │
├─────────────────────────────────────────────────────────────┤
│                     Core Services & Logic                   │
│   app.metaqa.detector          app.services.run_service     │
│   app.metaqa.mutation          app.services.experiment_svc │
│   app.metaqa.verifier          app.metaqa.scoring           │
├─────────────────────────────────────────────────────────────┤
│                     LLM Provider Layer                      │
│   OllamaClient (native /api/chat, think=false, keep-alive)  │
│   OpenAICompatibleClient (chat completions /v1)             │
│   MockLLMClient (deterministic scenarios & test fixtures)   │
├──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
    ┌──────────────────────┐        ┌──────────────────────┐
    │  SQLite Database     │        │  Local Ollama Daemon │
    │  data/verifact.db    │        │  http://localhost:   │
    │  Runs & Experiments  │        │  11434 (Gemma 4:26b) │
    └──────────────────────┘        └──────────────────────┘
```

---

## MetaQA Methodology

MetaQA frames hallucination detection as a metamorphic consistency test under controlled semantic perturbation.

### Synonym Mutations (Meaning-Preserving)
- **Goal**: Rephrase a core claim using different words or structure while keeping its semantic truth value identical to the original answer.
- **Expected Behavior**: A coherent model that believes its original answer should agree with the paraphrase.
- **Expected Verdict**: `YES`

### Antonym Mutations (Meaning-Reversing)
- **Goal**: Invert, negate, or substitute key entities in a core claim to create a statement that contradicts the original answer.
- **Expected Behavior**: A coherent model that believes its original answer should reject the contradiction.
- **Expected Verdict**: `NO`

### Why This Detects Hallucinations
When an LLM hallucinates, it lacks firm probabilistic or semantic grounding for the generated facts. Consequently, under perturbation:
- It may agree with an inverted statement (e.g., agreeing that *"Canberra is NOT the capital of Australia"* after stating it is).
- It may reject a valid paraphrase of its own statement.
- Such contradictory behavior yields elevated penalty scores across the mutation suite.

---

## MetaQA Scoring

VeriFact's scoring is **completely deterministic** and computed by Python code, not by prompting an LLM to assign a grade.

### 1. Contribution Matrix

For each mutation $i \in \{1, \dots, N\}$, the contribution score $c_i$ is determined by its mutation type and observed verifier verdict:

| Mutation Type | Verdict: `YES` | Verdict: `NO` | Verdict: `NOT SURE` |
| :--- | :---: | :---: | :---: |
| **Synonym** (Expected: `YES`) | **0.0** (Consistent) | **1.0** (Inconsistent) | **0.5** (Uncertain) |
| **Antonym** (Expected: `NO`) | **1.0** (Inconsistent) | **0.0** (Consistent) | **0.5** (Uncertain) |

### 2. Aggregate Hallucination Score

The total hallucination score $H$ is the arithmetic mean of all individual mutation contributions:

$$H = \frac{1}{N} \sum_{i=1}^{N} c_i \quad \text{where } H \in [0.0, 1.0]$$

### 3. Classification Rule

Given decision threshold $\theta$ (default $\theta = 0.5$):

$$\text{Classification} = \begin{cases} \mathbf{Hallucinated} & \text{if } H \ge \theta \\ \mathbf{Reliable} & \text{if } H < \theta \end{cases}$$

- Verifier rationales are recorded for explainability only; they do not alter the mathematical score.
- Malformed verifier outputs or unexpected network errors default safely to `NOT SURE` ($c_i = 0.5$).
- Classification outputs are strictly **Reliable** or **Hallucinated**.

---

## Mutation Counts: Detect vs. Experiments

VeriFact separates interactive user detection from research experiments:

| Configuration | Synonym Mutations | Antonym Mutations | Total per Run | Primary Purpose |
| :--- | :---: | :---: | :---: | :--- |
| **Interactive Detect** | **3** | **3** | **6** | Optimized for practical latency on local 26B hardware (`SYNONYM_COUNT=3`, `ANTONYM_COUNT=3`). |
| **Research Experiments** | **5** | **5** | **10** | Standard 2×2 study scaffold (`ExperimentRunRequest`), frozen and reused across verifiers. |

---

## Ollama + Gemma 4:26b Integration

VeriFact supports local, private inference using [Ollama](https://ollama.com).

- **Configured Model**: `gemma4:26b` (Gemma 4 26B parameter model).
- **Native Ollama Client**: Uses Ollama's native `/api/chat` endpoint with `think: false` to ensure deterministic structured JSON output without consuming token budgets on reasoning traces.
- **Connection Efficiency**: Reuses persistent `httpx.AsyncClient` instances with HTTP keep-alive (`OLLAMA_KEEP_ALIVE=30m`).
- **Privacy & Zero Cost**: No OpenAI API key or cloud subscriptions required when running locally.

### Verified Environment Configuration

The backend reads settings from `backend/.env`. Key variables confirmed by the codebase:

```env
# Runtime mode: 'live' or 'mock'
LLM_MODE=live

# Provider: 'ollama' or 'openai_compatible'
LLM_PROVIDER=ollama

# Ollama connection parameters
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_API_KEY=ollama
OLLAMA_ALLOWED_MODELS=gemma4:26b
OLLAMA_KEEP_ALIVE=30m

# Generator and Verifier models
GENERATOR_MODEL=gemma4:26b
VERIFIER_MODEL=gemma4:26b

# Interactive Detect mutation and concurrency knobs
SYNONYM_COUNT=3
ANTONYM_COUNT=3
THRESHOLD=0.5
VERIFY_CONCURRENCY=3
LLM_TIMEOUT_SECONDS=300
LLM_MAX_RETRIES=1
LLM_TEMPERATURE=0
LLM_ANSWER_MAX_TOKENS=350
LLM_CLAIM_MAX_TOKENS=256
LLM_MUTATION_MAX_TOKENS=700
LLM_VERIFY_MAX_TOKENS=96
```

---

## Progressive Detection Flow

Local 26B inference requires significant compute time. To eliminate perceived latency, VeriFact implements a progressive execution pipeline:

```text
POST /api/detect
      ↓
Generate base answer via Gemma 4:26b
      ↓
Persist run in SQLite (status: answer_ready)
      ↓
Return response immediately to user (Answer visible in UI!)
      ↓
BackgroundTasks triggers _continue_metaqa_analysis(run_id)
      ↓
Extract claims & generate mutations (status: generating_mutations → mutations_ready)
      ↓
Verify mutations concurrently (status: verifying_mutations)
      ↓
Compute aggregate score (status: calculating_score)
      ↓
Persist final results (status: completed)
```

The frontend polls `GET /api/runs/{run_id}`:
- **`answer_ready`**: Answer is displayed immediately.
- **`generating_mutations`**: Indicates test creation in progress.
- **`mutations_ready` / `verifying_mutations`**: Mutation statements become visible; individual verdicts update in real time.
- **`completed`**: Final MetaQA score and **Reliable / Hallucinated** classification appear.
- **`failed`**: If analysis fails, the generated answer remains visible alongside the failure stage.

---

## Mock vs. Live Mode

| Attribute | Demo / Mock Mode (`LLM_MODE=mock`) | Live Mode (`LLM_MODE=live`, Ollama) |
| :--- | :--- | :--- |
| **Backend Engine** | `MockLLMClient` | `OllamaClient` |
| **Model** | Deterministic fixtures | `gemma4:26b` (local Ollama daemon) |
| **Hardware Required** | Minimal (runs on any CPU) | GPU recommended (or capable CPU with 24GB+ RAM) |
| **Response Latency** | Instant (~100 ms) | Seconds to minutes (hardware dependent) |
| **UI Indicator** | Amber banner: **Demo / Mock Mode** | Green badge: **Live Mode — Local Ollama** |
| **Use Cases** | Unit tests, pytest suite, CI, fast UI demos | Real hallucination detection and interactive experiments |

*Note: Live mode never silently falls back to Mock mode. If Ollama is unreachable, the system reports a descriptive error.*

---

## Research Experiments (2×2 Framework)

VeriFact includes a research experiment module designed to investigate whether LLMs exhibit self-verification bias:
- **Condition Matrix**:
  - $A \to A$: Model A generates, Model A verifies (Same-model)
  - $A \to B$: Model A generates, Model B verifies (Cross-model)
  - $B \to A$: Model B generates, Model A verifies (Cross-model)
  - $B \to B$: Model B generates, Model B verifies (Same-model)
- **Experimental Control**: Core claims and mutation sets are generated once per question and **frozen** across verifiers, guaranteeing that verifier comparisons are not confounded by differing mutation texts.
- **Frozen Repository Lock**: Artifact `58baff20-fb86-4f43-b20e-895a086ceb6b` (n=40 pilot) is **Mock Mode demonstration data**. It confirms pipeline mechanics and illustrates verifier calibration confounds, but does not represent live LLM empirical evidence.

---

## Installation & Quick Start

### Prerequisites
- **Python**: Version 3.11 or 3.12 (confirmed compatible up to 3.14)
- **Node.js**: Version 20+ (tested on Node 20 / 22)
- **Ollama**: (For Live mode) Installed and running from [ollama.com](https://ollama.com)

### 1. Clone the Repository
```bash
git clone https://github.com/RohanSingh-2003/verifact.git
cd verifact
```

### 2. Backend Setup
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

### 3. Ollama Setup (for Live Mode)
```bash
# Pull the Gemma 4:26b model
ollama pull gemma4:26b

# Verify Ollama is serving
ollama list
```

### 4. Frontend Setup
```bash
cd ../frontend

# Install dependencies
npm install
```

### 5. Running the Application

In terminal 1 (Backend):
```bash
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

In terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

Open your browser at **[http://localhost:5173](http://localhost:5173)**.

---

## Performance Considerations

Running local 26B parameter models (`gemma4:26b`) is compute-intensive. Latency depends directly on GPU VRAM, quantization, and system RAM:
- **First Request Warm-up**: The initial query after Ollama starts may experience additional load latency while the weights are mapped to memory.
- **Implemented Speed Optimizations**:
  - **Token Caps**: Stage-specific output limits (`LLM_ANSWER_MAX_TOKENS=350`, `LLM_CLAIM_MAX_TOKENS=256`, `LLM_MUTATION_MAX_TOKENS=700`, `LLM_VERIFY_MAX_TOKENS=96`).
  - **Bounded Concurrency**: Verifications execute concurrently with a semaphore (`VERIFY_CONCURRENCY=3`).
  - **Think Disabled**: Disabling reasoning traces on Ollama (`think: false`) prevents models from burning token allowances on hidden reasoning loops.
  - **Process-Level HTTP Re-use**: Async HTTP clients and connection pools are reused across calls.
  - **Keep-Alive**: Ollama models remain loaded in memory for 30 minutes (`OLLAMA_KEEP_ALIVE=30m`).

---

## Testing & Validation

All tests run locally using Mock LLM fixtures without external API costs or Ollama dependencies:

### 1. Backend Pytest Suite
```bash
cd backend
pytest
```
- **Current Status**: **162 passed**, 2 warnings in ~15s.

### 2. Ruff Linter
```bash
cd backend
ruff check .
```
- **Current Status**: 5 code-style lint notices in existing implementation (duplicate set items, startswith/endswith tuple formatting, and type union syntax).

### 3. Frontend Production Build
```bash
cd frontend
npm run build
```
- **Current Status**: **0 errors**, TypeScript typechecks and Vite bundles successfully (`tsc -b && vite build` in <1s).

---

## Project Structure

```text
verifact/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI route handlers (detect, runs, experiments, health)
│   │   ├── database/        # SQLAlchemy engine, session maker, SQLite models
│   │   ├── evaluation/      # Dataset loader and offline ground-truth evaluators
│   │   ├── llm/             # LLM clients (OllamaClient, OpenAICompatibleClient, MockLLMClient)
│   │   ├── metaqa/          # MetaQA core (detector, mutation generator, verifier, scoring)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── services/        # Run persistence, experiment orchestration, exports
│   ├── data/                # SQLite database (verifact.db) and evaluation datasets
│   ├── tests/               # 22 test files covering all backend units (162 tests)
│   ├── requirements.txt     # Python backend dependencies
│   └── ruff.toml            # Ruff linter configuration
├── frontend/
│   ├── src/
│   │   ├── api/             # API client bindings
│   │   ├── components/      # UI components (DetectForm, MutationTable, Header, etc.)
│   │   ├── pages/           # DetectPage, ExperimentsPage, HistoryPage, MetaQAPage, SettingsPage
│   │   └── types/           # TypeScript interfaces matching backend schemas
│   ├── package.json         # React 19, Vite, Tailwind CSS dependencies
│   └── vite.config.ts       # Vite configuration with /api backend proxy
├── docs/                    # In-depth architectural, methodological, and research notes
├── experiments/             # Frozen experiment artifacts and CSV/JSON export logs
└── LICENSE                  # MIT License
```

---

## Important Research Boundary

> [!IMPORTANT]
> **What MetaQA Does and Does Not Establish:**
> - MetaQA evaluates the **semantic self-consistency** of an LLM's generated answer under controlled transformations.
> - It does **not** independently prove factual truth in the real world. If a model consistently maintains a false premise under both synonym paraphrasing and antonym negation, MetaQA measures high consistency.
> - VeriFact's detector is strictly **reference-free** (zero-resource). It does not consult external databases or search engines during detection.

---

## Limitations

1. **Hardware Requirements**: Local Gemma 4:26b inference demands substantial compute and memory resources. On pure CPU, full MetaQA verification can take several minutes.
2. **Consistency vs. Factual Truth**: An internally coherent but completely fictitious generation can receive a low hallucination score if the verifier consistently mirrors the hallucinated logic.
3. **Mutation Quality**: Mutation generation relies on prompt adherence. If an LLM produces incomplete sentences or fails to negate a claim properly, heuristic filters reject the output and trigger retries.
4. **Verifier Imperfections**: Verifiers can occasionally return ambiguous or malformed text, which VeriFact safely defaults to `NOT SURE` (0.5 contribution).
5. **Research Prototype**: VeriFact is an academic research prototype designed to explore metamorphic consistency and verifier behavior, not a commercial fact-checking service.

---

## Future Work (Planned Extensions)

The following capabilities are **planned future extensions** and are **not yet implemented**:
- **Web Evidence Integration**: Integrating external search APIs (e.g., Tavily or SerpAPI) to retrieve live web sources.
- **Evidence-Grounded Claim Verification**: Extracting atomic claims and classifying them as **SUPPORTED**, **CONTRADICTED**, or **INSUFFICIENT EVIDENCE** against retrieved documents.
- **Hybrid MetaQA + Web Verification**: Cross-referencing internal metamorphic consistency scores with external retrieval confidence.
- **Browser Extension**: An interactive Chrome extension to verify text selected on web pages.
- **Expanded Multi-Model Trials**: Conducting large-scale live 2×2 trials across heterogeneous model families.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

*Copyright (c) 2026 VeriFact contributors.*
