# VeriFact Browser QA Report

## Environment

- **Frontend**: `http://localhost:5173/` (Vite 8.2.2 + React 19 + Tailwind CSS)
- **Backend**: `http://127.0.0.1:8000/` (FastAPI + Uvicorn + SQLite)
- **Mode**: `mock` (`LLM_MODE=mock`, deterministic question-aware MockLLMClient)
- **Browser**: Windows Default Web Browser (Microsoft Edge / Google Chrome)

---

## Test 1 — Health Check

**PASS**

- Endpoint: `GET /api/health`
- Response: `{"status": "ok", "llm_mode": "mock"}`
- Verified directly and through the Vite reverse proxy at `http://localhost:5173/api/health`.

---

## Test 2 — API Connectivity

**PASS**

- Vite proxy correctly relays `/api/*` traffic from `http://localhost:5173` to `http://127.0.0.1:8000`.
- CORS middleware in FastAPI allows origins `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:5174`, and `http://127.0.0.1:5174`.

---

## Test 3 — France Question

**PASS**

- Question: `"What is the capital of France?"`
- Answer: `"Paris is the capital of France."`
- Mutations: 10 total (5 synonyms, 5 antonyms) dynamically synthesized from Paris.
- Hallucination Score: `0.00`
- Classification: `Reliable`
- Status: Correctly rendered and persisted to the database.

---

## Test 4 — Newton Question

**PASS**

- Question: `"Who formulated the three laws of motion?"`
- Answer: `"Isaac Newton formulated the three laws of motion."`
- Mutations: 10 total referencing Isaac Newton and laws of motion.
- Hallucination Score: `0.00`
- Classification: `Reliable`
- Status: Correctly classified as Reliable with all synonyms YES (contribution 0.0) and antonyms NO (contribution 0.0).

---

## Test 5 — Hamlet Question

**PASS**

- Question: `"Who wrote Hamlet?"`
- Answer: `"William Shakespeare wrote Hamlet."`
- Mutations: 10 total referencing William Shakespeare.
- Hallucination Score: `0.00`
- Classification: `Reliable`
- Status: Distinct from all other runs.

---

## Test 6 — Math Question

**PASS**

- Question: `"What is 2 + 2?"`
- Answer: `"2 + 2 equals 4."`
- Mutations: 10 total referencing 4.
- Hallucination Score: `0.00`
- Classification: `Reliable`
- Status: Fully distinct arithmetic factual answer.

---

## Test 7 — History

**PASS**

- Route: `/history` (`GET /api/runs?limit=50&offset=0`)
- Verified: All runs are stored independently with unique UUIDs (`run_id`).
- Verified: Opening individual runs loads question, answer, mutations, verdicts, score, and classification belonging strictly to that run without cross-contamination.

---

## Test 8 — Experiments

**PASS**

- Route: `/experiments` (`GET /api/experiments/latest`, `GET /api/evaluations`)
- Displays: 2×2 generator/verifier matrix, statistical metrics, Wilcoxon and paired t-test results, flip rates, and category analysis from stored experiment data.
- Frozen research results preserved without modification.

---

## Test 9 — MetaQA Mutation Analysis

**PASS**

- Evaluated across synonym and antonym sets:
  - Synonym contribution: `YES=0.0`, `NO=1.0`, `NOT SURE=0.5`
  - Antonym contribution: `YES=1.0`, `NO=0.0`, `NOT SURE=0.5`
  - Score = arithmetic mean of all contributions.
  - Thresholding: `score >= threshold` → `Hallucinated`, `score < threshold` → `Reliable`.
- Table on Detect page displays:
  - Mutation text
  - Mutation type (Synonym / Antonym)
  - Expected verdict
  - Actual verdict
  - Contribution score

---

## Test 10 — Mock Hallucination Scenario

**PASS**

- Controlled Mock Scenario:
  - Question: `"What is the capital of Australia?"`
  - Generated Answer: `"Sydney is the capital of Australia."`
  - Scenarios by question maps Australia to the `"hallucinated"` verifier pattern (Synonyms → `NO`, Antonyms → `YES`).
  - Contributions: 1.0 for all 10 mutations.
  - Hallucination Score: `1.0`
  - Threshold: `0.5`
  - Classification: **`Hallucinated`**
