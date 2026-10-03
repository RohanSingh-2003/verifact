# VeriFact Frontend

Modern single-page web interface for VeriFact built with **React 19**, **TypeScript**, **Vite**, and **Tailwind CSS**.

The frontend communicates with the FastAPI backend service via Vite's local reverse proxy at `/api` (`http://127.0.0.1:8000`).

---

## Key Features

### 1. Progressive Detection Interface (`/`)
Renders the verification workflow incrementally as background stages complete:
- **Immediate AI Answer**: Displays the candidate answer from the generator model as soon as it is generated (`status: answer_ready`).
- **Concurrent Progress Indicators**: Shows real-time progress steps for both the **MetaQA** and **Web Evidence** background pipelines running in parallel.
- **Compact VeriFact Result Card**: A streamlined summary card at the conclusion of the run:
  - **Verdict Badge**: Prominent final assessment (`Likely Reliable`, `Potentially Hallucinated`, `Needs Verification`, or `Insufficient Evidence`).
  - **Combined Hallucination Risk**: Prominently displayed numerical risk signal ($0.5 \times \text{MetaQA} + 0.5 \times \text{Web Risk}$).
  - **3-Column Score Summary**: Equal-width compact columns for MetaQA Score, Web Evidence Consistency %, and Combined Risk.
  - **Short Explanation & Disclaimer**: Direct, scannable summary with transparent application-level disclosure.
- **MetaQA Inspection**: View synonym and antonym mutations alongside independent verifier verdicts (`YES`, `NO`, `NOT SURE`) and the mathematical hallucination score.
- **Web Evidence Inspection**: View extracted claims, source strategy tags, and **clean claim-relevant evidence cards** showing domain, title, extracted evidence sentences, verifier rationale, and direct source links.
- **Contradicted Claims Drawer**: Dedicated highlight section when contradictions are detected.

### 2. Run History (`/history`)
- Paginated, filterable table of past detection runs stored in the local SQLite database.
- Inspect full question prompts, candidate answers, mutation tables, and source evidence.

### 3. Research Guides
- **MetaQA Guide (`/metaqa`)**: Visual guide explaining metamorphic relations, synonym/antonym perturbations, the arithmetic contribution matrix, and decision thresholds.
- **Web Analysis Guide (`/web-analysis`)**: Visual guide explaining question-type routing, authoritative domain categorization, and evidence consistency scoring.

### 4. Simplified Settings (`/settings`)
- **Appearance**: One-click switching between **Light**, **Dark**, and **System** themes with persistent local storage.
- **AI Configuration**: Read-only display of currently active models and providers (e.g., Ollama / Gemma 4:26B, Google Gemini 3.8 Flash, Tavily Search).
- **About VeriFact**: Overview of the two verification approaches, research paper citations, and system versioning.

---

## User Interface Pages & Routes

| Path | Component | Description |
| :--- | :--- | :--- |
| `/` | `DetectPage` | Interactive question entry and progressive dual-pipeline detection results. |
| `/history` | `HistoryPage` | Paginated audit log of previous verification runs. |
| `/metaqa` | `MetaQAPage` | Educational guide explaining MetaQA metamorphic testing. |
| `/web-analysis` | `WebAnalysisPage` | Educational guide explaining Web Evidence analysis. |
| `/settings` | `SettingsPage` | User preferences: theme selection, active model overview, and about card. |

---

## Directory Organization

```text
frontend/src/
├── components/
│   ├── detect/             # Detect dashboard components:
│   │   ├── AnswerCard.tsx                 # Base AI answer presentation
│   │   ├── AnalysisProgress.tsx           # Step-by-step pipeline progress bars
│   │   ├── MutationTabs.tsx               # Synonym and antonym mutation tables
│   │   ├── ScoreCard.tsx                  # MetaQA score and gauge display
│   │   ├── WebEvidencePanel.tsx           # Web evidence results and source cards
│   │   └── VerificationSummaryPanel.tsx   # Compact Overall VeriFact Result card
│   ├── layout/             # Global layout, header, navigation, and footer
│   └── ui/                 # Reusable UI primitives: badges, buttons, cards, modals, tooltips
├── pages/                  # Top-level view routes (Detect, History, MetaQA, WebAnalysis, Settings)
├── services/               # Backend API communication:
│   ├── api.ts              # HTTP client functions for /api endpoints
│   └── mappers.ts          # Normalization of backend schemas into frontend types
├── theme/                  # ThemeProvider and dark/light mode context
├── types/                  # TypeScript interfaces and enum definitions
├── lib/                    # Formatting helpers and utility functions
├── App.tsx                 # React Router application entry point
├── main.tsx                # React DOM root initialization
└── index.css               # Design tokens, CSS variables, and Tailwind utilities
```

---

## Setup & Running

```bash
cd frontend

# Install Node dependencies
npm install

# Start local development server with HMR
npm run dev
```

The application will be accessible at **[http://localhost:5173](http://localhost:5173)**.

---

## Production Build & Linting

```bash
# Typecheck and build optimized production bundle
npm run build

# Run linter
npm run lint
```

The production output is generated in `frontend/dist/`.

---

## Security Best Practices

- **Zero Client-Side Secrets**: All API keys (`GEMINI_API_KEY`, `TAVILY_API_KEY`) are managed strictly on the FastAPI backend.
- **Proxy Configuration**: All API requests flow through Vite's local `/api` reverse proxy in development and the production web server in deployment.
