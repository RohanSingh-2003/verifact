# Interview & Oral Defense Guide

This guide provides crisp, technically rigorous, and verbally natural answers to common interview, oral examination, and project evaluation questions regarding VeriFact.

---

## Elevator Pitches

### 30-Second Explanation
> "VeriFact is an explainable hallucination detection framework for Large Language Models. When a user asks a factual question, Gemma 4:26B generates an answer that the user sees immediately. In the background, VeriFact evaluates the answer across three concurrent branches: MetaQA tests internal semantic consistency using synonym and antonym mutations; independent cloud models (Gemini, GLM, Qwen, OpenRouter) conduct direct-answer peer review; and Web Evidence checks claims against retrieved Tavily search snippets. The signals are synthesized in an Overall Assessment without corrupting the underlying research metrics."

### 60-Second Explanation
> "Large Language Models often produce fluent, confident answers that contradict established facts. Asking a model directly 'Did you hallucinate?' fails because of self-confirmation bias and sycophancy.
> 
> VeriFact addresses this with structural separation:
> 1. **Answer-First Responsiveness**: Gemma 4:26B generates the candidate answer via Ollama Cloud, rendered immediately so the user never waits on lengthy verification.
> 2. **Three Concurrent Verification Branches**:
>    - **MetaQA Metamorphic Testing**: Claims are extracted and perturbed into meaning-preserving synonyms and meaning-reversing antonyms, verified across a non-Gemma model pool and scored deterministically.
>    - **Direct-Answer Multi-Model Peer Review**: Independent peer models review Gemma's answer against full context, surfacing consensus and contradictory claims.
>    - **Web Evidence Grounding**: The question domain is classified, targeted queries search authoritative sources via Tavily, and claims are checked against retrieved snippets.
> 3. **Synthesis**: The Overall Assessment contrasts internal consistency with external evidence side-by-side, providing transparent, explainable verification."

### 2-Minute Technical Explanation
> "The technical stack consists of a React 19 and Vite frontend, a FastAPI backend service, an SQLite persistence layer, and a multi-provider cloud LLM abstraction layer.
>
> Because verifying natural language claims across multiple models requires multiple API round-trips, VeriFact decouples answer generation from verification. `POST /api/detect` invokes Gemma 4:26B, writes the record to SQLite with status `answer_ready`, and returns immediately. FastAPI background workers then launch three concurrent verification branches via `asyncio.gather(..., return_exceptions=True)`. The client polls `GET /api/runs/{id}` to progressively render mutation tables, peer consensus badges, and evidence source cards.
> 
> In MetaQA, verifier outputs parse into YES, NO, or NOT SURE. Synonym YES yields 0.0 penalty, NO yields 1.0; antonym YES yields 1.0, NO yields 0.0; NOT SURE yields 0.5. The mean determines whether the answer is Reliable (<0.5) or Hallucinated (≥0.5).
> 
> In Multi-Model Peer Review, non-Gemma models evaluate Gemma's full answer directly and return structured verdicts, confidence ratings, and contradictory claim flags.
> 
> In Web Evidence, questions are routed to preferred domain categories (science, government, statistics, medicine) to optimize retrieval relevance. Snippets are retrieved via Tavily, and claims are verified solely against snippet text. Crucially, lack of search evidence is never treated as a hallucination.
> 
> Finally, the Verification Summary presents both perspectives clearly without inventing an artificial fused score."

---

## Detailed Question & Answer Index

### 1. What is VeriFact?
**Answer**: VeriFact is an explainable LLM hallucination detection framework that combines reference-free MetaQA metamorphic testing, direct-answer multi-model peer review, and targeted external Web Evidence grounding.

### 2. What problem does it solve?
**Answer**: It detects fact-conflicting hallucinations without relying on naive self-reflection prompts. MetaQA evaluates whether the model's underlying knowledge state is semantically stable; independent peer review surfaces model disagreement; and Web Evidence grounds claims in retrieved real-world snippets.

### 3. How do MetaQA, Peer Review, and Web Evidence relate?
**Answer**: They are independent verification vectors running concurrently:
- **MetaQA** is reference-free and evaluates internal semantic consistency under controlled perturbations.
- **Peer Review** evaluates direct answer agreement across heterogeneous independent cloud models.
- **Web Evidence** retrieves external text snippets and checks factual alignment with authoritative sources.
The Overall Assessment presents these perspectives side-by-side.

