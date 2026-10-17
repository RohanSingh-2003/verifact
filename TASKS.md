# VeriFact — Project Status, QA Verification & Task Ledger

**Document Version**: 1.0.0 (Release Freeze)
**Status**: Feature-Complete & Quality-Audited
**Baseline Commit**: [`54aff3c`](https://github.com/RohanSingh-2003/verifact/commit/54aff3c)

---

## A. Completed Implementation Milestones

### 1. Core Architecture & Backend
- [x] **Decoupled Asynchronous API**: Built FastAPI backend with non-blocking async routes and background tasks (`app/api/routes_detect.py`).
- [x] **Model Registry & Cloud Clients**: Implemented `MODEL_REGISTRY` supporting:
  - Gemma 4:26B via Ollama Cloud (`gemma4:26b`) for answer generation.
  - Microsoft Phi-4 Reasoning via OpenRouter (`microsoft/phi-4-reasoning:free`) for verifier pool.
  - GLM-4.7-Flash via Cloudflare Workers AI (`@cf/zai-org/glm-4.7-flash`) for verifier pool.
  - Qwen-2.5-32B via Groq (`qwen-2.5-32b`) for verifier pool.
  - Liquid LFM-2.5 via OpenRouter (`liquid/lfm-2.5-2.6b:free`) for verifier pool.
- [x] **MetaQA Metamorphic Engine**: Implemented synonym, antonym, and negation perturbation generators (`metaqa/mutation.py`), multi-model verification dispatcher (`metaqa/multi_verifier.py`), and Yang et al. Equation 5 deterministic scoring matrix (`metaqa/scoring.py`).
- [x] **Direct-Answer Multi-Model Review**: Built concurrent cross-model evaluator (`services/independent_verifiers.py`) that collects independent judgments, confidence ratings, and contradiction flags without allowing Gemma to review itself.
- [x] **Web Evidence Retrieval Engine**: Built atomic claim extractor (`web_evidence/claim_extractor.py`), multi-pass Tavily search client (`web_evidence/pipeline.py`), 6-tier domain authority classifier (`web_evidence/source_tiering.py`), relevance filtering ($\ge 0.20$), and evidence scoring.
- [x] **SQLite Persistence**: Modeled relational tables (`runs`, `mutations`, `model_verdicts`, `evaluation_items`) in `database/models.py` with transactional integrity.

### 2. Frontend User Interface
- [x] **SPA Routing**: Configured React Router v7 routes (`/`, `/history`, `/metaqa`, `/web-analysis`, `/settings`) with `Layout` shell and `ScrollToTop`.
- [x] **Detect Studio (`/`)**: Created interactive question input with client-side validation, live progress stepper, answer latency display, educational accordions (`MethodOverview.tsx`), score cards, independent verdict badges, and web evidence breakdown.
- [x] **MetaQA Theory View (`/metaqa`)**: Designed accessible stacked fractions for Yang et al. Equation 5, interactive 4-step workflow diagram, plain-English bullet explanations, and threshold documentation ($\theta = 0.50$).
- [x] **Web Analysis Theory View (`/web-analysis`)**: Created prominent human-readable consistency formula banner, 4-card contribution grid, 6-tier domain authority breakdown cards, and research caveat documentation.
- [x] **Settings View (`/settings`)**: Redesigned clean layout **without decorative icons**, displaying model configuration status badges, theme toggle (Light / Dark / System), SQLite connectivity indicator, and research links.
- [x] **History View (`/history`)**: Built persisted run history explorer displaying timestamps, questions, component scores, and run detail expansion.
- [x] **Theme System**: Implemented HSL-tailored desaturated design system in `index.css` supporting light and dark themes with WCAG AA compliance.

### 3. Documentation & Audits
- [x] Synchronized `README.md`, `backend/README.md`, `frontend/README.md`, and `analysis/README.md`.
- [x] Formalized safety guardrails and agent constraints in `AGENTS.md`.
- [x] Completed comprehensive documentation pack (`PRD.md`, `ARCHITECTURE.md`, `RULES.md`, `DESIGN.md`, `TASKS.md`, `MEMORY.md`).

---

## B. Verified Quality Checks (Latest Final QA Results)

The following verification metrics were independently executed and verified during the final quality assurance audit:

| Verification Target | Command Executed | Reported Result | Notes |
|---|---|---|---|
| **Backend Unit & Integration Tests** | `.\.venv\Scripts\pytest -q` | **491 passed, 2 skipped, 0 failures** | Executed in 22.53s across 34 test files. 2 tests skipped due to optional live cloud token requirements. |
| **Frontend Unit Tests** | `npm test` | **26 passed, 0 failures** | Executed in 1.48s across 4 test suites (`format.test.ts`, `ScrollToTop.test.tsx`, `QuestionInput.test.tsx`, `CollapsibleModelVerdicts.test.tsx`). |
| **Frontend Linter** | `npm run lint` (`oxlint`) | **0 errors, 2 warnings** | 42 files inspected in 24ms. Warnings relate to standard React Compiler suggestions in `ThemeProvider.tsx`. |
| **TypeScript Typecheck & Build** | `npm run build` (`tsc -b && vite build`) | **Compiled successfully in 384ms** | Production bundle generated: `index.html` (1.88 kB), CSS (50.28 kB), JS (439.27 kB). |
| **Git Diff Cleanliness** | `git diff --check` | **Clean (Exit 0)** | Zero trailing whitespaces, zero formatting anomalies. |
| **Live API Audit Script** | `test_e2e_live_audit.py` | **100% Passed** | Verified `/api/health`, `/api/settings`, `/api/models`, `/api/runs`, empty question validation (422), and missing ID lookup (404). |

---

## C. Known Limitations & Configuration Dependencies

1. **Cloud Provider API Keys**:
   - Running live evaluations requires valid external API keys configured in `backend/.env` (`OLLAMA_API_KEY`, `OPENROUTER_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `GROQ_API_KEY`, `TAVILY_API_KEY`).
   - If keys are missing, the system gracefully operates in `mock` mode (`LLM_MODE=mock`) using deterministic mock fixtures.
2. **External Rate Limits**:
   - Free or shared cloud API tiers (OpenRouter free models, Cloudflare rate limits) can experience transient throttling. VeriFact captures these as `FAILED` verdicts with error explanations rather than crashing.
3. **Database Concurrency**:
   - Uses SQLite (`db/verifact.db`). Highly reliable for single-server research prototypes and local demonstration, but not designed for distributed multi-region horizontal scaling.
4. **Search Engine Horizon**:
   - Tavily search results depend on index coverage; highly obscure, private, or real-time breaking events (past hour) may produce `INSUFFICIENT_EVIDENCE` or `NOT_ASSESSED_NO_RELEVANT_SOURCE`.
5. **Non-Probability Scores**:
   - MetaQA and Web Evidence consistency scores are normalized empirical heuristic metrics in $[0.0, 1.0]$; they are not calibrated Bayesian probabilities of factual truth.

---

## D. Future Possibilities (Optional Post-Freeze Roadmap)

*The following items are optional prospective ideas and are not required for current release readiness:*

- [ ] **PostgreSQL Storage Adapter**: Provide an optional enterprise database backend for high-concurrency multi-user deployments.
- [ ] **Streaming Answer Generation**: Stream Gemma's initial answer generation via Server-Sent Events (SSE) before triggering background verification tasks.
- [ ] **Claim Highlight Annotations**: Visually highlight specific spans within the answer text that correspond directly to extracted claims.
- [ ] **Automated PDF Export**: Generate one-click executive audit reports in PDF format summarizing the dual-pipeline findings and source citations.
- [ ] **Custom Domain Whitelisting**: Allow enterprise users to configure custom domain authority rankings tailored to proprietary or internal knowledge bases.
