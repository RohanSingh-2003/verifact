# VeriFact Research & Engineering Audit

Date: 2026-09-04  
Scope: backend MetaQA detector, 2×2 experiment, evaluation layer, statistics, APIs, tests, frontend data binding, and research claims.  
Mode: mock-only verification. No live LLM spend.

## 1. MetaQA Correctness

**Status: PASS** (after audit fixes)

The detector remains zero-resource MetaQA. Answer, mutation, and verify prompts forbid tools, retrieval, and browsing. Ground-truth fields are never formatted into those prompts.

### Scoring table

Implemented in `backend/app/metaqa/scoring.py` and covered by tests:

| Type | YES | NO | NOT SURE |
|------|-----|----|----------|
| Synonym | 0 | 1 | 0.5 |
| Antonym | 1 | 0 | 0.5 |

`hallucination_score` is the mean of mutation contributions, rounded to four decimals and clamped to `[0, 1]`. Classification is `score >= threshold → Hallucinated`, else Reliable. Default threshold is `0.5` and is not overwritten by the F1 sweep.

Expected verdicts are derived in code (`synonym → YES`, `antonym → NO`). They are stored for display and evaluation only. They are not present in `VERIFY_SYSTEM` / `VERIFY_USER`.

Malformed verifier output maps to `NOT SURE` with `parse_failed=True` and a warning log. Rationale is stored and does not enter the score.

### Mutation generation

The mutation LLM is asked for exactly `synonym_count` and `antonym_count` items. The collector:

- rejects malformed items
- removes duplicates keyed by `(type, mutated_text)`
- rejects no-op copies where mutated text equals original text
- retries once, then fails the question if unique counts are short

Semantic synonym-preservation and antonym inversion are **prompt constraints**, not independently measured. That is a research limitation, not a detector-methodology change.

### Issues found

- **Severity: Medium.** No-op mutations (identical original and mutated text) were previously accepted.  
  **Evidence:** `collect_valid_mutations` only deduplicated on type + mutated text.  
  **Fix:** reject case-insensitive original==mutated copies.  
  **Verification:** `test_collect_valid_mutations_rejects_noop_copies`.

- **Severity: Low.** `aggregate_score` did not explicitly bound the mean to `[0, 1]`. Contributions from the table already lie in that range.  
  **Fix:** clamp after averaging.  
  **Verification:** `test_aggregate_score_stays_in_unit_interval`.

## 2. 2×2 Experiment Correctness

**Status: PASS**

For each `(question, generator, trial)`:

1. Generate one base answer.
2. Generate one mutation set.
3. Store that set (IDs, texts, SHA-256 `mutation_set_hash`).
4. Verify the same objects with verifier A, then verifier B.
5. Compare mutation IDs **and** texts across the two conditions.
6. On mismatch, stop **that item**, set `integrity_ok=false`, record an exclusion, keep raw rows.

The four conditions are A→A, A→B, B→A, B→B. Pair type is `same` iff generator string equals verifier string. Answers and mutations are not regenerated when the verifier changes. Call counts in the mock 2×2 test match: 1 answer + 1 mutation batch per generator-question, and 10 verifications × 2 verifiers.

Resume skips completed `(question_id, generator, trial)` cells. Live mode does not fall back to the mock client.

### Issues found

- **Severity: Medium.** Experiment records lacked a mutation-set identifier for paper-level tracing.  
  **Evidence:** `ExperimentGeneration` stored mutations but no hash.  
  **Fix:** `hash_mutation_set` persisted as `mutation_set_hash` and exported in CSV/traces.  
  **Verification:** 2×2 tests assert a 64-character hash; export CSV includes the column.

## 3. Evaluation Correctness

**Status: PASS**

Detection runs first. `resolve_ground_truth` is applied to the already-generated answer. Reference answers, aliases, and labels are not interpolated into MetaQA prompts.

Positive class = Hallucinated.

```
                    Predicted Reliable    Predicted Hallucinated
Actual Reliable          TN                    FP
Actual Hallucinated      FN                    TP
```

Zero denominators return `0.0`. Needs Review rows are excluded from P/R/F1. Threshold sweep reclassifies **saved scores** at 0.30–0.70. Best F1 is stored as an experimental observation (`best_threshold_by_f1`); `is_primary` remains the configured production threshold (default 0.5).

## 4. Statistical Analysis

**Status: PASS**

Each of A→A, A→B, B→A, B→B reports n, mean, median, SD, 95% CI, Reliable %, Hallucinated %, NOT SURE rate.

Paired differences:

- Generator A: A→A − A→B (`same − cross`)
- Generator B: B→B − B→A (`same − cross`)

Named **self-verification score difference**, not bias. Primary test: Wilcoxon signed-rank on per-question differences, alpha = 0.05. Optional paired t-test. n < 20 is labeled exploratory and is **not** called statistically significant. Wilcoxon effect size `z / sqrt(n)` is reported when computed.

### Issues found

- **Severity: Low.** Median paired difference was not reported next to the mean difference.  
  **Fix:** `median_paired_difference` and `mean_paired_difference` on the analysis block.  
  **Verification:** `test_self_verification_difference`.

