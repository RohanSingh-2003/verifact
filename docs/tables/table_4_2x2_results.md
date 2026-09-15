# Table 4. 2×2 hallucination scores

Locked experiment `58baff20-fb86-4f43-b20e-895a086ceb6b`. **DEMO / MOCK DATA.** Threshold = 0.5.

| Generator | Verifier | Condition | Pair type | n | Mean | Median | SD | 95% CI | NOT SURE | Reliable % | Hallucinated % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| model-a | model-a | A → A | same | 40 | 0.0 | 0.0 | 0.0 | [0.0, 0.0] | 0.0 | 100 | 0 |
| model-a | model-b | A → B | cross | 40 | 1.0 | 1.0 | 0.0 | [1.0, 1.0] | 0.0 | 0 | 100 |
| model-b | model-a | B → A | cross | 40 | 0.0 | 0.0 | 0.0 | [0.0, 0.0] | 0.0 | 100 | 0 |
| model-b | model-b | B → B | same | 40 | 1.0 | 1.0 | 0.0 | [1.0, 1.0] | 0.0 | 0 | 100 |

Source: `experiments/processed/58baff20-fb86-4f43-b20e-895a086ceb6b/condition_summary.csv`.
