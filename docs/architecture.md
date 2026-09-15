# Architecture

VeriFact is a small research application: a React client, a FastAPI MetaQA service, SQLite traces, and an experiment/evaluation layer. The detector path is zero-resource. Ground truth is applied only after detection.

## Frontend

**React + Vite + TypeScript + Tailwind.**

Routes:

- Detect — question in, MetaQA trace out
- History — stored detection runs
- Experiments — 2×2 dashboard bound to API results (DEMO banner when `llm_mode=mock`)
- MetaQA — method explanation
- Settings — non-secret runtime configuration

The UI does not hold API keys. Detection scores and experiment numbers come from the backend, not from hardcoded findings.

## Backend

**Python + FastAPI + Pydantic.**

The API exposes detection, run history, evaluations, experiments, health, and settings. An OpenAI-compatible LLM client (or a deterministic mock client) implements the generator and verifier roles. Prompts forbid tools, browsing, and retrieval.

## Database

**SQLite** (default `backend/data/verifact.db`).

Stores detection runs, experiment rows (answers, mutations, verifications, scores), and evaluation runs. Experiment exports also write files under `experiments/raw|processed|results/`.

## LLM abstraction

Two logical roles share the same client interface:

- **Generator** — base answer and mutation JSON
- **Verifier** — YES / NO / NOT SURE plus a rationale

Live mode uses `OpenAICompatibleClient`. Mock mode uses `MockLLMClient` and labels outputs DEMO / MOCK DATA.

## Core detection pipeline

```
React UI
  → FastAPI
  → Answer generator
  → Mutation generator
  → Verifier
  → MetaQA score engine
  → Threshold classifier
  → SQLite
```

Purpose of each stage:

| Stage | Purpose |
| --- | --- |
| UI | Collect a question and display explainable results |
| FastAPI | Orchestrate the detector without putting secrets in the browser |
| Answer generator | Produce one candidate answer |
| Mutation generator | Produce synonym and antonym restatements |
| Verifier | Label each restatement YES / NO / NOT SURE |
| Score engine | Apply the MetaQA contribution table and average |
| Classifier | Compare the score with threshold θ |
| SQLite | Persist an auditable trace |

This path does not query Google, Wikipedia, RAG, embeddings, vector databases, or external fact-checking APIs.

## Experiment pipeline

```
Dataset
  → Generator A / B
  → Fixed mutation sets
  → Verifier A / B
  → 2×2 conditions
  → Metrics
  → Statistics
  → Charts
  → Research results
```

The experiment service generates each (question, generator) answer and mutation set once, then verifies with both verifiers. Integrity checks compare mutation IDs and texts across paired conditions. Statistics (Wilcoxon, CIs, flips, category splits) run on stored scores.

## Evaluation / ground-truth layer

Evaluation loads a labeled dataset, runs detection first, then matches the generated answer to a reference or curated label. Needs Review items stay in the raw table and are dropped from automatic P/R/F1. Threshold sweeps reuse stored scores.

```
Detection complete
  → attach reference / label
  → confusion matrix and F1
```

## Diagram

![VeriFact system architecture](architecture.png)