- Pipeline integrity: Verified that the classification is produced strictly through metamorphic verifier contributions, without any hardcoded bypass logic.

---

## Test 11 — Error Handling

**PASS**

1. **Empty Question**: Client rejects whitespace-only submission with immediate inline message `"Enter a factual question before running analysis."` Backend validates with 422 Bad Request.
2. **Long Question (>2000 chars)**: Backend rejects with HTTP 422 (`"String should have at most 2000 characters"`), parsed and displayed gracefully by `readApiError`.
3. **Backend Unavailable / Network Error**: Surfaces clear error banner without white-screen or crash.
4. **Repeated Clicks**: Submit button is disabled with loading spinner while request is in flight.

---

## Test 12 — Responsive UI

**PASS**

- **Desktop (>= 1024px)**: Full sidebar navigation with 220px fixed rail.
- **Laptop / Tablet (768px - 1023px)**: Compact icon-only sidebar navigation (72px rail).
- **Mobile (< 768px)**: Sticky top header + fixed bottom navigation bar with safe-area padding.
- No horizontal overflow, cards wrap cleanly, and tables scroll with horizontal overflow containers.

---

## Console Errors

- No uncaught JavaScript exceptions or React render errors.
- Clean application startup and navigation.

---

## Backend Errors

- No unhandled exceptions or stack traces.
- All endpoints responded with expected HTTP status codes (200 OK for operational endpoints, 422 for intentional invalid validation tests).

---

## Bugs Found

1. **"Failed to fetch" Root Cause**:
   - Backend uvicorn server was not started or had stopped.
   - Vite proxy in `vite.config.ts` was targeted to `http://localhost:8000`, which on Windows Node.js resolves to IPv6 `::1:8000` rather than IPv4 `127.0.0.1:8000`, causing `ECONNREFUSED`.
   - FastAPI CORS allowed origins only included `settings.frontend_origin` without development fallbacks (`127.0.0.1:5173`, `localhost:5174`).
2. **"Sydney is the capital of Australia" Leak**:
   - `MockLLMClient.complete_text()` previously returned a single constant `ORIGINAL` regardless of user question.
   - `DEFAULT_MUTATIONS` previously hardcoded `Sydney is the capital of Australia.` for all mutation generations.
3. **Missing Controlled Hallucination Fixture in Mock Mode**:
   - Mock mode lacked default `scenarios_by_question` wiring for testing the `Hallucinated` outcome in the live application.

---

## Bugs Fixed

1. Updated `frontend/vite.config.ts`:
   - Configured proxy target to `http://127.0.0.1:8000`.
   - Explicitly configured default port `5173`.
2. Updated `backend/app/main.py`:
   - Broadened CORS allowed origins to include both `localhost` and `127.0.0.1` on ports `5173` and `5174`.
   - Allowed methods and headers wildcarded for development flexibility.
3. Updated `backend/app/api/deps.py`:
   - Configured `MockLLMClient` with `scenarios_by_question` mapping `"What is the capital of Australia?"` to `"hallucinated"`, enabling end-to-end verification of the `Hallucinated` classification through the MetaQA pipeline.
4. Verified and reinforced `MockLLMClient` question-aware answers and dynamic mutation synthesis in `backend/app/llm/mock.py`.

---

## Regression Tests Added

- `test_question_is_passed_to_generator`
- `test_mutations_use_current_base_answer`
- `test_mock_generator_is_deterministic`
- `test_different_questions_produce_different_mock_answers`
- `test_unknown_question_gets_mock_prefix`
- `test_hallucinated_answer_is_flagged_hallucinated`
- `test_reliable_answer_is_flagged_reliable`
- `test_hallucinated_and_reliable_differ_for_same_question`
- `test_api_different_questions_produce_different_answers`
- `test_api_response_question_matches_submitted`
- `test_api_new_detection_does_not_reuse_previous_run`
- `test_api_mutations_reference_actual_answer`
- `test_api_frontend_displays_correct_run_from_history`

---

## Final Status

**WORKING**
