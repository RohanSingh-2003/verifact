# Limitations & System Boundaries

This document provides an honest, technical accounting of the constraints, assumptions, and failure modes of VeriFact.

---

## 1. Consistency vs. Real-World Factual Truth

The primary methodological limitation of MetaQA is that it measures **internal semantic consistency**, not physical reality:
- If a language model generates a completely fictional claim (e.g., *"The Moon was manufactured in 1968"*) and coherently maintains that assertion under synonym paraphrases while rejecting antonym negations, MetaQA will record zero inconsistency ($H = 0.0$).
- Conversely, if a model states a factually true answer but becomes confused and inconsistent during mutation verification, MetaQA will penalize it with a high hallucination score.
- The current system is strictly **reference-free** (zero-resource) and does not consult external databases or search indices during detection.

---

## 2. Local 26B Inference Latency

Executing a 26-billion parameter model (`gemma4:26b`) locally is computationally demanding:
- On consumer hardware lacking dedicated high-VRAM GPUs, running the full MetaQA sequence (generating the base answer, generating 6 mutations, and executing 6 separate verifier calls) can take several minutes.
- While VeriFact's progressive architecture mitigates perceived latency by showing the answer immediately, total end-to-end analysis time remains bounded by hardware throughput.
- Cold model loads require significant initialization time on the first query after daemon launch.

---

## 3. Mutation Generation Dependence

The quality of MetaQA testing is directly coupled to the model's ability to produce high-quality semantic variations:
- Models may occasionally generate sentence fragments, duplicate assertions, or fail to accurately invert a claim's polarity.
- Although VeriFact applies multi-round retries, syntax heuristics, and length bounds, low-quality mutations can introduce noise into the final score.
- Core claim extraction can miss nuanced subordinate clauses in long, multi-paragraph answers.

---

## 4. Verifier Judgment Fragility

The verifier LLM may struggle with subtle semantic distinctions:
- Highly technical, mathematical, or double-negated sentences can confuse the verifier.
- Verifiers occasionally return explanatory text rather than the requested JSON structure. While VeriFact's fallback logic captures these as `NOT SURE` (0.5 contribution), frequent parsing failures reduce discrimination between reliable and hallucinated text.

---

## 5. Web Evidence is Future Work

- External search integration (e.g., Tavily, Google, Bing, Wikipedia retrieval) is **not implemented** in the current release.
- VeriFact cannot verify claims against live real-time events or newly broken news occurring after the LLM's training cutoff.
- Any future evidence-grounded verification remains a planned extension.

---

## 6. Research Prototype Status

- VeriFact is an academic research prototype designed to investigate metamorphic testing and same-model versus cross-model verifier behaviors.
- It is not a commercial, production-hardened fact-checking platform and should not be used as the sole arbiter of truth in safety-critical medical, legal, or financial applications.
- Background tasks run via FastAPI's in-process `BackgroundTasks` rather than a distributed, persistent message queue (e.g., Celery/Redis). Restarting the backend service during an active detection will terminate in-flight background analyses.
