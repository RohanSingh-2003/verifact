# Resume bullets

Frozen 2×2 is mock. Do not cite live-model accuracy.

### Research-focused

- Implemented MetaQA as a reference-free detector and a 2×2 same-model vs cross-model verification study with frozen mutation sets and Wilcoxon tests (α = 0.05).
- On a 40-question pilot, the locked **mock** run showed scores tracking verifier identity (0 vs 1); the live-LLM hypothesis remains inconclusive after calibration.
- Isolated evaluation from detection: ground truth is applied only after scoring; Needs Review items are excluded from automatic P/R/F1.

### Software-engineering-focused

- Built VeriFact v1.0.0: React/TypeScript/Vite UI, FastAPI, SQLite traces, Ollama / OpenAI-compatible / mock LLM clients, pytest + ruff + frontend build CI.
- Shipped progressive Detect (answer first, then mutations / verdicts / score on one `run_id`) with explainable mutation analysis and a research dashboard bound to stored experiment APIs.
- Added live-run cost gates, resume-safe experiment cells, and CSV/config exports under `experiments/`.

### AI/ML-focused

- Encoded the MetaQA contribution table (synonym YES=0/NO=1; antonym YES=1/NO=0; NOT SURE=0.5) with threshold classification at 0.5.
- Designed a controlled LLM experiment: one generator answer and mutation set per item, two verifiers, integrity checks on mutation IDs and texts.
- Reported paired self-verification score differences, classification flips, and threshold sweeps on stored scores without extra LLM calls.
