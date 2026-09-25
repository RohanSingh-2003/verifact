# Interview & Oral Defense Guide

This guide provides crisp, technically rigorous, and verbally natural answers to common interview, oral examination, and project evaluation questions regarding VeriFact.

---

## Elevator Pitches

### 30-Second Explanation
> "VeriFact is a hallucination detection framework for Large Language Models. Instead of naively asking an LLM if its own answer is correct—which fails due to self-confirmation bias—VeriFact uses MetaQA metamorphic testing. It generates meaning-preserving (synonym) and meaning-reversing (antonym) mutations of the answer's core claims, asks a verifier whether each statement is supported, and deterministically computes a hallucination score. It runs locally using Ollama and Gemma 4:26b, with a progressive architecture that displays the AI answer immediately while running background verification on the same run."

### 60-Second Explanation
> "Large Language Models often produce confident, fluent statements that are factually wrong. VeriFact addresses this without needing external search engines or vector databases by probing metamorphic consistency.
> 
> When a user asks a question, Gemma 4:26b generates a base answer that the user sees immediately. In the background, VeriFact extracts 3–4 core claims and generates paired mutations: synonyms (which a consistent model should accept) and antonyms (which a consistent model should reject). An independent verifier labels each mutation YES, NO, or NOT SURE. VeriFact's mathematical engine averages these contributions into a 0.0-to-1.0 hallucination score, classifying the output as Reliable or Hallucinated at threshold 0.5. Everything runs locally on Ollama without API costs, and a separate 2×2 study scaffold evaluates same-model versus cross-model verifier behaviors."

### 2-Minute Technical Explanation
> "The technical stack consists of a React 19 and Vite frontend, a FastAPI backend, and an SQLite database for run and experiment persistence. 
> 
> In traditional pipelines, detection latency on 26B models blocks the user. VeriFact solves this with a progressive lifecycle: `POST /api/detect` produces the answer and returns an `answer_ready` status in seconds. FastAPI's `BackgroundTasks` continues MetaQA analysis on the event loop, transitioning through `generating_mutations`, `verifying_mutations`, `calculating_score`, and `completed`. The client polls `GET /api/runs/{id}` to progressively render mutation rows and live verdicts.
> 
> Mutation verification runs concurrently with bounded semaphores (`VERIFY_CONCURRENCY=3`). Verifier outputs parse into YES, NO, or NOT SURE (fallback on parse error). Synonym YES gives 0 contribution, NO gives 1.0; antonym YES gives 1.0, NO gives 0; NOT SURE gives 0.5. The mean determines whether the answer is Reliable (<0.5) or Hallucinated (≥0.5).
> 
> In addition to interactive detection, VeriFact includes a 2×2 experiment runner (A→A, A→B, B→A, B→B) with frozen mutation sets to evaluate verifier calibration. The repository's frozen pilot lock demonstrates pipeline mechanics in mock mode, while live interactive detection runs independently via local Ollama."

---

## Detailed Question & Answer Index

### 1. What is VeriFact?
**Answer**: VeriFact is a reference-free framework and web application that detects fact-conflicting hallucinations in LLM-generated answers using MetaQA metamorphic testing.

### 2. What problem does it solve?
**Answer**: It solves the problem of detecting factual hallucinations in LLMs without requiring external search engines, RAG pipelines, or direct self-reflection prompts that suffer from confirmation bias and sycophancy.

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
**Answer**: No. MetaQA evaluates **semantic self-consistency**. If a model generates an internally consistent fictional story and consistently rejects contradictions to that story, MetaQA measures high consistency. It detects contradictions, not physical truth.

### 13. What are the limitations of the current system?
**Answer**: 
1. 26B inference is compute-intensive locally.
2. An internally consistent but universally false hallucination can receive a low score.
3. Mutation generation quality depends on the LLM's instruction-following ability.
4. The system is currently an academic prototype, not a commercial fact-checker.

### 14. What is the next planned feature?
**Answer**: The next planned extension is an external **Web Evidence** pipeline to extract atomic claims, retrieve live web sources, and verify claims as **SUPPORTED**, **CONTRADICTED**, or **INSUFFICIENT EVIDENCE**, contrasting external verification with internal MetaQA consistency.
