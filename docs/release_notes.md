# Release Notes: VeriFact v1.0.0

## Release Summary
VeriFact v1.0.0 establishes the production-grade software implementation of the MetaQA metamorphic hallucination detection framework extended with direct-answer Multi-Model Peer Review and an independent Web Evidence verification layer. It features cloud LLM inference via the official Ollama Cloud API (`https://ollama.com/api`) for Gemma 4:26B alongside a diverse multi-model verifier pool (Google Gemini, Cloudflare Workers AI, Groq, OpenRouter), progressive SSE streaming, and a deterministic side-by-side Verification Summary.

---

## Completed Milestones & Implemented Features

### 1. Core MetaQA Metamorphic Engine
- **Atomic Claim Extraction**: Automated extraction of core factual claims from generated answers, with fallback to deterministic sentence segmentation.
- **Bilateral Mutation Generation**: Meaning-preserving (synonym) and meaning-reversing (antonym) transformations with heuristic sentence gates (rejecting fragments, questions, prefixes, duplicates, and no-ops).
- **Independent Verification**: Isolated verification prompting without leaking mutation categories, expected outcomes, or ground-truth references.
- **Robust Verdict Parsing**: Safe parsing of `YES`, `NO`, and `NOT SURE`, with malformed outputs defaulting gracefully to `NOT SURE`.
- **Deterministic Scoring**: Arithmetic mean of individual contributions mapped strictly to a 0.0–1.0 score and a calibrated threshold ($\theta = 0.5$) for **Reliable** versus **Hallucinated** classification.

### 2. Cloud LLM Integration (Ollama Cloud API + Gemma 4:26B)
- **Ollama Cloud API Provider**: Native cloud integration via HTTPS `/api/chat` with authentication against `https://ollama.com/api`. No local Ollama daemon or local GPU hardware is required.
- **Gemma 4:26B Dedicated Role**: Cloud-hosted Gemma 4:26B acts as the dedicated answer generator and mutation generator.
- **Reasoning Loop Suppression (`think: false`)**: Native suppression of internal reasoning traces to ensure deterministic, token-budgeted JSON outputs.
- **Multi-Model Verifier Pool**: Dynamic support for Google Gemini, Cloudflare Workers AI, Groq, and OpenRouter for cross-model verification.

### 3. Progressive Detection Workflow
- **Concurrent Three-Branch Verification**: After answer delivery, MetaQA, Multi-Model Peer Review, and Web Evidence run concurrently via `asyncio.gather` with full error isolation. Any branch may fail or be absent without blocking the others or hiding the generated answer.
- **Progressive Polling via REST**: Real-time progress updates are monitored by client polling on `GET /api/runs/{id}` following immediate `POST /api/detect` background task dispatch, updating the UI as mutation checks and evidence snippets complete.
- **Lifecycle Statuses**: Granular execution states (`running` | `completed` | `partial` | `failed`) with branch-level status tracking.

### 4. Direct-Answer Multi-Model Peer Review
- **Unconditioned Peer Review**: Evaluates the candidate answer directly by external verifiers without mutation context.
- **Multi-Model Consensus**: Tracks individual verdicts (`YES`, `NO`, `UNCERTAIN`) and aggregate consensus across the active verifier pool.

### 5. Targeted Web Evidence Pipeline
- **Question-Type Routing**: Rule-based classifier selects domain strategies (science, government, current events, statistics, technology, medicine, general facts, academic research).
- **Source Strategies**: Preferred domain categories and freshness hints for Tavily Search; automatically broadens when preferred results are insufficient.
- **Claim Extraction & Verification**: Strict snippet-only verification labeled `SUPPORTED`, `CONTRADICTED`, or `INSUFFICIENT_EVIDENCE`.
- **Source Metadata**: Tags sources with institutional categories (OFFICIAL, ACADEMIC, GOVERNMENT, NEWS, REFERENCE, FACT_CHECK, GENERAL).
- **Insufficiency Invariance**: Evidence insufficiency is strictly never treated as a hallucination.

### 6. Verification Summary & Heuristic Risk Assessment
- Deterministic side-by-side synthesis presenting MetaQA Hallucination Score, Web Consistency Score, and Multi-Model Verdicts without an artificial fused percentage.
- Descriptive relationship outcomes: `AGREE`, `DISAGREE`, `BOTH_CONCERNING`, `WEB_INSUFFICIENT`, or `PARTIAL`.
- Heuristic Combined Risk assessment card for rapid visual evaluation.

### 7. Interactive Web Interface
- **React 19 & Vite UI**: Fast, responsive single-page application built with TypeScript and Tailwind CSS.
- **Truthful Status Banners**: Distinct UI indicators for **Live Mode — Cloud API** and **Demo / Mock Mode**.
- **Streamlined 5-Page Product Layout**:
  - **Detect** (`/`): Progressive detection dashboard with real-time SSE streaming.
  - **History** (`/history`): Run audit log with mutation inspection and web evidence traces.
  - **MetaQA Guide** (`/metaqa`): Educational visualizer for metamorphic testing theory and scoring tables.
  - **Web Analysis** (`/web-analysis`): Deep-dive into web evidence queries, domains, and snippet grounding.
  - **Settings** (`/settings`): Runtime configuration, provider selection, and API credentials.

### 8. Persistence & Historical Research Archive
- **SQLite Database**: Relational storage for runs, mutation statements, verification rationales, and execution timings.
- **Comprehensive Test Suite**: 458 backend test items collected at the time of the audit (`pytest backend/tests/`).
- **Preserved Historical Research**: The retired 2×2 offline experiment runner and endpoints have been removed from the active application; historical mock run `58baff20-fb86-4f43-b20e-895a086ceb6b` is preserved as an immutable archive under `experiments/results/` for reproducible academic inspection.

---

## Planned Future Extensions
- **Calibrated Multi-Signal Fusion**: Principled statistical fusion models to integrate metamorphic consistency and external evidence confidence.
- **Browser Extension**: An interactive Chrome extension for on-the-fly verification of web content.
- **Expanded Multi-Model Benchmarks**: Automated evaluation over heterogeneous open-weight LLMs.
