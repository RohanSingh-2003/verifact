# Interview & Oral Defense Guide

This guide provides crisp, technically rigorous, and verbally natural answers to common interview, oral examination, and project evaluation questions regarding VeriFact.

---

## Elevator Pitches

### 30-Second Explanation
> "VeriFact is a hallucination detection framework for Large Language Models. MetaQA tests internal semantic consistency with synonym and antonym mutations of an answer's core claims, then scores the result deterministically. Independently, Web Evidence checks extracted factual claims against retrieved Tavily snippets and labels them SUPPORTED, CONTRADICTED, or INSUFFICIENT_EVIDENCE. The two signals are synthesized side-by-side in a Verification Summary without an artificial fused percentage. It runs locally with Ollama and Gemma 4:26b, showing the answer immediately while verification proceeds in the background."

### 60-Second Explanation
> "Large Language Models often produce confident, fluent statements that are factually wrong. VeriFact addresses this with two complementary, independent verification layers.
> 
> When a user asks a question, Gemma 4:26b generates a base answer that the user sees immediately. In parallel, VeriFact executes two background pipelines:
> 1. MetaQA extracts 3–4 core claims and generates paired mutations: synonyms (which a consistent model should accept) and antonyms (which a consistent model should reject). An independent verifier labels each mutation YES, NO, or NOT SURE. VeriFact's mathematical engine averages these contributions into a 0.0-to-1.0 hallucination score, classifying the output as Reliable or Hallucinated at threshold 0.5.
> 2. Web Evidence classifies the question, routes to preferred trusted sources, retrieves snippets via Tavily, and labels each claim as supported, contradicted, or insufficient evidence.
> 
> The final Verification Summary presents both perspectives clearly without combining them into a single arbitrary score."

### 2-Minute Technical Explanation
> "The technical stack consists of a React 19 and Vite frontend, a FastAPI backend, and an SQLite database for persistence. 
> 
> In traditional pipelines, detection latency on 26B models blocks the user. VeriFact solves this with a progressive lifecycle: `POST /api/detect` produces the answer and returns an `answer_ready` status in seconds. FastAPI's `BackgroundTasks` executes MetaQA and Web Evidence concurrently via `asyncio.gather(..., return_exceptions=True)`. The client polls `GET /api/runs/{id}` to progressively render mutation rows, evidence snippets, and live verdicts.
> 
> In MetaQA, verifier outputs parse into YES, NO, or NOT SURE (fallback on parse error). Synonym YES gives 0 contribution, NO gives 1.0; antonym YES gives 1.0, NO gives 0; NOT SURE gives 0.5. The mean determines whether the answer is Reliable (<0.5) or Hallucinated (≥0.5).
> 
> In Web Evidence, questions are routed to preferred domain categories (science, government, news, statistics, medicine) to improve retrieval quality. Snippets are retrieved via Tavily, and claims are verified solely against snippet text. Insufficient evidence is strictly never treated as a hallucination.
> 
> Both signals are synthesized in the Verification Summary side-by-side (AGREE, DISAGREE, BOTH_CONCERNING, WEB_INSUFFICIENT, or PARTIAL)."

---

## Detailed Question & Answer Index

### 1. What is VeriFact?
**Answer**: VeriFact is an LLM hallucination detection framework that combines reference-free MetaQA metamorphic testing with targeted external Web Evidence verification.

### 2. What problem does it solve?
**Answer**: It detects fact-conflicting hallucinations without relying on self-confirmation prompts. MetaQA probes metamorphic consistency; Web Evidence grounds claims in retrieved snippets. Lack of web evidence is never treated as proof of hallucination.

### 2b. How do MetaQA and Web Evidence relate?
**Answer**: They are independent. MetaQA is reference-free consistency testing. Web Evidence classifies the question type, prefers relevant source categories, and checks claims against Tavily snippets. A Verification Summary reports whether the signals agree or disagree. Preferred sources are not a truth oracle, and VeriFact does not invent a combined hallucination percentage.

### 3. What is MetaQA?
**Answer**: MetaQA is a metamorphic testing methodology for question answering. It tests whether an answer maintains semantic consistency when perturbed into meaning-preserving (synonym) and meaning-reversing (antonym) restatements.

### 4. What is a mutation?
**Answer**: A mutation is a controlled transformation of a factual claim extracted from the generated answer. It tests how the model behaves under controlled semantic variations.

### 5. Why synonym mutations?
**Answer**: A synonym mutation rephrases the claim while preserving its meaning. A consistent model must recognize that the rephrased claim is supported (`YES`). If it answers `NO`, it indicates fragile knowledge and scores as an inconsistency ($c_i = 1.0$).

### 6. Why antonym mutations?
**Answer**: An antonym mutation inverts or contradicts the claim. A consistent model must reject the contradiction (`NO`). If it answers `YES`, it has agreed with contradictory assertions of its own claim, indicating severe hallucination ($c_i = 1.0$).

### 7. How does verification work?
**Answer**: Each mutated statement is sent to the verifier LLM with the original question and answer. Crucially, the verifier is never told whether the statement is a synonym or an antonym, nor what verdict is expected. The verifier outputs `YES`, `NO`, or `NOT SURE`.

### 8. How is the hallucination score calculated?
**Answer**: It is the arithmetic mean of individual mutation contributions:
- Synonym: `YES` = 0.0, `NO` = 1.0, `NOT SURE` = 0.5
- Antonym: `YES` = 1.0, `NO` = 0.0, `NOT SURE` = 0.5
- Aggregate score: $H = \frac{1}{N} \sum c_i \in [0.0, 1.0]$.
If $H \ge 0.5$, the answer is classified as **Hallucinated**; otherwise **Reliable**.

### 9. Why did you use Gemma 4:26b?
**Answer**: Gemma 4:26b offers strong open-weights reasoning and factual capabilities that can be executed locally on workstation hardware, providing high generative quality without proprietary cloud APIs.

### 10. Why Ollama?
**Answer**: Ollama provides a reliable local runtime for model weights, handles GPU offloading, and exposes standard API endpoints. We use its native `/api/chat` with `think: false` to ensure concise JSON outputs without wasting tokens on hidden reasoning loops.

### 11. Why local inference?
**Answer**: Local inference guarantees complete data privacy, eliminates ongoing API costs, avoids third-party rate limits, and allows offline reproducible research.

### 12. Does MetaQA prove real-world factual correctness?
**Answer**: No. MetaQA evaluates **semantic self-consistency**. If a model generates an internally consistent fictional story and consistently rejects contradictions to that story, MetaQA measures high consistency. It detects contradictions, not physical truth. This is precisely why VeriFact includes the parallel Web Evidence pipeline.

### 13. What are the limitations of the current system?
**Answer**: 
1. 26B inference is compute-intensive locally.
2. An internally consistent but universally false hallucination can receive a low MetaQA score (mitigated by Web Evidence).
3. Mutation generation quality depends on the LLM's instruction-following ability.
4. Web Evidence depends on Tavily API limits and search snippet availability.
5. The system is an academic research prototype, not a commercial fact-checker.

### 14. What are the planned future extensions?
**Answer**: Planned extensions include principled multi-signal statistical fusion models (rather than naive averaging), dynamic retrieval-augmented mutation generation, browser extensions for on-page text verification, and expanded multi-model benchmark evaluation suites.
