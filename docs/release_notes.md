# Release Notes: VeriFact v1.0.0

## Release Summary
VeriFact v1.0.0 establishes the core software implementation of the MetaQA metamorphic hallucination detection framework, featuring real local LLM inference via Ollama + Gemma 4:26b, a progressive web application architecture, and a 2×2 same-model versus cross-model experiment harness.

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
- **Background Event Loop Orchestration**: Downstream MetaQA analysis continues asynchronously in the background on the exact same run ID.
- **Incremental State Transitions**: Discrete lifecycle states (`answer_ready` → `generating_mutations` → `mutations_ready` → `verifying_mutations` → `calculating_score` → `completed`).
- **Real-Time Polling**: Frontend polls `GET /api/runs/{id}` to progressively render mutation texts, live verification badges, and final scores.

### 4. Interactive Web Interface
- **React 19 & Vite UI**: Fast, responsive single-page application built with TypeScript and Tailwind CSS.
- **Truthful Status Banners**: Distinct UI indicators for **Live Mode — Local Ollama** and **Demo / Mock Mode**.
- **Pages**: Interactive Detect, Run History with audit traces, 2×2 Research Experiments, MetaQA methodology visualizer, and Settings inspector.

### 5. Persistence & Research Scaffold
- **SQLite Database**: Persistent relational storage for runs, mutation statements, verification rationales, and execution timings.
- **2×2 Experiment Harness**: Controlled same-model vs. cross-model study runner ($A \to A, A \to B, B \to A, B \to B$) with frozen mutation set controls.
- **Automated Test Suite**: 162 backend unit tests passing with pytest.

---

## Planned Future Extensions (Not in v1.0.0)
- **External Web Evidence**: Integration with web search APIs (e.g., Tavily) to ground claims against external sources.
- **Evidence-Based Claim Verification**: Classifying factual assertions as SUPPORTED, CONTRADICTED, or INSUFFICIENT EVIDENCE.
- **Browser Extension**: An interactive Chrome extension for on-the-fly verification of web content.
