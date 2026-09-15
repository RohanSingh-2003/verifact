# Screenshots

Place product screenshots here when captured from the **running application**.

Recommended files:

| File | Page |
| --- | --- |
| `detect.png` | Detect — question, score, classification |
| `mutations.png` | Mutation analysis tabs |
| `experiments.png` | 2×2 experiment dashboard |
| `history.png` | Run history |

Do not invent or generate fake UI screenshots.

To capture locally:

1. `LLM_MODE=mock` in `backend/.env`
2. Start FastAPI on port 8000 and Vite on 5173
3. Analyze a sample question on Detect
4. Open History and Experiments
5. Save PNGs into this folder and link them from the README
