# Experimental Results

Source: frozen experiment `58baff20-fb86-4f43-b20e-895a086ceb6b`.  
**DEMO / MOCK DATA — not a live-model research result.** Full lock: `docs/final_results_lock.md`.

## 1. Dataset

| Field | Value |
| --- | --- |
| Dataset | `pilot` v1.0 |
| Questions | 40 |
| Source | Hand-selected factual items (not TruthfulQA) |
| Categories | named_entity, location, date, numeric, general_fact (8 each) |
| Ground truth | Reference answers and aliases in the evaluation layer only. Two items (q032, q039) are Needs Review and are excluded from automatic P/R/F1 (38 labeled). |

The detector received questions only. Reference answers were not passed into generation, mutation, or verification.

## 2. Model Configuration

| Role | Model |
| --- | --- |
| Generator A | model-a |
| Generator B | model-b |
| Verifier A | model-a |
| Verifier B | model-b |

These are mock client IDs used by `LLM_MODE=mock`. The intended live pair (`gpt-4o-mini`, `gpt-4o`) was configured but **not executed**.

## 3. MetaQA Detection Results

Mutations: 5 synonym + 5 antonym. Threshold = 0.5. NOT SURE rate = 0.0 in every 2×2 condition. Integrity exclusions: 0.

Post-detection metrics on 38 labeled items at threshold 0.5:

| Condition | Accuracy | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| A→A | 0.5 | 0.0 | 0.0 | 0.0 |
| A→B | 0.5 | 0.5 | 1.0 | 0.6667 |
| B→A | 0.5 | 0.0 | 0.0 | 0.0 |
| B→B | 0.5 | 0.5 | 1.0 | 0.6667 |

Accuracy is 0.5 in all four cells. F1 is 0.0 whenever verifier A is used and 0.6667 whenever verifier B is used.

## 4. 2×2 Results

| Generator | Verifier | Condition | Mean Score | Median | NOT SURE | Hallucinated % |
| --- | --- | --- | --- | --- | --- | --- |
| model-a | model-a | A → A | 0.0 | 0.0 | 0.0 | 0% |
| model-a | model-b | A → B | 1.0 | 1.0 | 0.0 | 100% |
| model-b | model-a | B → A | 0.0 | 0.0 | 0.0 | 0% |
| model-b | model-b | B → B | 1.0 | 1.0 | 0.0 | 100% |

n = 40 per cell. SD = 0.0. 95% CI collapses to the mean because every item in a cell has the same score.

## 5. Same vs Cross Comparison

| Generator | Same | Cross | Difference (same − cross) |
| --- | --- | --- | --- |
| A (model-a) | 0.0 (A→A) | 1.0 (A→B) | −1.0 |
| B (model-b) | 1.0 (B→B) | 0.0 (B→A) | +1.0 |

## 6. Statistical Significance

| Comparison | n | Mean paired difference | Median paired difference | Wilcoxon W | p | Effect size |
| --- | --- | --- | --- | --- | --- | --- |
| A→A vs A→B | 40 | −1.0 | −1.0 | 0 | p<0.001 | −1.0 |
| B→B vs B→A | 40 | +1.0 | +1.0 | 0 | p<0.001 | +1.0 |

p-values under alpha 0.05 are statistically significant **in this mock sample**. They do not describe live LLM behavior.

## 7. Classification Flips

Overall flip rate = 1.0 (80/80 generator–question pairs).

| Generator | Flips | Flip rate | Reliable → Hallucinated | Hallucinated → Reliable |
| --- | --- | --- | --- | --- |
| A | 40 / 40 | 1.0 | 40 | 0 |
| B | 40 / 40 | 1.0 | 0 | 40 |

## 8. Verifier Calibration

Across generators, scores equal the verifier identity:

- Verifier A mean score = 0.0 (A→A and B→A)
- Verifier B mean score = 1.0 (A→B and B→B)

NOT SURE rate = 0.0 for both verifiers. Verifier A classifies every item Reliable; verifier B classifies every item Hallucinated. The same-versus-cross pairing does not remain after this calibration view: the mock pattern is a **verifier effect**.

## 9. Threshold Analysis

Sweep on stored scores: 0.30 through 0.70. F1, precision, and recall do not change with threshold because scores are only 0.0 or 1.0.

Highest F1 in the sweep = **0.6667** (verifier B conditions). Verifier A F1 = 0.0 at every threshold.

Default production threshold remains **0.5**. The sweep does not replace it.

## 10. Category Analysis

Each category has n = 8 per generator (sufficient for descriptive reporting; not treated as a separate confirmatory test).

| Category | Generator | n | Mean same | Mean cross | Difference | Flip rate | NOT SURE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| date | A | 8 | 0.0 | 1.0 | −1.0 | 1.0 | 0.0 |
| date | B | 8 | 1.0 | 0.0 | +1.0 | 1.0 | 0.0 |
| general_fact | A | 8 | 0.0 | 1.0 | −1.0 | 1.0 | 0.0 |
| general_fact | B | 8 | 1.0 | 0.0 | +1.0 | 1.0 | 0.0 |
| location | A | 8 | 0.0 | 1.0 | −1.0 | 1.0 | 0.0 |
| location | B | 8 | 1.0 | 0.0 | +1.0 | 1.0 | 0.0 |
| named_entity | A | 8 | 0.0 | 1.0 | −1.0 | 1.0 | 0.0 |
| named_entity | B | 8 | 1.0 | 0.0 | +1.0 | 1.0 | 0.0 |
| numeric | A | 8 | 0.0 | 1.0 | −1.0 | 1.0 | 0.0 |
| numeric | B | 8 | 1.0 | 0.0 | +1.0 | 1.0 | 0.0 |

No category departs from the global mock pattern.

## 11. Main Finding

**Hypothesis status: inconclusive** for the live-LLM research question.

Our experiment observed, in the frozen mock 2×2, a complete verifier-identity split (score 0 vs 1) and opposite same-minus-cross signs for Generator A and Generator B. After accounting for verifier calibration, the data do not support a general same-model verification effect. Because the run used a deterministic mock client rather than live models, the original hypothesis is **not answered** by this evidence. We do not interpret these numbers as properties of `gpt-4o-mini`, `gpt-4o`, or LLMs in general.
