# Project Description: VeriFact

## 1. Executive Summary

**VeriFact: Verify what AI says.**

VeriFact is a research-oriented hallucination detection system that combines the **MetaQA** metamorphic testing methodology with an independent **Web Evidence** verification layer to identify **fact-conflicting hallucinations** in Large Language Model (LLM) outputs. Running locally using **Ollama** and **Gemma 4:26b**, VeriFact decouples answer generation from verification through an interactive progressive workflow: users view the AI-generated answer immediately, while the system creates semantic mutations, queries trusted external sources in parallel, and deterministically presents a side-by-side Verification Summary.

---

## 2. Problem Statement

Large Language Models (LLMs) frequently generate answers that appear authoritative and syntactically flawless, yet contain subtle or overt factual errors—commonly known as **hallucinations**.

In high-stakes domains (medicine, law, education, technical research), identifying whether an AI-generated answer is factually dependable is critical. However, automated hallucination detection faces major hurdles:
1. **Self-Confirmation Bias**: Asking an LLM whether its own answer is true typically results in affirmative sycophancy. The model tends to reinforce its own errors rather than dispute them.
2. **Computational & Retrieval Noise**: Relying solely on unstructured web search or RAG pipelines can introduce noisy, outdated, or conflicting third-party snippets.
3. **Reference-Free vs. Evidence Grounding Gap**: An internal consistency check alone (like MetaQA) cannot detect a model consistently repeating a widespread real-world falsehood, while external search alone cannot probe the semantic stability of the model's internal representations.

---

## 3. The VeriFact Dual-Pipeline Architecture

VeriFact solves this by executing two independent, complementary verification layers:

```text
User Question
      ↓
Ollama / Gemma 4:26b generates AI answer
      ↓
      ┌───────────────────────┐
      │                       │
      ↓                       ↓
   MetaQA              Web Evidence
      │                       │
      ├─ Gemma 4:26b:         ├─ Question classification
      │  Synonym mutations    ├─ Claim extraction
      │  Antonym mutations    ├─ Trusted-source routing
      │                       ├─ Tavily search
      ├─ Gemini API:          └─ Evidence verification
      │  Mutation verifier
      │
      └─ VeriFact Engine:
         MetaQA score
      ↓                       ↓
      └──────────┬────────────┘
                 ↓
        Verification Summary
```

The cross-model configuration allows the same generated answer and mutation set to be verified by a different LLM, enabling comparison between same-model and cross-model verifier behavior. MetaQA and Web Evidence are **strictly independent signals**. The final **Verification Summary** reports agreement/disagreement descriptively (`AGREE`, `DISAGREE`, `BOTH_CONCERNING`, `WEB_INSUFFICIENT`, `PARTIAL`). There is no arbitrary combined hallucination percentage.

---

## 4. Methodology Deep-Dive

### Pipeline 1: MetaQA (Internal Semantic Consistency)
1. **Atomic Claim Extraction**: Isolates 3–4 core factual claims from the candidate answer.
2. **Synonym Mutations (Meaning-Preserving)**: Rephrased assertions that preserve the truth value of the original claim. A consistent model must agree (`YES`).
3. **Antonym Mutations (Meaning-Reversing)**: Controlled inversions or negations that contradict the original claim. A consistent model must reject (`NO`).
4. **Isolated Verification**: Evaluates each mutated statement without prompt leakage (the verifier is never told the mutation type or expected verdict).
5. **Deterministic Scoring**:
   - Synonym: `YES` = 0.0, `NO` = 1.0, `NOT SURE` = 0.5.
   - Antonym: `YES` = 1.0, `NO` = 0.0, `NOT SURE` = 0.5.
   - Aggregate Hallucination Score: $H = \frac{1}{N}\sum_{i=1}^N c_i \in [0.0, 1.0]$.
   - Classification: $H \ge 0.5 \implies$ **Hallucinated**; $H < 0.5 \implies$ **Reliable**.

### Pipeline 2: Web Evidence (External Grounding)
1. **Important Claim Extraction**: Extracts testable factual assertions while filtering subjective opinions, greetings, and vague filler.
2. **Question-Type Classification**: Categorizes the user's question (science, government, current events, statistics, technology, medicine, general facts, academic research).
3. **Trusted-Source Routing**: Selects category-specific preferred domains to improve evidence relevance:
   - General facts → Britannica, Wikipedia, institutional encyclopedias
   - Science & space → NASA, NIH, Nature, Science, universities
   - Government & policy → Official government (`.gov`) portals, regulatory agencies
   - Current events → Reuters, AP News, BBC, major news outlets
   - Statistics → World Bank, UN, national census agencies, OECD
   - Technology → Official documentation, MDN, standard bodies
   - Medicine & health → WHO, CDC, PubMed, Cochrane
   - Academic research → JSTOR, arXiv, university archives (`.edu`)
4. **Tavily Search**: Executes targeted Basic Search per claim within configured credit caps. Automatically broadens search if preferred sources return empty.
5. **Snippet Verification**: Evaluates claims strictly against retrieved snippets → `SUPPORTED`, `CONTRADICTED`, or `INSUFFICIENT_EVIDENCE`.
6. **Web Consistency Score**: Average claim contribution (`SUPPORTED` = 1.0, `INSUFFICIENT_EVIDENCE` = 0.5, `CONTRADICTED` = 0.0). Evidence insufficiency is **never** treated as a hallucination.

---

## 5. Cloud-API-Only Architecture & Gemma 4:26B Implementation

- **Cloud-Only Inference**: VeriFact uses cloud/API-based LLM inference. Gemma 4:26B is accessed through Ollama Cloud (`https://ollama.com/api`); no local Ollama installation is required.
- **Reasoning Control (`think: false`)**: Gemma thinking models spend substantial token budgets on internal reasoning traces. VeriFact configures the Ollama Cloud `/api/chat` client with `think: false` to guarantee well-formed, deterministic JSON outputs within concise token limits.
- **Progressive UI Architecture**: VeriFact's progressive design presents the generated answer immediately upon completion (`answer_ready`), then runs MetaQA and Web Evidence as independent parallel pipelines. Failure of one verification branch does not hide the answer or cancel the other branch.
- **Mock Mode for Development**: Full deterministic mock support allows running the complete suite of automated backend unit tests and fast UI demonstrations without requiring live API keys.

---

## 6. Current Limitations

1. **Semantic Consistency vs. Objective Reality**: MetaQA evaluates whether the model contradicts itself. If a model consistently reinforces a factual error under both synonym and antonym transformations, the MetaQA score reflects high consistency.
2. **Local Inference Latency**: Running multiple verifications on 26B models requires capable GPU resources or patient CPU execution.
3. **Mutation Generation Fragility**: Prompt-based mutation generation may occasionally yield sentence fragments or duplicates; VeriFact filters these with heuristics and retry rounds, but generation quality remains model-dependent.
4. **Search Coverage & API Budgets**: External search is bounded by Tavily API limits and snippet availability. Preferred sources improve quality but do not guarantee physical truth.

---

## 7. Previous Research Investigation (Offline 2×2 Studies)

Prior research with VeriFact explored same-model versus cross-model verifier behaviors ($A \to A, A \to B, B \to A, B \to B$) with frozen mutation sets to isolate verifier calibration confounds. That study was completed as an offline investigation and is preserved in [`docs/final_results_lock.md`](final_results_lock.md) and automated backend test suites (`test_experiments.py`), leaving the user-facing product cleanly focused on interactive dual-pipeline hallucination detection.
