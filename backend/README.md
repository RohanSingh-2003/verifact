# VeriFact backend

VeriFact implements the MetaQA metamorphic hallucination-detection methodology. The core detector does not use external retrieval or fact databases.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `OPENAI_API_KEY`. `OPENAI_BASE_URL` can point at any OpenAI-compatible provider.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Provider API key. Never sent to the React app. |
| `OPENAI_BASE_URL` | Chat completions base URL. |
| `GENERATOR_MODEL` | Model used for answers and mutations. |
| `VERIFIER_MODEL` | Model used for YES / NO / NOT SURE checks. |
| `ALLOWED_MODELS` | Comma-separated allow-list. |
| `SYNONYM_COUNT` / `ANTONYM_COUNT` | Mutation counts. Default 5 / 5. |
| `THRESHOLD` | Hallucination threshold θ. Default 0.5. |
| `VERIFY_CONCURRENCY` | Max parallel verifier calls. |
| `FRONTEND_ORIGIN` | Allowed CORS origin. Must not be `*`. |
| `DATABASE_URL` | SQLAlchemy URL. Default SQLite. |
| `LLM_MODE` | `mock` (dev) or `live`. Mock results are labeled DEMO DATA. |
| `MOCK_SCENARIO` | Default mock verifier pattern for Detect. |

## Start FastAPI

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/api/health`

## API

- `POST /api/detect` — run MetaQA on one question and persist the trace
- `GET /api/runs` — paginated history
- `GET /api/runs/{run_id}` — full stored trace
- `POST /api/evaluations/run` — evaluate a labeled dataset (pilot by default)
- `GET /api/evaluations` — previous evaluation runs
- `GET /api/evaluations/{id}` — metrics, confusion matrix, threshold sweep, per-question results
- `GET /api/evaluations/{id}/export` — CSV export
- `POST /api/experiments/run` — run the 2×2 experiment (live mode requires `confirm_live_run` above the unconfirmed question cap)
- `GET /api/experiments/{experiment_id}`
- `GET /api/experiments/latest`
- `GET /api/health`

## MetaQA pipeline

1. Generate a concise base answer.
2. Create synonym (meaning-preserving) and antonym (meaning-reversing) mutations.
3. Verify each mutated statement independently. The verifier is not told the mutation type or expected label.
4. Score contributions:
   - Synonym: YES=0, NO=1, NOT SURE=0.5
   - Antonym: YES=1, NO=0, NOT SURE=0.5
5. Hallucination score = mean(contributions). Classify as Hallucinated if score ≥ θ, else Reliable.

Verifier rationales are stored for explanation only and do not affect the score.

## Evaluation

Ground truth is applied **after** MetaQA detection. Reference answers are never passed to answer generation, mutation generation, the verifier, or scoring.

Positive class = Hallucinated.

| | Predicted Reliable | Predicted Hallucinated |
| --- | --- | --- |
| Actual Reliable | TN | FP |
| Actual Hallucinated | FN | TP |

Ambiguous items are marked Needs Review and excluded from P/R/F1 until resolved.

Pilot dataset: `backend/data/datasets/pilot.json` (40 curated questions, not TruthfulQA). Add local CSV/JSON files in that folder. TruthfulQA is supported as a file interface only and is not bundled.

Threshold sweeps re-classify saved scores; they do not re-run the LLM.

## Tests

```bash
cd backend
pytest
```

Tests mock the LLM client. They never call a real provider.
