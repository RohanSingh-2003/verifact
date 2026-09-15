# Research limitations

VeriFact is a controlled MetaQA implementation for studying same-model versus cross-model verification. The results of any single run are empirical observations under that run’s models, prompts, dataset, and mutation configuration. They do not establish a universal self-verification bias.

The frozen repository 2×2 (`58baff20-fb86-4f43-b20e-895a086ceb6b`) is **DEMO / MOCK DATA**. See `docs/final_results_lock.md`. Mock outputs must not be presented as live-model findings.

## Dataset size

The bundled pilot set is small (on the order of 40 items). Wilcoxon tests and confidence intervals on this scale are sensitive to sample size. Runs with fewer than 20 paired questions are labeled exploratory and should not be treated as confirmatory.

## Model dependence

Generator and verifier behavior is model-specific. A difference observed for one pair of models may not appear for another pair, another provider, or a later snapshot of the same model name.

## Mutation-generation dependence

Synonym and antonym quality depends on the mutation prompt and the generator. Weak, duplicated, or off-target mutations change the hallucination score independently of verifier identity. The 2×2 design holds mutations fixed across verifiers, but it does not remove mutation-quality error.

## Verifier calibration

Verifiers differ in strictness. The four condition means (A→A, A→B, B→A, B→B) must be reported together. Averaging only the diagonal versus only the off-diagonal confounds self-verification with verifier calibration.

## Stochasticity of LLM APIs

Live completions are not bit-reproducible. Temperature is fixed at 0 in the OpenAI-compatible client, but hosted APIs may still vary. Mock mode is deterministic and is for development only. Do not present mock outputs as research findings.

## Prompt sensitivity

Answer, mutation, and verifier prompts can shift scores. The verifier is not told the expected MetaQA verdict or mutation type, but it does receive the question, candidate answer, and mutated statement. Prompt wording remains a source of variation.

## MetaQA limitations

MetaQA is a metamorphic consistency check, not an external fact lookup. It does not retrieve Wikipedia, search the web, or consult a ground-truth database during detection. A consistent but false generator-verifier pair can receive a low hallucination score. Conversely, a factually correct answer can score high if the verifier is inconsistent.

## Ground-truth matching

Automatic labels used after detection rely on curated labels or normalized string matching against a reference answer. Matching is not perfect semantic evaluation. Ambiguous items are marked Needs Review and excluded from precision, recall, F1, and accuracy.

## Causal claims

A small 2×2 experiment can measure a paired score difference for the selected setup. It cannot by itself prove that “self-verification bias” is a general property of large language models, nor can it isolate every alternative explanation (prompt form, mutation artifacts, verifier calibration, dataset composition).
