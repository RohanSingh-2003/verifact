# Application Screenshots Guide

> **Standardized Screenshots Registry and Capture Guide for VeriFact**

Place product screenshots in this directory when captured from the **live running web application**. These images serve as visual documentation for research papers, presentations, and project demonstrations.

---

## Recommended Screenshots Registry

| Filename | View / Page Route | Recommended Content & Visual Elements |
| :--- | :--- | :--- |
| **`detect.png`** | Detect (`/`) | Complete Detect interface showing the candidate AI answer, Overall VeriFact Result card, MetaQA tabs, Independent Verdicts, and Web Evidence cards. |
| **`independent_verdicts.png`** | Detect (`/`) | Close-up of the Independent Verdicts card showing multi-model consensus, individual model votes (YES/NO/UNCERTAIN), and peer review rationales. |
| **`final_result_card.png`** | Detect (`/`) | Close-up of the Overall VeriFact Result card displaying the executive verdict badge, combined risk gauge, and metric breakdown. |
| **`metaqa_mutations.png`** | Detect (`/`) | Close-up of the Synonym and Antonym mutation tabs with verifier votes and penalty breakdowns. |
| **`web_evidence.png`** | Detect (`/`) | Close-up of claim-relevant evidence cards with extracted snippets, source domain badges, and external links. |
| **`history.png`** | History (`/history`) | Paginated audit log showing previous runs, search controls, and status filtering badges. |
| **`metaqa_guide.png`** | MetaQA Guide (`/metaqa`) | Educational guide view explaining metamorphic relations, synonym/antonym perturbations, and scoring tables. |
| **`web_analysis.png`** | Web Analysis (`/web-analysis`) | Educational guide view explaining question classification and authoritative domain routing. |
| **`settings.png`** | Settings (`/settings`) | Settings view showing Dark/Light theme toggle, active provider configuration, and citations. |

> [!NOTE]
> **No Synthetic Mockups**: Screenshots must be captured from the actual running web application at `http://localhost:5173`. Do not create synthetic or hand-edited graphic mockups.

---

## Capturing Screenshots Locally

### 1. Start the Backend Service
In your first terminal, activate the virtual environment and start FastAPI:

```bash
cd backend

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Start the Frontend Development Server
In your second terminal, start Vite:

```bash
cd frontend
npm run dev
```

### 3. Run a Detection Analysis
1. Open your browser to **[http://localhost:5173](http://localhost:5173)**.
2. Enter a test question (e.g., *"Who discovered penicillin and in what year?"*).
3. Click **"Run Verification"** and wait for the progressive verification steps to complete (status: `COMPLETED`).

### 4. Capture & Save Images
Capture the views using your browser's screenshot tool or OS utility, and save the PNG files directly into `docs/screenshots/` using the filenames listed in the registry table above.

---

## Related Documentation

- [`docs/README.md`](../README.md): Master index of technical documentation.
- [`frontend/README.md`](../../frontend/README.md): Frontend developer guide and component architecture.
- [`README.md`](../../README.md): Root project documentation.
