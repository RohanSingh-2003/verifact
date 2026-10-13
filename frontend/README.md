# VeriFact Frontend Application

Modern single-page web interface for VeriFact built with **React 19**, **TypeScript**, **Vite**, and **Tailwind CSS**.

---

## Table of Contents

- [Overview & Architecture](#overview--architecture)
- [Frontend–Backend Communication](#frontendbackend-communication)
- [Key Features & User Interface](#key-features--user-interface)
  - [1. Progressive Detection Dashboard (`/`)](#1-progressive-detection-dashboard-)
  - [2. Fixed Gemma Generator & Independent Peer Review](#2-fixed-gemma-generator--independent-peer-review)
  - [3. MetaQA Inspection Panels](#3-metaqa-inspection-panels)
  - [4. Web Evidence Source Cards](#4-web-evidence-source-cards)
  - [5. Overall VeriFact Result Card](#5-overall-verifact-result-card)
  - [6. History, Guides, & Settings](#6-history-guides--settings)
- [Setup & Installation](#setup--installation)
  - [Prerequisites](#prerequisites)
  - [Install Dependencies](#install-dependencies)
  - [Start Local Development Server](#start-local-development-server)
- [Production Build, Linting, & Testing](#production-build-linting--testing)
- [Environment Configuration](#environment-configuration)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

---

## Overview & Architecture

The frontend provides an interactive, explainable hallucination analysis interface. It is architected for **progressive disclosure**: rather than displaying a blocking loading spinner while lengthy AI evaluations run, it presents results incrementally as each background stage completes.

- **UI Framework**: React 19 with functional components and React hooks.
- **Language**: TypeScript with strict type checking.
- **Build Tool**: Vite with Hot Module Replacement (HMR).
- **Styling**: Tailwind CSS (Tailwind v4 with `@tailwindcss/vite`) and custom design tokens in `src/index.css`.
- **Icons & Routing**: `lucide-react` and `react-router-dom`.
- **Theme Support**: Seamless Dark, Light, and System theme switching via `ThemeProvider`.

---

## Frontend–Backend Communication

### Vite Reverse Proxy
In local development, the Vite dev server (`http://localhost:5173`) proxies all requests starting with `/api` directly to the FastAPI backend service (`http://127.0.0.1:8000`), configured in `frontend/vite.config.ts`:

```typescript
server: {
  port: 5173,
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
}
```

This setup ensures zero CORS friction during development and allows frontend API calls to use relative URLs (e.g., `fetch('/api/detect')`).

### Communication Lifecycle
1. **Model Readiness**: On mount, the application checks backend provider availability and settings via `GET /api/models` and `GET /api/settings`.
2. **Detection Submission**: Submitting a question dispatches `POST /api/detect` with:
   ```json
   {
     "question": "What is the capital of Australia?",
     "answer_model": "gemma"
   }
   ```
   *(Gemma 4:26B is the permanent answer-generating model; no model-selector dropdown is presented to the user).*
3. **Immediate Answer Display**: The backend responds synchronously with `{ id: "...", base_answer: "...", status: "answer_ready" }`. The frontend renders the answer immediately in `AnswerCard`.
4. **Asynchronous Polling**: The frontend begins polling `GET /api/runs/{id}` at 1-second intervals. As background workers progress, the UI updates:
   - Analysis progress bars (`AnalysisProgress`)
   - Synonym and antonym mutation tables as mutations are generated and verified across the verifier pool (`MutationTabs`)
   - Independent Multi-Model Review Card (`IndependentVerdictsCard`) displaying peer consensus, agreement ratios, qualitative rationales, and contradictory claims
   - Web evidence claims, search domains, and clean evidence cards (`WebEvidencePanel`)
   - Final Overall VeriFact Assessment and Combined Risk once status transitions to `completed` or `partial`.

---

## Key Features & User Interface

### 1. Progressive Detection Dashboard (`/`)
- **Non-blocking workflow**: Candidate AI answer renders within seconds.
- **Step-by-step progress tracking**: Independent progress indicators show real-time states for MetaQA, Multi-Model Review, and Web Evidence.
- **Side-by-side verification tabs**: Effortlessly toggle between metamorphic testing details and external web sources.

### 2. Fixed Gemma Generator & Independent Peer Review
- **Dedicated Answer Generation**: Candidate answers are generated exclusively by **Gemma 4:26B** (Ollama Cloud). The model-selection dropdown has been removed from the user interface to ensure a standardized benchmark baseline.
- **Independent Multi-Model Review Card (`IndependentVerdictsCard`)**:
  - Peer models (**Gemini 3.8 Flash**, **GLM-4.7-Flash**, **Qwen-2.5-32B**, and **Liquid/OpenRouter**) concurrently evaluate Gemma's complete answer text with full context (question, answer, claims, mutations, and web snippets).
  - **Consensus Badge**: Displays `Consensus: Correct`, `Disagreement Detected`, `Consensus: Incorrect`, `Uncertain Consensus`, or `No Reviews Available`.
  - **Agreement Metric**: Shows `X/Y agreed` across all responding peer models.
  - **Peer Reasoning Accordions**: Expandable details displaying each verifier's confidence score and qualitative explanation.
  - **Contradictory Claims Registry**: Highlights specific claims where peer verifiers disputed Gemma's answer.

### 3. MetaQA Inspection Panels
- **ScoreCard**: Visual gauge displaying the arithmetic MetaQA Hallucination Score ($H \in [0.0, 1.0]$) and categorical badge (**Reliable** vs. **Hallucinated** based on threshold $\theta = 0.5$).
- **MutationTabs**: Separate tabs for Synonym (meaning-preserving) and Antonym (meaning-reversing) mutations.
- Displays:
  - Mutated statement text
  - Verifier verdict badge (`YES`, `NO`, `NOT SURE`)
  - Expected relationship indicator
  - Verifier rationale expandable accordion.

### 4. Web Evidence Source Cards
- **Claim-Level Panels**: Lists each factual claim extracted from the answer.
- **Clean Evidence Cards**: Surfaces preprocessed 1–2 sentence evidence summaries (`evidenceSummary`) stripped of navigation noise, markdown clutter, and bracket citations.
- **Metadata**: Shows source domain tag, page title, verifier reasoning, and direct clickable external URLs.
- **Contradicted Claims Drawer**: Dedicated highlight section when contradictions are detected.

### 5. Overall VeriFact Result Card
- Synthesizes findings into a clear executive summary at the conclusion of the run:
  - **Verdict Badge**: `Likely Reliable`, `Potentially Hallucinated`, `Needs Verification`, or `Insufficient Evidence`.
  - **Combined Hallucination Risk**: Prominent numeric risk score ($0.5 \times \text{MetaQA} + 0.5 \times \text{Web Risk}$).
  - **3-Column Score Summary**: Equal-width cards for MetaQA Score, Web Evidence Consistency %, and Combined Risk.
  - **Transparent Disclaimer**: Clear explanation that the combined score is an application-level heuristic.

### 6. History, Guides, & Settings
- **History (`/history`)**: Filterable, paginated audit log of previous runs stored in the local SQLite database. Inspect questions, answers, scores, and full verification traces.
- **MetaQA Guide (`/metaqa`)**: Visual educational guide explaining metamorphic testing, synonym/antonym perturbations, the scoring contribution matrix, and thresholds.
- **Web Analysis Guide (`/web-analysis`)**: Educational guide explaining question-type routing, authoritative domain categorization, and evidence consistency scoring.
- **Settings (`/settings`)**: Theme switcher (Light, Dark, System), read-only display of configured backend AI providers, and About VeriFact citations.

---

## Setup & Installation

### Prerequisites
- **Node.js**: Version 20.0 or higher
- **npm**: Version 9.0 or higher

### Install Dependencies
```bash
cd frontend
npm install
```

### Start Local Development Server
```bash
npm run dev
```

The application will launch at **[http://localhost:5173](http://localhost:5173)**.

---

## Production Build, Linting, & Testing

```bash
# 1. Typecheck and build optimized production bundle
npm run build

# 2. Run fast linter (oxlint)
npm run lint

# 3. Run frontend unit tests (vitest)
npm test

# 4. Preview production build locally
npm run preview
```

Production assets are output to `frontend/dist/`.

---

## Environment Configuration

The frontend works out of the box with default settings. If custom routing is needed, configure `frontend/.env`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `""` (empty) | Base URL for API calls. When left empty, requests use relative `/api` paths routed through the Vite proxy. |

Template file: `frontend/.env.example`.

---

## Project Structure

```text
frontend/src/
├── components/
│   ├── detect/                        # Detection dashboard components
│   │   ├── AnswerCard.tsx             # Candidate AI answer card
│   │   ├── AnalysisProgress.tsx       # Progress steps indicator
│   │   ├── MutationTabs.tsx           # Synonym & antonym mutation inspection
│   │   ├── ScoreCard.tsx              # MetaQA score gauge & classification
│   │   ├── WebEvidencePanel.tsx       # Web claims, evidence cards, sources
│   │   └── VerificationSummaryPanel.tsx # Compact Overall Result & Combined Risk
│   ├── layout/                        # Global layout, header, navbar, footer
│   └── ui/                            # Primitives: buttons, badges, cards, modals, tooltips
├── pages/                             # Route view pages
│   ├── DetectPage.tsx                 # Core question entry & progressive analysis
│   ├── HistoryPage.tsx                # Paginated audit log of historical runs
│   ├── MetaQAPage.tsx                 # Educational guide to MetaQA
│   ├── WebAnalysisPage.tsx            # Educational guide to Web Evidence
│   └── SettingsPage.tsx               # Theme selection, active models, about
├── services/                          # Backend API communication
│   ├── api.ts                         # HTTP client functions for /api endpoints
│   └── mappers.ts                     # Schema normalization into frontend domain types
├── theme/                             # ThemeContext (Dark, Light, System)
├── types/                             # TypeScript interfaces & domain types
├── lib/                               # String utilities & formatting helpers
├── App.tsx                            # React Router configuration
├── main.tsx                           # React DOM root entry point
└── index.css                          # Design tokens, CSS variables, Tailwind styles
```

---

## Troubleshooting

- **API calls fail with `Connection Refused` or `500 Proxy Error`**:
  - The FastAPI backend service is not running. Start the backend in a separate terminal:
    ```bash
    cd backend
    uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
    ```
- **Port 5173 already in use**:
  - Vite will automatically attempt the next available port (e.g., 5174). If this happens, ensure `FRONTEND_ORIGIN` in `backend/.env` is updated to match the new port.
- **Provider status displays "Unconfigured"**:
  - The cloud provider API key has not been added to `backend/.env`. Add the corresponding key (e.g., `OLLAMA_API_KEY`, `GEMINI_API_KEY`) and restart the backend.
- **Styles not rendering properly**:
  - Ensure dependencies are installed via `npm install` and that Tailwind CSS is correctly processed via `@tailwindcss/vite`.
