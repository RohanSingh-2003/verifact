# Release Notes: VeriFact v1.0.0

## Release Summary
VeriFact v1.0.0 establishes the production-grade software implementation of the MetaQA metamorphic hallucination detection framework extended with an independent Web Evidence verification layer. It features real local LLM inference via Ollama + Gemma 4:26b, a progressive web application architecture, and a deterministic side-by-side Verification Summary.

---

## Completed Milestones & Implemented Features

### 1. Core MetaQA Metamorphic Engine
- **Atomic Claim Extraction**: Automated extraction of 3–4 core factual claims from generated answers, with fallback to deterministic sentence segmentation.
- **Bilateral Mutation Generation**: Meaning-preserving (synonym) and meaning-reversing (antonym) transformations with heuristic sentence gates (rejecting fragments, questions, prefixes, duplicates, and no-ops).
- **Independent Verification**: Isolated verification prompting without leaking mutation categories, expected outcomes, or ground-truth references.
- **Robust Verdict Parsing**: Safe parsing of `YES`, `NO`, and `NOT SURE`, with malformed outputs defaulting gracefully to `NOT SURE`.
- **Deterministic Scoring**: Arithmetic mean of individual contributions mapped strictly to a 0.0–1.0 score and a calibrated threshold ($\theta = 0.5$) for **Reliable** versus **Hallucinated** classification.

### 2. Local LLM Integration (Ollama + Gemma 4:26b)
- **Ollama Provider**: Direct integration with local Ollama runtime via native `/api/chat`.
- **Gemma 4:26b**: Support for Google's Gemma 4:26b open-weights model for answer generation and verification.
- **Reasoning Loop Suppression (`think: false`)**: Native suppression of internal reasoning traces to ensure deterministic, token-budgeted JSON outputs.
- **HTTP Client Re-use**: Long-lived async connection pooling with `OLLAMA_KEEP_ALIVE=30m` for fast subsequent queries.

### 3. Progressive Detection Workflow
- **Answer-First Responsiveness**: Base answer is generated and returned immediately to the frontend (`status: answer_ready`), eliminating user wait time during local 26B inference.
- **Parallel verification**: After answer delivery, MetaQA and Web Evidence run concurrently via `asyncio.gather` with full error isolation. Either may fail without blocking the other or hiding the answer.
- **Overall status**: `running` | `completed` | `partial` | `failed` — partial means one verification branch failed while the answer (and possibly the other branch) remains available.
- **Incremental State Transitions**: Discrete MetaQA lifecycle states (`answer_ready` → `generating_mutations` → `mutations_ready` → `verifying_mutations` → `calculating_score` → `completed`), independent of Web Evidence stages.
- **Real-Time Polling**: Frontend polls `GET /api/runs/{id}` until **both** branches are terminal.

### 4. Targeted Web Evidence Pipeline
- **Question-type routing**: Rule-based classifier selects domain strategies (science, government, current events, statistics, technology, medicine, general facts).
- **Source strategies**: Preferred domain categories and freshness hints for Tavily Basic Search; automatically broadens when preferred results are insufficient.
- **Claim extraction & verification**: Strict snippet-only verification labeled `SUPPORTED`, `CONTRADICTED`, or `INSUFFICIENT_EVIDENCE`.
- **Source metadata**: Tags sources with institutional categories (OFFICIAL, ACADEMIC, GOVERNMENT, NEWS, REFERENCE, FACT_CHECK, GENERAL).
- **Insufficiency Invariance**: Evidence insufficiency is strictly never treated as a hallucination.

### 5. Verification Summary
- Deterministic side-by-side synthesis comparing MetaQA vs Web Evidence without an artificial fused percentage.
- Descriptive relationship outcomes: `AGREE`, `DISAGREE`, `BOTH_CONCERNING`, `WEB_INSUFFICIENT`, or `PARTIAL`.

### 6. Interactive Web Interface
- **React 19 & Vite UI**: Fast, responsive single-page application built with TypeScript and Tailwind CSS.
- **Truthful Status Banners**: Distinct UI indicators for **Live Mode — Local Ollama** and **Demo / Mock Mode**.
- **Clean Navigation**: Streamlined 4-page product layout:
  - **Detect** (`/`): Progressive detection dashboard.
  - **History** (`/history`): Run audit log with mutation inspection and web evidence traces.
  - **MetaQA Guide** (`/metaqa`): Educational visualizer for metamorphic testing theory and scoring tables.
  - **Settings** (`/settings`): Runtime configuration parameters.

### 7. Persistence & Research Reproducibility
- **SQLite Database**: Persistent relational storage for runs, mutation statements, verification rationales, and execution timings.
- **Automated Test Suite**: 252 backend unit tests passing with pytest.
- **Research Artifact Preservation**: Preserved 2×2 study scaffold and frozen pilot artifacts in backend test suite for offline academic evaluation.

---

## Planned Future Extensions
- **Calibrated Multi-Signal Fusion**: Principled statistical fusion models to integrate metamorphic consistency and external evidence confidence.
- **Browser Extension**: An interactive Chrome extension for on-the-fly verification of web content.
- **Expanded Multi-Model Benchmarks**: Automated evaluation over heterogeneous open-weight LLMs.
