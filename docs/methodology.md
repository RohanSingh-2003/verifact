# VeriFact Methodology

## 1. Problem Definition

Large language models can produce fluent answers that conflict with established facts. This project treats **fact-conflicting hallucination** as a generated answer that is inconsistent with a known factual reference (for example, naming the wrong capital, person, date, or quantity). VeriFact does not try to score stylistic quality or open-ended opinion. It implements a reference-free consistency check at detection time and, separately, may compare the already-generated answer with a reference during evaluation.

## 2. MetaQA

VeriFact implements the **MetaQA** metamorphic hallucination-detection methodology. MetaQA is an existing approach: it probes whether an answer remains consistent under meaning-preserving and meaning-reversing restatements. VeriFact does **not** claim to have invented MetaQA.

- **MetaQA** = the existing metamorphic detection methodology (mutation types, YES/NO/NOT SURE verification, contribution table, averaged score, threshold classification).
- **VeriFact** = a software implementation of that methodology, plus an interactive UI, evaluation layer, and a controlled 2×2 experiment on same-model versus cross-model verification.

## 3. Base Answer Generation

Given a user or dataset question, the generator LLM is asked for a concise factual answer. The detector stores the question, generator model, raw answer text, generation parameters, and timestamp. Ground-truth reference answers are **not** included in this prompt. If generation fails after the configured retries, the item is marked failed; mock output is not substituted in live mode.

## 4. Metamorphic Mutation Generation

From the base answer, a mutation LLM produces two families of restatements:

- **Synonym mutations** — meaning-preserving paraphrases of the original statement. A consistent verifier is expected to accept them (YES).
- **Antonym / negation mutations** — meaning-reversing restatements. A consistent verifier is expected to reject them (NO).

Default counts are 5 synonym and 5 antonym mutations (10 total). The collector rejects malformed items, duplicates, and no-op copies (mutated text identical to the original). Expected verdicts are derived in code and are not sent to the verifier.

## 5. Mutation Verification

Each mutated statement is verified independently. The verifier receives the question, the candidate answer, and the mutated statement. It does not receive mutation type, expected verdict, or any external evidence. The allowed labels are:

- **YES** — the mutated statement is supported given the candidate answer
- **NO** — the mutated statement is not supported
- **NOT SURE** — the verifier cannot decide, or the output cannot be parsed

Malformed verifier text maps to NOT SURE with `parse_failed=True`.

## 6. MetaQA Scoring

Each valid mutation contributes a numeric score:

| Mutation Type | YES | NO | NOT SURE |
| --- | --- | --- | --- |
| Synonym | 0 | 1 | 0.5 |
| Antonym | 1 | 0 | 0.5 |

## 7. Hallucination Score

Let \(c_i\) be the contribution of mutation \(i\) and \(n\) the number of valid mutations:

\[
\text{hallucination\_score} = \frac{1}{n}\sum_{i=1}^{n} c_i
\]

The implementation rounds to four decimals and clamps the mean to \([0, 1]\).

## 8. Threshold Classification

With default threshold \(\theta = 0.5\):

- score \(\ge \theta\) → **Hallucinated**
- score \(< \theta\) → **Reliable**

A later F1 sweep over stored scores is an experimental diagnostic. It does not automatically replace the production threshold.

## 9. Zero-Resource Constraint

The core detector does not retrieve external evidence and does not use:

- Google
- Wikipedia
- RAG
- vector databases
- embeddings
- external fact-checking APIs

External references are used only for evaluation/ground truth, after detection has finished.

## 10. Explainability

The UI and stored traces show each mutation, the verifier verdict, the contribution, and the verifier rationale. **Rationales do not affect the score.** Only the parsed YES / NO / NOT SURE label enters the MetaQA table.
