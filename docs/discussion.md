# Discussion

## 1. Interpretation

The frozen artifacts implement the intended MetaQA 2×2 pipeline: one answer and one mutation set per generator, then both verifiers on those exact mutations. In the locked run, every cell is deterministic. That is useful as a pipeline demonstration and a calibration warning. It is not a measurement of live model behavior.

Within the mock data, hallucination scores did not vary by question, category, or generator answer content. They varied only with verifier identity. That is the observation that should drive interpretation.

## 2. Same-Model vs Cross-Model Verification

Same-model scores were lower than cross-model scores for Generator A and higher for Generator B. Both paired Wilcoxon tests were significant at α = 0.05 in this mock sample (p<0.001). The effects therefore **differ between generators**. That is outcome D of the experimental plan, and it is expected if the true factor is verifier identity rather than same-model pairing.

We do not describe this as self-verification bias. After the four cells are viewed together, same-versus-cross is not a residual effect.

## 3. Verifier Calibration

Verifier A assigned score 0.0 and Reliable to all 80 of its (question, generator) cells. Verifier B assigned score 1.0 and Hallucinated to all 80 of its cells. NOT SURE rate was 0.0. This is a maximal calibration difference. H0’s clause “after accounting for verifier calibration” is decisive here: the apparent same-model differences are the verifier split written in a same-versus-cross layout.

For a live study, the same four-cell report is required. A single diagonal-versus-off-diagonal average would have been misleading even in this mock run.

## 4. Mutation Behavior

The locked 2×2 files do not break scores down by synonym versus antonym contribution. The mock verifier tables are constructed so that one model emits the expected YES/NO pattern and the other emits the inverted pattern, which yields contributions of 0 or 1 on every mutation. We therefore cannot claim an empirical synonym-versus-antonym finding about live models from this run. Mutation quality (true synonymy or inversion) remains a methodological limitation of MetaQA as implemented.

## 5. Detection Performance

Against post-detection labels, accuracy was 0.5 in every condition. In this mock run, verifier A predicted Hallucinated for 0 of 38 labeled items (recall 0, F1 0). Verifier B predicted Hallucinated for all 38 (recall 1.0, precision 0.5, F1 0.6667). Those figures describe a mock classifier that ignores item content. They should not be cited as MetaQA detection performance on live generators.

## 6. Threshold Sensitivity

The sweep from 0.30 to 0.70 did not change F1, precision, or recall. Interior thresholds cannot separate items when every score is 0 or 1. The highest observed F1 (0.6667) is therefore not an informative operating-point discovery. Default threshold 0.5 stays in place.

## 7. Practical Implications

For systems that reuse a generator as its own MetaQA verifier, this project shows **how** to test that design: freeze answers and mutations, swap only the verifier, report calibration, and test paired differences. The frozen mock run shows that a naive same-versus-cross table can look “significant” while being a verifier effect. Until a live run exists, VeriFact should be described as an implementation and experimental apparatus, not as a finished empirical claim about LLM self-verification.

## 8. Limitations

- No live LLM experiment is stored.
- n = 40, two models in mock form, one trial.
- Automatic ground-truth matching is string/alias based; two items are Needs Review.
- Mutation semantics are prompt-constrained, not independently scored.
- Wilcoxon uses a normal approximation; here all non-zero differences are tied in magnitude.
- Results must not be generalized to “all LLMs.”

See `docs/limitations.md` and `docs/final_results_lock.md`.

## 9. Future Work

These extensions are separate from the current MetaQA core:

- Larger labeled datasets
- More model families and providers
- Repeated trials to quantify API stochasticity
- Stronger mutation generation and checks for no-op or off-target mutations
- Additional metamorphic relations
- Atomic claim decomposition
- An optional evidence-grounded extension that is not part of the zero-resource detector
- A larger statistical study with pre-registered live configuration
