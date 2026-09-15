# VeriFact v1.0.0

## Overview

VeriFact is a **research-oriented prototype** for detecting fact-conflicting hallucinations with MetaQA and for running a controlled 2×2 same-model vs cross-model verification study. It is not a production fact-checking service.

## Core Detection

Zero-resource MetaQA: generate an answer, create synonym and antonym/negation mutations, verify YES / NO / NOT SURE, average contributions, classify with threshold 0.5. Rationales do not affect the score. Ground truth is not used during detection.

## Research Experiment

2×2 design (A→A, A→B, B→A, B→B) with fixed mutation sets. Frozen artifact: `58baff20-fb86-4f43-b20e-895a086ceb6b` (pilot v1.0, n=40, **mock**). Live-LLM hypothesis: **inconclusive**.

## Evaluation

Post-detection labeling against references. Needs Review items excluded from automatic P/R/F1. Threshold sweeps reuse stored scores.

## Software Architecture

React + Vite + TypeScript UI, FastAPI backend, SQLite traces, mock or OpenAI-compatible LLM client. API keys stay on the server.

## Testing

pytest (mock LLM), ruff, frontend `tsc -b` + Vite build, GitHub Actions with `LLM_MODE=mock`.

## Documentation

README, methodology, experiment methodology, frozen results lock, discussion, architecture, demo/interview/viva notes.

## Known Limitations

No stored live 2×2. Mock lock uses placeholder model IDs. Small dataset. Mutation quality is prompt-constrained. Live APIs are stochastic. See `docs/limitations.md`.
