# VeriFact frontend

React UI for VeriFact. Talks to the FastAPI backend at `http://localhost:8000` through the Vite `/api` proxy.

```bash
cd frontend
npm install
npm run dev
```

Optional `.env`:

```
VITE_API_BASE_URL=
```

Leave `VITE_API_BASE_URL` empty when using the Vite proxy. Set it to `http://localhost:8000` only if you want the browser to call FastAPI directly (CORS must allow the frontend origin).
