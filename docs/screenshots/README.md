# Application Screenshots

Place product screenshots here when captured from the **live running application**.

---

## Recommended Screenshots

| Filename | View / Page | Description |
| :--- | :--- | :--- |
| `detect.png` | Detect (`/`) | Full Detect interface displaying candidate AI answer, Overall VeriFact Result card, MetaQA tabs, and Web Evidence cards. |
| `model_selector.png` | Detect (`/`) | Model selection dropdown showing configured cloud models and provider badges. |
| `final_result_card.png` | Detect (`/`) | Close-up of the compact Overall VeriFact Result card showing verdict, combined risk score, and 3-column metric breakdown. |
| `metaqa_mutations.png` | Detect (`/`) | Close-up of the Synonym and Antonym mutation tabs with verifier responses and rationales. |
| `web_evidence.png` | Detect (`/`) | Close-up of claim-relevant evidence cards with extracted snippets, source domain badges, and external links. |
| `history.png` | History (`/history`) | Paginated audit log showing previous runs and filtering controls. |
| `metaqa_guide.png` | MetaQA Guide (`/metaqa`) | Educational guide explaining metamorphic relations, synonym/antonym perturbations, and scoring tables. |
| `web_analysis.png` | Web Analysis (`/web-analysis`) | Educational guide explaining question classification and authoritative domain routing. |
| `settings.png` | Settings (`/settings`) | Settings view showing Dark/Light theme selection, read-only AI configuration, and citations. |

> [!NOTE]
> Do not generate synthetic mockups. Only capture screenshots from the actual running web application.

---

## Capturing Screenshots Locally

1. **Start Backend**: In one terminal, activate the virtual environment and start FastAPI:
   ```bash
   cd backend
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
2. **Start Frontend**: In a second terminal, start Vite:
   ```bash
   cd frontend
   npm run dev
   ```
3. **Run Analysis**: Open `http://localhost:5173`, select a model, submit a factual question (e.g., *"What is the capital of Australia?"*), and wait for verification to complete.
4. **Capture & Save**: Use your browser or OS screenshot tool to capture the views and save them into `docs/screenshots/` matching the filenames above.
