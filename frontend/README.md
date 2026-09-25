# VeriFact Frontend

Modern single-page web interface for VeriFact built with **React 19**, **TypeScript**, **Vite**, and **Tailwind CSS**.

Communicates with the FastAPI backend at `http://localhost:8000` through Vite's local `/api` reverse proxy.

---

## Key Features

- **Progressive Detect Dashboard**: Renders results incrementally as they become available on a single run:
  1. **AI Answer**: Rendered immediately upon generation (`status: answer_ready`).
  2. **Generated Mutations**: Displayed as soon as core claims and mutations are ready (`status: mutations_ready`).
  3. **Verification Verdicts**: Live status badges (`YES`, `NO`, `NOT SURE`) stream into the table in real time (`status: verifying_mutations`).
  4. **Score & Classification**: Displays final aggregate score and **Reliable** / **Hallucinated** badge upon completion (`status: completed`).
- **Truthful Status Banners**:
  - Displays **Live Mode — Local Ollama · Model: gemma4:26b** when running against local Ollama.
  - Displays **Demo / Mock Mode** when running with synthetic test fixtures.
- **Pages**:
  - `DetectPage`: Main detection interface with progressive polling on `GET /api/runs/{id}`.
  - `ExperimentsPage`: 2×2 research matrix visualizer with export options (CSV/JSON).
  - `HistoryPage`: Paginated run history with full metamorphic mutation inspection.
  - `MetaQAPage`: Educational visualizer explaining the MetaQA contribution matrix.
  - `SettingsPage`: Public runtime configuration inspector.

---

## Setup & Running

```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

Open your browser at **[http://localhost:5173](http://localhost:5173)**.

---

## Production Build

```bash
# Typecheck and build production bundle
npm run build
```

The production output will be generated in `frontend/dist/`.

---

## Environment Configuration

By default, Vite proxies all `/api` requests to `http://localhost:8000`. If you need to override the backend address, create an optional `.env` file:

```env
VITE_API_BASE_URL=
```

*(Leave `VITE_API_BASE_URL` empty to use the built-in Vite proxy. Never put backend API keys or secrets in the frontend.)*