### 4. What is MetaQA metamorphic testing?
**Answer**: MetaQA is a metamorphic testing methodology for natural language. It tests whether an answer maintains semantic invariance when its factual claims are restated in meaning-preserving (synonym) and meaning-reversing (antonym) forms.

### 5. Why synonym and antonym mutations?
**Answer**:
- **Synonym mutation**: Preserves the claim's meaning. A consistent model must recognize that the claim is supported (`YES`). Saying `NO` indicates brittle knowledge and incurs an inconsistency penalty ($c_i = 1.0$).
- **Antonym mutation**: Inverts or negates the claim. A consistent model must reject the contradiction (`NO`). Saying `YES` indicates severe hallucination and incurs an inconsistency penalty ($c_i = 1.0$).

### 6. How does mutation verification work?
**Answer**: Each mutated statement is sent to the verifier pool with the question and candidate answer. The verifier is **never told** whether the statement is a synonym or an antonym, nor the expected verdict or ground truth.

### 7. How is the MetaQA hallucination score calculated?
**Answer**: It is the arithmetic mean of individual mutation contributions:
- Synonym: `YES` = 0.0, `NO` = 1.0, `NOT SURE` = 0.5
- Antonym: `YES` = 1.0, `NO` = 0.0, `NOT SURE` = 0.5
- Aggregate score: $H = \frac{1}{N} \sum c_i \in [0.0, 1.0]$.
If $H \ge 0.5$, the answer is classified as **Hallucinated**; otherwise **Reliable**.

### 8. Why is Gemma 4:26B the fixed answer generator?
**Answer**: Gemma 4:26B provides high-quality open-weights factual reasoning. Designating it as the permanent answer generator establishes a controlled, reproducible baseline for all evaluations and verification comparisons.

### 9. How are LLM calls executed? Is inference local or cloud-based?
**Answer**: VeriFact uses **100% cloud-based inference** over official provider APIs:
- Gemma 4:26B runs via the official **Ollama Cloud API** (`https://ollama.com/api`).
- Verifier models run via official cloud APIs: Google Gemini (`gemini-3.8-flash`), Cloudflare Workers AI (`glm-4.7-flash`), Groq (`qwen-2.5-32b`), and OpenRouter (`liquid-lfm-2.5`).
No local GPU hardware or local Ollama daemon is required.

### 10. Why is `think: false` enforced on Gemma?
**Answer**: Gemma thinking models spend substantial token budgets outputting internal reasoning traces. VeriFact enforces `think: false` on the Ollama Cloud `/api/chat` client to guarantee concise, deterministic JSON outputs within fixed token limits (`LLM_ANSWER_MAX_TOKENS=350`).

### 11. Does MetaQA prove physical factual truth?
**Answer**: No. MetaQA evaluates **semantic self-consistency**. If a model generates an internally consistent myth and consistently defends that myth under synonym paraphrases while rejecting antonym inversions, MetaQA will measure high consistency ($H = 0.0$). This is precisely why VeriFact includes the parallel Web Evidence pipeline to ground claims against real-world documents.

### 12. How does Web Evidence handle missing information?
**Answer**: If search snippets are missing or inconclusive, the claim is labeled **`INSUFFICIENT_EVIDENCE`**. Crucially, lack of evidence is **never** treated as a hallucination.

### 13. What is the historical 2×2 study mentioned in the repository?
**Answer**: Prior to release, an offline 2×2 factorial study evaluated same-model versus cross-model verifier behaviors ($A \to A, A \to B, B \to A, B \to B$). That study was executed in mock mode (`58baff20-fb86-4f43-b20e-895a086ceb6b`), and the intended live configuration was frozen as not executed. The batch experiment runner was subsequently retired, and the mock run is preserved as an immutable historical record in `experiments/` and `docs/final_results_lock.md`.

### 14. What automated tests validate the system?
**Answer**: VeriFact includes comprehensive test suites across both backend and frontend. At the time of this documentation audit, the backend test suite contained **458 collected test items** (`pytest`), executing offline with deterministic mock fixtures in ~15–20 seconds without requiring live API keys.
