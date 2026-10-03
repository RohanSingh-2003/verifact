# Limitations & System Boundaries

This document provides an honest, technical accounting of the constraints, assumptions, and failure modes of VeriFact.

---

## 1. Consistency vs. Real-World Factual Truth

The primary methodological boundary of MetaQA is that it measures **internal semantic consistency**, not physical reality:
- If a language model generates a completely fictional claim (e.g., *"The Moon was manufactured in 1968"*) and coherently maintains that assertion under synonym paraphrases while rejecting antonym negations, MetaQA will record zero inconsistency ($H = 0.0$).
- Conversely, if a model states a factually true answer but becomes confused and inconsistent during mutation verification, MetaQA will penalize it with a high hallucination score.
- MetaQA is **reference-free** and does not consult external databases or search indices during detection.

---

## 2. Local 26B Inference Latency

Executing a 26-billion parameter model (`gemma4:26b`) locally is computationally demanding:
- On consumer hardware lacking dedicated high-VRAM GPUs, running the full verification sequence (generating the base answer, extracting claims, generating 6 mutations, and executing 6 separate verifier calls) can take several minutes.
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

## 5. Cross-Model Verification Boundaries

VeriFact supports cross-model verification where Ollama / Gemma 4:26B generates answers and mutations, while the Google Gemini API verifies them:
- **Purpose**: The cross-model configuration allows the same generated answer and mutation set to be verified by a different LLM, enabling comparison between same-model and cross-model verifier behavior.
- **Scientific Caveat**: We do **not** claim that Gemini is inherently more accurate than Gemma, nor that this architecture proves verifier bias. It enables the experiment; the empirical results determine what conclusions can be drawn.
- **API Availability & Rate Limits**: Live cross-model verification requires an active `GEMINI_API_KEY` and network access. If Gemini encounters rate limits (HTTP 429) or connection issues, MetaQA halts verification with an explicit failure state. The system never silently falls back to Ollama.
- **Mock Mode Independence**: In mock mode (`LLM_MODE=mock`), a deterministic `MockGeminiClient` is used so that offline evaluation and continuous integration run without external API dependencies.

---

## 6. Web Evidence Scope & Retrieval Boundaries

Web Evidence is an **independent external verification pipeline** running concurrently with MetaQA:
- **Tavily Dependency & API Limits**: Live external search requires network connectivity and a valid `TAVILY_API_KEY`. Verification is capped by request budgets (`WEB_MAX_CLAIMS=3`, `WEB_MAX_SEARCHES=3`).
- **Targeted Search, Not Universal Web Crawl**: The system searches targeted queries per claim; it does not crawl the entire internet. Niche or newly breaking facts may return sparse or inconclusive snippets.
- **Rule-Based Question Classification**: Question-type classification relies on pattern-matching heuristics, which can occasionally misclassify hybrid or ambiguous prompts.
- **Preferred Sources Do Not Guarantee Truth**: Routing toward preferred categories (`.gov`, NASA, Britannica) optimizes search relevance, but a domain is never treated as an automatic truth oracle.
- **Evidence Insufficiency Is Not Hallucination**: If snippets are missing or inconclusive, the claim is labeled `INSUFFICIENT_EVIDENCE`. Insufficient evidence is **never** treated as proof of hallucination.
- **Uncalibrated Score**: The Web Evidence Consistency Score reflects snippet agreement across checked claims; it is not a calibrated probability of hallucination and is never mathematically averaged with the MetaQA score.

---

## 7. Research Prototype Status

- VeriFact is an academic research prototype designed to investigate metamorphic consistency and evidence-grounded verification.
- It is not a commercial, production-hardened fact-checking platform and should not be used as the sole arbiter of truth in safety-critical medical, legal, or financial applications.
- Background verification uses FastAPI's in-process `BackgroundTasks` with `asyncio.gather`. Restarting the backend during an active detection terminates in-flight background analyses.
