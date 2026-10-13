# Limitations & System Boundaries

This document provides a technical accounting of the constraints, assumptions, and failure modes of VeriFact.

---

## 1. Consistency vs. Real-World Factual Truth

The primary methodological boundary of MetaQA is that it evaluates **internal semantic consistency**, not physical reality:
- If a language model generates a completely fictional claim (e.g., *"The Moon was manufactured in 1968"*) and coherently maintains that assertion under synonym paraphrases while rejecting antonym negations, MetaQA will record zero inconsistency ($H = 0.0$).
- Conversely, if a model states a factually true answer but becomes confused during mutation verification, MetaQA will penalize it with an elevated hallucination score.
- MetaQA is **reference-free** and does not consult external databases or search indices during detection.

---

## 2. Cloud API Latency & Rate Limits

All model inference in VeriFact runs through official cloud provider APIs (Ollama Cloud, Google Gemini, Cloudflare Workers AI, Groq, OpenRouter):
- **Network & Provider Latency**: Multiple LLM API calls are required per detection (answer generation, mutation generation, concurrent mutation verification, and direct peer reviews). Round-trip network latency depends on cloud provider responsiveness.
- **Progressive Architecture**: VeriFact's progressive design mitigates perceived latency by displaying Gemma's candidate answer immediately (`answer_ready`), but end-to-end background completion times remain bounded by third-party provider response speeds.
- **Rate Limits & Quotas**: If a cloud provider encounters rate limits (HTTP 429) or connection timeouts, the affected verification branch reports an explicit failure state. VeriFact never silently hallucinates or falls back to unintended models.

---

## 3. Mutation Generation Dependence

The quality of MetaQA testing is directly coupled to the model's ability to produce high-quality semantic variations:
- Models may occasionally generate sentence fragments, duplicate assertions, or fail to accurately invert a claim's polarity.
- Although VeriFact applies multi-round retries, syntax heuristics, and length bounds, low-quality mutations can introduce noise into the final score.
- Core claim extraction can miss nuanced subordinate clauses in long, multi-paragraph answers.

---

## 4. Verifier Judgment Fragility

Verifier LLMs may struggle with subtle semantic distinctions:
- Highly technical, mathematical, or double-negated sentences can confuse the verifier.
- Verifiers occasionally return explanatory text rather than the requested JSON structure. While VeriFact's fallback logic captures these as `NOT SURE` (0.5 contribution), frequent parsing failures reduce discrimination between reliable and hallucinated text.
- Malformed outputs or network timeouts are isolated as technical errors (`parse_failed=True`) rather than counted as legitimate uncertainty judgments.

---

## 5. Multi-Model Verifier Pool Boundaries

VeriFact supports a multi-model verification architecture where Gemma 4:26B generates answers and candidate mutations, while independent cloud models (`Gemini 3.8 Flash`, `GLM-4.7-Flash`, `Qwen-2.5-32B`, `Liquid LFM-2.5`) verify mutations and conduct direct-answer peer review:
- **Scientific Caveat**: We do **not** claim that verifier models are inherently more truthful than the generator. Structural separation mitigates self-confirmation bias, but verifiers remain fallible and can share common pre-training biases.
- **Provider Readiness**: Live multi-model verification requires configured cloud credentials in `backend/.env`. If a verifier model is unconfigured or unavailable, its verdict is reported as unavailable without corrupting active verifiers.
- **Mock Mode Independence**: In mock mode (`LLM_MODE=mock`), deterministic mock clients are used so that offline evaluation and continuous integration run without external API dependencies.

---

## 6. Web Evidence Scope & Retrieval Boundaries

Web Evidence is an **independent external verification pipeline** running concurrently with MetaQA:
- **Tavily Dependency & API Limits**: Live external search requires network connectivity and a valid `TAVILY_API_KEY`. Verification is capped by request budgets (`WEB_MAX_CLAIMS=3`, `WEB_MAX_SEARCHES=3`).
- **Targeted Search, Not Universal Web Crawl**: The system searches targeted queries per claim; it does not crawl the entire internet. Niche or newly breaking facts may return sparse or inconclusive snippets.
- **Rule-Based Question Classification**: Question-type classification relies on pattern-matching heuristics, which can occasionally misclassify hybrid or ambiguous prompts.
- **Preferred Sources Do Not Guarantee Truth**: Routing toward preferred categories (`.gov`, NASA, Britannica) optimizes search relevance, but a domain is never treated as an automatic truth oracle.
- **Evidence Insufficiency Is Not Hallucination**: If snippets are missing or inconclusive, the claim is labeled `INSUFFICIENT_EVIDENCE`. Insufficient evidence is **never** treated as proof of hallucination.
- **Heuristic Combined Risk**: The application-level Combined Hallucination Risk is an engineering heuristic combining internal consistency and external evidence. It is **not** a calibrated statistical probability.

---

## 7. Research Prototype Status

- VeriFact is an academic research prototype designed to investigate metamorphic consistency, multi-model peer review, and evidence-grounded verification.
- It is not a commercial, production-hardened fact-checking platform and should not be used as the sole arbiter of truth in safety-critical medical, legal, or financial applications.
- Background verification uses FastAPI's in-process `BackgroundTasks` with `asyncio.gather`. Restarting the backend during an active detection terminates in-flight background analyses.
