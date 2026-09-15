# Table 3. MetaQA detection metrics

Locked experiment `58baff20-fb86-4f43-b20e-895a086ceb6b`. **DEMO / MOCK DATA.** Positive class = Hallucinated. n_labeled = 38 at threshold 0.5.

| Condition | n (scores) | Mean score | NOT SURE rate | Accuracy | Precision | Recall | F1 | Specificity | FPR | FNR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A→A | 40 | 0.0 | 0.0 | 0.5 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 1.0 |
| A→B | 40 | 1.0 | 0.0 | 0.5 | 0.5 | 1.0 | 0.6667 | 0.0 | 1.0 | 0.0 |
| B→A | 40 | 0.0 | 0.0 | 0.5 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 1.0 |
| B→B | 40 | 1.0 | 0.0 | 0.5 | 0.5 | 1.0 | 0.6667 | 0.0 | 1.0 | 0.0 |

Accuracy, precision, recall, and F1: `experiments/processed/58baff20-fb86-4f43-b20e-895a086ceb6b/condition_summary.csv`.  
TP/TN/FP/FN at 0.5: `threshold_sweep.csv` (included_examples = 38). Specificity, FPR, and FNR are computed from those counts.
