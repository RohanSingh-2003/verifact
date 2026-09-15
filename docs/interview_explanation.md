# Interview explanation

Answers match the implementation and the frozen mock 2×2 (`58baff20-fb86-4f43-b20e-895a086ceb6b`). Do not present mock scores as live LLM behavior.

## 30-second explanation

VeriFact is a research app that implements MetaQA: it restates an LLM answer with synonyms and antonyms, asks a verifier YES/NO/NOT SURE, and turns that into a hallucination score. I also built a 2×2 experiment so the same mutations can be judged by the generator’s own model versus a different verifier.

## 60-second explanation

Fact-conflicting hallucinations are wrong facts said fluently. VeriFact does not look up Wikipedia. It tests consistency. Synonym mutations should be accepted; antonym mutations should be rejected. The average of those contributions is the score; 0.5 is the default threshold. The research question is whether same-model verification scores differently from cross-model verification after you account for how strict each verifier is. We freeze the answer and mutations so the only intended change is verifier identity.

## 2-minute technical explanation

Stack: React/TypeScript UI, FastAPI, SQLite, OpenAI-compatible or mock LLM client. Detection: generate → mutate → verify concurrently with a bound → MetaQA table → classify. Evaluation labels the already-generated answer against a reference and never injects that reference into prompts. The 2×2 stores a mutation-set hash and fails an item if A and B did not see the same texts. Statistics: paired Wilcoxon on same-minus-cross scores, alpha 0.05. The frozen repository run is mock: verifier A always scores 0, verifier B always scores 1, so the live hypothesis is inconclusive.

## Why MetaQA?

It gives a reference-free, mutation-level audit trail. VeriFact implements it; it does not replace retrieval-based fact checking.

## Why synonym mutations?

A consistent answer should survive paraphrase. Unexpected NO on a synonym raises the score.

## Why antonym mutations?

A consistent answer should not support a negated or inverted claim. Unexpected YES on an antonym raises the score.

## Why NOT SURE?

The verifier may be unable to decide, or the parse may fail. NOT SURE contributes 0.5 and is tracked as a diagnostic. Rationales do not enter the score.

## Why zero-resource?

The research target is metamorphic consistency, not evidence retrieval. Mixing search into the detector would change the method.

## Why 2×2 instead of only A→A vs A→B?

A→A vs A→B confounds pairing with verifier B’s strictness. The four cells separate generator, verifier, and same-versus-cross.

## Why fixed mutation sets?

If mutations are regenerated per verifier, score changes can come from different paraphrases. Freezing the set isolates verifier identity.

## Why Wilcoxon?

Paired per-question scores need not be normal. Wilcoxon signed-rank is the primary test; n<20 is labeled exploratory.

## What did the experiment find?

In the frozen **mock** 40-question run, scores followed verifier identity (0 vs 1) and same-minus-cross had opposite signs for the two generators. That does not support a general same-model effect after calibration. Live LLMs were not measured.

## What are the limitations?

Mock lock, n=40, two placeholder models, prompt-only mutation quality, string-based ground-truth matching, stochastic live APIs if used later.