- **Severity: Medium.** Category rows with n=1 still looked like confirmatory statistics.  
  **Fix:** `insufficient_data` when n < 5, with an explicit note. Raw n and means are retained, not deleted.  
  **Verification:** `test_category_analysis_flags_insufficient_samples`.

## 5. Reproducibility

**Status: PASS** (for a live run, once credentials exist)

Stored on experiment config / research log: dataset name and version, model names, mutation counts, threshold, trials, prompt bundle/version IDs, temperature, max tokens, timeout, retries, concurrency, llm_mode, timestamps. API keys are not exported. `.env` is gitignored. `.env.example` uses `replace-with-your-key` and `LLM_MODE=mock`.

Live hosted APIs remain non-bit-reproducible even at temperature 0. Mock mode is deterministic.

## 6. Failure Handling

**Status: PASS** with one residual risk

| Failure | Behavior |
|---------|----------|
| Empty / timeout / generator / mutation-generation failure | Item fails; experiment records exclusion; no mock substitution in live mode |
| Single verifier call failure | That mutation → NOT SURE + `parse_failed`; other mutations continue |
| Malformed verdict | NOT SURE + log |
| Rate limit / 5xx / timeout | Bounded retry with backoff in the OpenAI-compatible client |
| DB write after detect | 500; detection is not reported as saved |
| Interrupted experiment | status `failed` or incomplete cells listed; resume skips completed cells |
| Live without key or confirm | 400, no silent mock run |

### Remaining issue (not a silent mock swap)

- **Severity: Medium.** A verifier **API** failure is scored as NOT SURE (0.5), which is the same MetaQA fallback as unparseable text. Instrumented call counters still increment `failed`. A total verifier outage could therefore look like a mid-scale 0.5 condition unless `parse_failed` / `call_stats` are inspected.  
  **Fix this audit:** none that would change MetaQA (Part 1 requires malformed → NOT SURE and not crashing the run).  
  **Mitigation:** inspect `parse_failed` and `call_stats` before interpreting a live run.

## 7. Testing

**Status: PASS** — 111 pytest passed (mock only).

Coverage relative to the audit list:

1. Synonym scoring — yes  
2. Antonym scoring — yes  
3. NOT SURE scoring — yes  
4. Score range — yes (including clamp)  
5. Threshold classification — yes  
6. Malformed verdict parsing — yes  
7. Duplicate mutation removal — yes  
8. Expected verdict generation — yes  
9. Verifier prompt isolation — yes (template + captured live-style mock calls)  
10. Fixed mutation reuse — yes  
11. 2×2 conditions — yes  
12. Paired score differences — yes  
13. Confusion matrix — yes  
14. Threshold sweep — yes  
15. Zero-denominator metrics — yes  
16. Database persistence — yes  
17. Experiment export — yes  
18. API validation — yes  
19. Mock LLM determinism — yes  

No test makes a real provider call.

## 8. Code Quality

**Status: PASS** for methodology-critical code.

- pytest: 111 passed  
- frontend: `npm run build` succeeded (`tsc -b` + Vite)  
- ruff: FastAPI `Depends()` defaults are the framework idiom (ignored via `backend/ruff.toml` B008). Unused `Classification` import in the evaluator was removed. Remaining ruff items are import-order style, not logic defects.

`emptyExperimentSnapshot()` in the frontend mapper is unused by the Experiments page (dead helper). Low severity; left in place to avoid a UI-layer cleanup that is outside this audit’s methodology fixes.

## 9. Research-Claim Audit

**Status: PASS**

README, `docs/limitations.md`, experiment key-finding generator, and the dashboard describe an **investigation** of same- vs cross-model scores. Difference is not auto-labeled bias. Small-n results are exploratory. Mock output is labeled DEMO / MOCK DATA. No claim that MetaQA always detects hallucinations, that LLMs cannot self-verify, or that the method is better than alternatives.

The phrase “self-verification bias” appears only as something the system **does not** prove.

## 10. Remaining Risks

| Severity | Risk |
|----------|------|
| High (operational) | No live 40-question run has been completed; paper numbers do not exist yet. |
| Medium | Mutation quality is LLM-prompted, not independently validated for true synonymy/antonymy. |
| Medium | Verifier API failures share the NOT SURE scoring path with parse failures. |
| Medium | Automatic ground-truth matching is string/alias based, not semantic. |
| Medium | Wilcoxon uses a normal approximation; n<20 is exploratory. |
| Low | Live APIs are stochastic at temperature 0. |
| Low | Category splits on 40 items can still be thin even when n≥5. |

These are limitations of the design and of live LLM APIs. They do not invalidate the MetaQA table, the fixed-mutation 2×2 control, or the evaluation/sweep/stats pipeline.

## Final Audit Status

**READY FOR REAL EXPERIMENT**

Core methodology, fixed-input 2×2 controls, evaluation isolation, threshold sweep, statistical reporting, and the mock test suite are correct. Proceed with one-question live smoke, then the confirmed 30–50 question pilot. Do not treat mock pytest artifacts under `experiments/` as paper results.
