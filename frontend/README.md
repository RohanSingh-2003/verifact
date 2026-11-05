# VeriFact Frontend Application

> **Modern Reactive User Interface Built with React 19, TypeScript, Tailwind CSS v4, and Vite 8**

The VeriFact frontend is a single-page application (SPA) providing an interactive, explainable hallucination analysis dashboard. It implements a non-blocking progressive disclosure workflow: candidate answers render within seconds, while background verification progress (MetaQA metamorphic mutations, independent peer reviews, and live web evidence retrieval) updates in real time via reactive polling.

---

## Table of Contents

- [Overview & Technology Stack](#overview--technology-stack)
- [Frontend–Backend Communication](#frontendbackend-communication)
  - [Vite Reverse Proxy](#vite-reverse-proxy)
  - [API Communication Lifecycle](#api-communication-lifecycle)
- [Directory & Component Architecture](#directory--component-architecture)
- [Key Pages & Views](#key-pages--views)
  - [1. Progressive Detection Dashboard (`/`)](#1-progressive-detection-dashboard-)
  - [2. History & Audit Log (`/history`)](#2-history--audit-log-history)
  - [3. MetaQA Educational Guide (`/metaqa`)](#3-metaqa-educational-guide-metaqa)
  - [4. Web Analysis Educational Guide (`/web-analysis`)](#4-web-analysis-educational-guide-web-analysis)
  - [5. System Settings & Diagnostics (`/settings`)](#5-system-settings--diagnostics-settings)
- [UI Components & Data Mapping](#ui-components--data-mapping)
- [State Management & Polling Hook](#state-management--polling-hook)
- [Installation & Setup](#installation--setup)
  - [Prerequisites](#prerequisites)
  - [Install Dependencies](#install-dependencies)
  - [Start Local Development Server](#start-local-development-server)
- [Production Build, Linting & Testing](#production-build-linting--testing)
- [Design System & Theming](#design-system--theming)
- [Troubleshooting & FAQ](#troubleshooting--faq)

---

## Overview & Technology Stack

The client application is built on modern web standards with zero legacy boilerplate:

- **UI Framework**: **React 19** (`^19.2.8`) with functional components and modern hooks.
- **Language**: **TypeScript** (`~6.0.2`) with strict type checking across API mappers, UI props, and state.
- **Styling**: **Tailwind CSS v4** (`^4.3.3`) powered by the official `@tailwindcss/vite` plugin.
- **Build Tool**: **Vite 8** (`^8.2.2`) with instantaneous Hot Module Replacement (HMR).
- **Client Routing**: **React Router DOM v7** (`^7.18.3`).
- **Icons**: **Lucide React** (`^1.40.0`).
- **Testing**: **Vitest** (`^5.0.3`) and Testing Library.
- **Linter**: **Oxlint** (`^1.79.0`) for fast static code analysis.

---

## Frontend–Backend Communication

### Vite Reverse Proxy
In local development, the Vite dev server (`http://localhost:5173`) proxies all requests starting with `/api` directly to the FastAPI backend (`http://127.0.0.1:8000`). Configured in `frontend/vite.config.ts`:

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

This prevents CORS errors during local development and allows client services to use standard relative paths (e.g. `fetch('/api/detect/stream')`).

### API Communication Lifecycle
1. **Initial Mount**: The app inspects provider availability and settings via `GET /api/health` and `GET /api/settings`.
2. **Submit Query**: Submitting a question dispatches `POST /api/detect/stream` with:
   ```json
   {
     "question": "Who discovered penicillin and in what year?",
     "model": "gemma4:26b"
   }
   ```
3. **Immediate Handshake**: The backend synchronously returns `{ "id": "...", "answer": "...", "status": "RUNNING" }`. The frontend renders the base answer in `AnswerCard` immediately.
4. **Reactive Polling**: The frontend hook `useVerificationPolling` polls `GET /api/runs/{id}` every 3,000 milliseconds.
5. **Progressive Rendering**: As background tasks complete, the UI progressively mounts:
   - Analysis progress indicator (`AnalysisProgress`)
   - Synonym and Antonym mutation tabs with verifier votes and penalties (`MutationTabs`)
   - Independent Multi-Model Review card with consensus metrics (`IndependentVerdictsCard`)
   - Web evidence claim cards with domain badges and source URLs (`WebEvidencePanel`)
   - Final Overall Result Card and Combined Hallucination Risk gauge once status reaches `COMPLETED`.

---

## Directory & Component Architecture

```text
frontend/
├── public/                             # Static assets & favicon
├── src/
│   ├── assets/                         # SVG logos and illustrations
│   ├── components/                     # Modular React UI components
│   │   ├── detect/                     # Detect view panels & cards
│   │   │   ├── AnswerCard.tsx          # Displays base Gemma 4:26B response
│   │   │   ├── AnalysisProgress.tsx    # Live pipeline stage progress bars
│   │   │   ├── ScoreCard.tsx           # MetaQA hallucination score gauge
│   │   │   ├── MutationTabs.tsx        # Synonym vs. Antonym mutation tables
│   │   │   ├── IndependentVerdictsCard.tsx # Multi-model peer consensus panel
│   │   │   ├── WebEvidencePanel.tsx    # Extracted claims & verified sources
│   │   │   ├── OverallResultCard.tsx   # Combined risk & executive verdict
│   │   │   └── AnswerModelSelector.tsx # Dead code (model selection is disabled)
│   │   ├── history/                    # History view components
│   │   │   ├── HistoryTable.tsx        # Paginated audit log table
│   │   │   └── HistoryFilters.tsx      # Search bar & status filters
│   │   ├── layout/                     # Application shell
│   │   │   ├── Header.tsx              # Top navigation bar & theme toggle
│   │   │   └── Footer.tsx              # Version info & GitHub link
│   │   └── ui/                         # Reusable atomic UI elements
│   │       ├── Badge.tsx               # Status & verdict badges
│   │       ├── Button.tsx              # Styled interactive buttons
│   │       ├── Card.tsx                # Container cards with border styling
│   │       └── Modal.tsx               # Accessible dialog container
│   ├── data/                           # Static documentation data & presets
│   ├── hooks/                          # Custom React hooks
│   │   └── useVerificationPolling.ts   # 3000ms polling hook for active runs
│   ├── pages/                          # Primary view routes
│   │   ├── DetectPage.tsx              # Interactive detection interface (/)
│   │   ├── HistoryPage.tsx             # Audit log of previous runs (/history)
│   │   ├── MetaQAPage.tsx              # Educational guide to MetaQA (/metaqa)
│   │   ├── WebAnalysisPage.tsx         # Educational guide to Web Evidence (/web-analysis)
│   │   └── SettingsPage.tsx            # Model provider config & theme (/settings)
│   ├── services/                       # API client and response mappers
│   │   ├── api.ts                      # Axios/Fetch HTTP requests
│   │   └── mappers.ts                  # Backend JSON to TypeScript mappers
│   ├── theme/                          # ThemeContext (Dark, Light, System)
│   ├── types/                          # Shared domain TypeScript interfaces
│   │   └── index.ts                    # Run, Mutation, Claim, Evidence types
│   ├── App.tsx                         # Router & layout shell
│   ├── main.tsx                        # DOM mount & context provider setup
│   └── index.css                       # Design tokens & Tailwind imports
├── package.json                        # Dependencies, scripts, and engine specs
├── vite.config.ts                      # Vite configuration & dev server proxy
├── tsconfig.json                       # TypeScript compiler options
└── README.md                           # Frontend developer guide (this file)
```

---

## Key Pages & Views

### 1. Progressive Detection Dashboard (`/`)
The primary interactive interface:
- **Input Bar**: User inputs factual questions with sample prompt chips.
- **AnswerCard**: Immediately displays the candidate answer generated by Gemma 4:26B.
- **IndependentVerdictsCard**: Visualizes direct answer peer reviews across Microsoft Phi-4, GLM-4.7, Qwen-2.5, and Liquid LFM-2.5, showing consensus ratios (`3/4 agreed`) and qualitative rationales.
- **MetaQA Section**: Displays the MetaQA Inconsistency Score ($H \in [0.0, 1.0]$) and tabbed tables of synonym and antonym mutations with observed verifier votes.
- **Web Evidence Section**: Displays extracted claims, domain categorization badges, and expandable source cards with relevance scores and external hyperlinks.
- **OverallResultCard**: Displays the combined executive verdict (`Likely Reliable`, `Potentially Hallucinated`, `Needs Verification`) and composite risk gauge.

### 2. History & Audit Log (`/history`)
- Paginated table of all previous detection runs stored in SQLite.
- Search by question text, filter by status (`COMPLETED`, `RUNNING`, `FAILED`).
- Inspect individual runs or trigger CSV exports.

### 3. MetaQA Educational Guide (`/metaqa`)
- Educational documentation explaining metamorphic relations, synonym and antonym perturbations, prompt blindness, and Equation 5 penalty mathematics.

### 4. Web Analysis Educational Guide (`/web-analysis`)
- Visual guide to question domain classification, authoritative domain whitelisting, topical relevance filtering, and compound claim coverage.

### 5. System Settings & Diagnostics (`/settings`)
- Health status of backend and individual LLM provider adapters.
- Dark / Light / System theme switching.
- Academic citations and project metadata.

---

## State Management & Polling Hook

VeriFact uses React's native state combined with the custom hook `useVerificationPolling`:
- **File**: `src/hooks/useVerificationPolling.ts`
- **Interval**: 3,000 milliseconds.
- **Trigger**: Starts automatically when a `run_id` is created with status `RUNNING`.
- **Termination**: Halts polling when `status === "COMPLETED"` or `status === "FAILED"`, or when the component unmounts.
- **Error Handling**: Implements exponential backoff on transient network failures.

---

## Installation & Setup

### Prerequisites
- **Node.js**: Version `20.x` or higher
- **npm**: Version `9.x` or higher

### Install Dependencies
```bash
cd frontend
npm install
```

### Start Local Development Server
```bash
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser.

---

## Production Build, Linting & Testing

```bash
# 1. Type-check and build for production
npm run build

# 2. Preview the production build locally
npm run preview

# 3. Run high-performance linter (Oxlint)
npm run lint

# 4. Run automated frontend unit tests (Vitest)
npm test
```

---

## Design System & Theming

- **Tailwind CSS v4**: Utilizes the modern `@import "tailwindcss";` directive in `src/index.css`.
- **Theme Support**: `ThemeContext` persists the user's preference (`dark`, `light`, or `system`) in `localStorage` and dynamically toggles the `dark` class on the root `<html>` element.
- **Color Tokens**:
  - Reliable / Supported: Emerald / Green (`text-emerald-500`, `bg-emerald-500/10`)
  - Hallucinated / Contradicted: Rose / Red (`text-rose-500`, `bg-rose-500/10`)
  - Needs Verification / Uncertain: Amber / Yellow (`text-amber-500`, `bg-amber-500/10`)

---

## Troubleshooting & FAQ

| Problem | Root Cause | Solution |
| :--- | :--- | :--- |
| **API requests fail with 404 / Network Error** | Backend is not running on `http://127.0.0.1:8000`. | Ensure the FastAPI backend is running via `uvicorn app.main:app --port 8000`. |
| **Polling never stops** | Backend run status never transitioned to `COMPLETED`. | Check backend terminal logs for unhandled exceptions in background tasks. |
| **Model selector is missing from the UI** | Model selection was intentionally deprecated. | Gemma 4:26B is permanently enforced by design to establish a fixed evaluation baseline. |
| **Styles appear broken or unstyled** | Tailwind v4 compilation issue. | Ensure you are running Node 20+ and have installed `@tailwindcss/vite`. Run `npm run build` to verify. |
