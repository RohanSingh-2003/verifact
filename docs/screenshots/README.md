# Application Screenshots

Place product screenshots here when captured from the **running application**.

### Recommended Screenshots:

| File | Page | Description |
| :--- | :--- | :--- |
| `detect.png` | Detect (`/`) | Full Detect view showing candidate answer, Overall VeriFact Result card, MetaQA, and Web Evidence. |
| `final_result_card.png` | Detect (`/`) | Close-up of the compact Overall VeriFact Result card with 3-column score breakdown. |
| `metaqa_mutations.png` | Detect (`/`) | Close-up of the synonym and antonym mutation inspection tabs. |
| `web_evidence.png` | Detect (`/`) | Close-up of claim-relevant evidence cards with source links and verifier reasoning. |
| `history.png` | History (`/history`) | Paginated audit log of previous verification runs. |
| `metaqa_guide.png` | MetaQA Guide (`/metaqa`) | Educational guide explaining metamorphic testing and contribution scoring. |
| `web_analysis.png` | Web Analysis (`/web-analysis`) | Educational guide explaining authoritative domain strategies and claim checking. |
| `settings.png` | Settings (`/settings`) | Settings page showing Appearance theme selection, active AI Configuration, and About VeriFact. |

> [!NOTE]
> Do not invent or generate synthetic mockup screenshots. Only capture from the live running application.

### Capturing Screenshots Locally:

1. Start the FastAPI backend on port 8000 (`LLM_MODE=live` or `LLM_MODE=mock`).
2. Start the Vite frontend development server on port 5173.
3. Open `http://localhost:5173` and run an analysis on Detect.
4. Capture screenshots using your browser's devtools or screenshot tool, and save them in this directory.
