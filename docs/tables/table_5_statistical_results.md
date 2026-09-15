# Table 5. Statistical results

Locked experiment `58baff20-fb86-4f43-b20e-895a086ceb6b`. **DEMO / MOCK DATA.** Alpha = 0.05. Primary test = Wilcoxon signed-rank on paired per-question differences (same − cross). Effect size = z / √n from the project implementation.

| Generator | Comparison | n | Mean difference | Median difference | Wilcoxon W | p | Effect size | Significant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A (model-a) | A→A vs A→B | 40 | −1.0 | −1.0 | 0 | p<0.001 | −1.0 | Yes (mock sample) |
| B (model-b) | B→B vs B→A | 40 | +1.0 | +1.0 | 0 | p<0.001 | +1.0 | Yes (mock sample) |

| Generator | Flip rate | R → H | H → R |
| --- | --- | --- | --- |
| A | 1.0 (40/40) | 40 | 0 |
| B | 1.0 (40/40) | 0 | 40 |

p<0.001 matches `results_summary.md` (stored p underflowed to 0.0). W was reconstructed from saved paired differences using `backend/app/experiment/stats.py`. These tests describe the mock client, not live LLMs.
