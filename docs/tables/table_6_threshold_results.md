# Table 6. Threshold sweep

Locked experiment `58baff20-fb86-4f43-b20e-895a086ceb6b`. **DEMO / MOCK DATA.** No new LLM calls. included_examples = 38.

Because scores are only 0.0 or 1.0, every sweep threshold in {0.30, …, 0.70} yields the same confusion counts.

| Condition | Thresholds | TP | TN | FP | FN | Accuracy | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A→A | 0.30–0.70 | 0 | 19 | 0 | 19 | 0.5 | 0.0 | 0.0 | 0.0 |
| A→B | 0.30–0.70 | 19 | 0 | 19 | 0 | 0.5 | 0.5 | 1.0 | 0.6667 |
| B→A | 0.30–0.70 | 0 | 19 | 0 | 19 | 0.5 | 0.0 | 0.0 | 0.0 |
| B→B | 0.30–0.70 | 19 | 0 | 19 | 0 | 0.5 | 0.5 | 1.0 | 0.6667 |

Highest F1 in the sweep = **0.6667**. Default production threshold remains **0.5**.

Source: `experiments/processed/58baff20-fb86-4f43-b20e-895a086ceb6b/threshold_sweep.csv`.
