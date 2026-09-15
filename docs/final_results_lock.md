# Final Results Lock

**Status of frozen run:** DEMO / MOCK DATA. This lock records the latest completed 40-question 2×2 artifact in the repository. It is **not** a live-model research result. No saved experiment in this repository has `"mode": "live"`.

These results are frozen and should not be manually modified.

## Experiment ID

`58baff20-fb86-4f43-b20e-895a086ceb6b`

- Name: Verifier comparison
- Status: completed
- Mode: `mock`
- Started: 2026-09-04T11:25:23.102104+00:00
- Completed: 2026-09-04T11:25:23.717567+00:00
- Artifact path: `experiments/results/58baff20-fb86-4f43-b20e-895a086ceb6b/`

A later one-question pytest artifact (`1578380f-046a-4aa1-905d-02f6e7c1ede3`, dataset `mini`, n=1) exists. It is **not** the locked research run.

The intended live configuration in `experiments/config/final_experiment.yaml` was frozen as **not executed** (no live API credentials). That intended live run is **not** this lock.

## Dataset

| Field | Value |
| --- | --- |
| Name | `pilot` |
| Version | 1.0 |
| Source | Hand-selected factual questions. Not TruthfulQA. |
| Path | `backend/data/datasets/pilot.json` |
| Questions used | 40 |
| Categories | named_entity, location, date, numeric, general_fact (8 each) |
| Needs Review items excluded from P/R/F1 | q032, q039 (2 items; 38 labeled) |
| Exclusions from 2×2 integrity checks | none (`exclusions.json` is empty) |

## Models

| Role | Frozen run (mock IDs) | Intended live config (not executed) |
| --- | --- | --- |
| Generator A | `model-a` | `gpt-4o-mini` |
| Generator B | `model-b` | `gpt-4o` |
| Verifier A | `model-a` | `gpt-4o-mini` |
| Verifier B | `model-b` | `gpt-4o` |

## Configuration

| Setting | Value |
| --- | --- |
| Synonym mutations | 5 |
| Antonym mutations | 5 |
| Total mutations | 10 |
| Threshold | 0.5 (production default; not replaced by the sweep) |
| Trials | 1 |
| Temperature | 0.0 |
| Max output tokens | 800 |
| Timeout | 60 s |
| Max retries | 2 |
| Verify concurrency | 5 |
| Prompt bundle | `metaqa-v1` (`answer-v1`, `mutation-v1`, `verify-v1`) |
| Mutation reuse valid | True |
| Alpha | 0.05 |
| Primary test | Wilcoxon signed-rank |

## A→A Result

Generator `model-a`, verifier `model-a` (same-model).

- n = 40
- Mean score = 0.0
- Median = 0.0
- SD = 0.0
- 95% CI = [0.0, 0.0]
- NOT SURE rate = 0.0
- Reliable = 100%
- Hallucinated = 0%

## A→B Result

Generator `model-a`, verifier `model-b` (cross-model).

- n = 40
- Mean score = 1.0
- Median = 1.0
- SD = 0.0
- 95% CI = [1.0, 1.0]
- NOT SURE rate = 0.0
- Reliable = 0%
- Hallucinated = 100%

## B→A Result

Generator `model-b`, verifier `model-a` (cross-model).

- n = 40
- Mean score = 0.0
- Median = 0.0
- SD = 0.0
- 95% CI = [0.0, 0.0]
- NOT SURE rate = 0.0
- Reliable = 100%
- Hallucinated = 0%

## B→B Result

Generator `model-b`, verifier `model-b` (same-model).

- n = 40
- Mean score = 1.0
- Median = 1.0
- SD = 0.0
- 95% CI = [1.0, 1.0]
- NOT SURE rate = 0.0
- Reliable = 0%
- Hallucinated = 100%

## Statistical Results

Self-verification score difference = mean(same-model) − mean(cross-model).

Wilcoxon W and p-values below reuse the project’s signed-rank implementation on the **saved** paired differences. The generated `results_summary.md` reported `p<0.001` and effect sizes ±1.0. Recomputation from `paired_comparisons.csv` yields W = 0 and p stored as 0.0 (underflow; report as p<0.001).

| Generator | Same mean | Cross mean | Mean paired difference | Median paired difference | n | Wilcoxon W | p | Effect size (z/√n) | Significant at α=0.05 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A (`model-a`) | 0.0 | 1.0 | −1.0 | −1.0 | 40 | 0 | p<0.001 | −1.0 | Yes (mock data) |
| B (`model-b`) | 1.0 | 0.0 | +1.0 | +1.0 | 40 | 0 | p<0.001 | +1.0 | Yes (mock data) |

Flip rate = 1.0 for both generators (40/40).

- Generator A: Reliable → Hallucinated = 40; Hallucinated → Reliable = 0
- Generator B: Hallucinated → Reliable = 40; Reliable → Hallucinated = 0

## Detection Metrics

Positive class = Hallucinated. Automatic metrics use 38 labeled items (2 Needs Review excluded). Values are from `condition_summary.csv` and `threshold_sweep.csv` at threshold 0.5.

| Condition | Accuracy | Precision | Recall | F1 | TP | TN | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A→A | 0.5 | 0.0 | 0.0 | 0.0 | 0 | 19 | 0 | 19 |
| A→B | 0.5 | 0.5 | 1.0 | 0.6667 | 19 | 0 | 19 | 0 |
| B→A | 0.5 | 0.0 | 0.0 | 0.0 | 0 | 19 | 0 | 19 |
| B→B | 0.5 | 0.5 | 1.0 | 0.6667 | 19 | 0 | 19 | 0 |

Derived from the same confusion counts:

| Condition | Specificity | FPR | FNR |
| --- | --- | --- | --- |
| A→A | 1.0 | 0.0 | 1.0 |
| A→B | 0.0 | 1.0 | 0.0 |
| B→A | 1.0 | 0.0 | 1.0 |
| B→B | 0.0 | 1.0 | 0.0 |

## Threshold Analysis

Sweep: 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70 on **stored** scores (no new LLM calls).

Because every hallucination score is exactly 0.0 or 1.0, metrics are constant across the sweep.

- Highest F1 in the sweep = **0.6667** (conditions that use verifier B)
- Verifier A conditions have F1 = 0.0 at every sweep threshold
- Production / default threshold remains **0.5** and is not replaced by the sweep

## Key Finding

DEMO / MOCK DATA. Within this frozen mock run, hallucination scores tracked **verifier identity**: verifier A assigned score 0.0 in both A→A and B→A; verifier B assigned score 1.0 in both A→B and B→B. Same-model minus cross-model therefore had opposite signs for Generator A (−1.0) and Generator B (+1.0). That pattern is a verifier-calibration confound in the mock client, not evidence about live LLM self-verification.

The original research question about live LLMs is **inconclusive** because no live experiment is stored.

## Limitations

- The locked run is mock, deterministic, and uses placeholder model IDs (`model-a`, `model-b`).
- Dataset size is 40 questions; two items are Needs Review for automatic detection metrics.
- Mutation quality is not independently validated.
- Live hosted APIs were not used; live runs would be stochastic even at temperature 0.
- Threshold 0.5 remains the default; the mock sweep cannot identify a meaningful operating point because scores have no interior values.
- See `docs/limitations.md`.

These results are frozen and should not be manually modified.
