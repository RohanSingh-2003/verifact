# Experimental Methodology

## Research Question

Does using the same LLM as both answer-generator and mutation-verifier produce a systematically different hallucination score than using a different LLM as verifier, after controlling for verifier calibration?

## Hypotheses

**H0.** No systematic difference exists after accounting for verifier calibration.

**H1.** Same-model verification produces a systematically different hallucination score.

A statistically significant paired difference is not automatically labeled “self-verification bias.” The measured quantity is the **self-verification score difference** (same-model score minus cross-model score) for each generator. Opposite signs across generators, or differences that track verifier identity rather than same-versus-cross pairing, are treated as evidence about verifier calibration rather than as support for a general same-model effect.

## Experimental Design

| | Verifier A | Verifier B |
| --- | --- | --- |
| Generator A | A → A | A → B |
| Generator B | B → A | B → B |

- **Diagonal (A→A, B→B)** = same-model verification
- **Off-diagonal (A→B, B→A)** = cross-model verification

The four condition means are reported together. Averaging only the diagonal versus only the off-diagonal confounds pairing with verifier strictness.

## Fixed-Input Control

For each question and each generator:

1. The generator answer is produced **once**.
2. The mutation set is produced **once** from that answer.
3. The same mutation objects (IDs and texts, plus a SHA-256 `mutation_set_hash`) are sent to verifier A and verifier B.
4. Answers and mutations are **not** regenerated when the verifier changes.

This control is necessary so that the intended difference between paired conditions is verifier identity. Without it, mutation sampling or answer resampling could explain score changes.

Items that fail the identity check (question, base answer, mutation set ID, mutation texts) are excluded from paired tests and recorded; they are not silently repaired.

## Variables

**Independent variable.** Verifier identity relative to the generator (same-model vs cross-model).

**Dependent variable.** MetaQA hallucination score.

**Secondary outcomes.** Classification (Reliable / Hallucinated), NOT SURE rate, classification flip rate, and evaluation metrics against post-detection ground truth.

**Control variables.** Questions, generator answer, mutation set, mutation counts, threshold, prompts, and generation configuration (temperature, max tokens, retries).

## Statistical Analysis

For each generator, paired per-question scores are compared:

- `difference_A = score(A→A) − score(A→B)`
- `difference_B = score(B→B) − score(B→A)`

The primary test is the **Wilcoxon signed-rank** test on those differences (zeros dropped, average ranks for ties, normal approximation for n ≥ 10). Alpha = 0.05. Effect size is \(z / \sqrt{n}\) when computed. Samples with n < 20 are labeled exploratory and are not described as confirmatory. If p ≥ 0.05, the report states that **no statistically significant difference was detected**, not that “there is no difference.”

## Evaluation

After detection, generated answers may be labeled against a reference (or a curated label). Positive class = Hallucinated.

| | Predicted Reliable | Predicted Hallucinated |
| --- | --- | --- |
| Actual Reliable | TN | FP |
| Actual Hallucinated | FN | TP |

Reported metrics: accuracy, precision, recall, F1, specificity, false-positive rate (FPR), false-negative rate (FNR). Ambiguous items are **Needs Review** and are excluded from automatic P/R/F1 until resolved. Reference text is not inserted into MetaQA prompts.

A threshold sweep reclassifies **stored** scores at 0.30–0.70 in steps of 0.05. The threshold with highest F1 is reported as a diagnostic. Default production threshold remains 0.5 unless explicitly changed later.
