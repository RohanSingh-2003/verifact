# Project Description: VeriFact

## 1. Executive Summary

**VeriFact: Verify what AI says.**

VeriFact is a research-informed hallucination detection and verification system that combines the **MetaQA** metamorphic testing methodology, direct-answer **Multi-Model Peer Review**, and an independent **Web Evidence** verification layer to identify **fact-conflicting hallucinations** in Large Language Model (LLM) outputs. Operating via cloud-hosted API providers—using **Gemma 4:26B** via the **Ollama Cloud API** (`https://ollama.com/api`) as the dedicated answer and mutation generator alongside a diverse pool of cloud verifiers (Google Gemini, Cloudflare Workers AI, Groq, OpenRouter)—VeriFact decouples answer generation from verification through an interactive progressive workflow: users view the AI-generated answer immediately, while the system concurrently evaluates semantic consistency, multi-model consensus, and external web evidence.

---

## 2. Problem Statement

Large Language Models (LLMs) frequently generate answers that appear authoritative and syntactically flawless, yet contain subtle or overt factual errors—commonly known as **hallucinations**.

In high-stakes domains (medicine, law, education, technical research), identifying whether an AI-generated answer is factually dependable is critical. However, automated hallucination detection faces major hurdles:
1. **Self-Confirmation Bias**: Asking an LLM whether its own answer is true typically results in affirmative sycophancy. The model tends to reinforce its own errors rather than dispute them.
2. **Computational & Retrieval Noise**: Relying solely on unstructured web search or RAG pipelines can introduce noisy, outdated, or conflicting third-party snippets.
3. **Reference-Free vs. Evidence Grounding Gap**: An internal consistency check alone (like MetaQA) cannot detect a model consistently repeating a widespread real-world falsehood, while external search alone cannot probe the semantic stability of the model's internal representations.
4. **Single-Judge Fallibility**: Relying on a single verifier model can inherit that model's idiosyncratic blind spots or prompt sensitivities.

---

## 3. The VeriFact Multi-Branch Verification Architecture

VeriFact solves this by executing three independent, concurrent verification branches:

```text
User Question
      ↓
Ollama Cloud / Gemma 4:26B generates AI answer (answer_ready)
      ↓
      ├───────────────────────────────┬───────────────────────────────┐
      ↓                               ↓                               ↓
Branch 1: MetaQA               Branch 2: Peer Review          Branch 3: Web Evidence
      │                               │                               │
      ├─ Gemma 4:26B:                 ├─ Multi-Model Verifier Pool:   ├─ Question classification
      │  Synonym mutations            │  Gemini, Cloudflare,          ├─ Claim extraction
      │  Antonym mutations            │  Groq, OpenRouter             ├─ Trusted-source routing
      │                               │                               ├─ Tavily Search
      ├─ Multi-Model Verifier Pool:   ├─ Direct answer assessment     └─ Snippet verification
      │  Evaluates mutations          │  without seeing mutations        SUPPORTED / CONTRADICTED /
      │                               │                                  INSUFFICIENT_EVIDENCE
      └─ VeriFact Engine:             └─ VeriFact Engine:
         MetaQA Hallucination Score      Consensus & individual          Web Consistency Score
         θ = 0.5 classification          verdicts (YES / NO / UNCERTAIN)
      │                               │                               │
      └───────────────────────────────┼───────────────────────────────┘
                                      ↓
                         Comprehensive Verification Summary
                         - MetaQA Hallucination Card (0.0 to 1.0)
                         - Web Evidence Grounding Card (0.0 to 1.0)
                         - Independent Verdicts Card (Multi-Model Consensus)
                         - Combined Risk Card (Heuristic agreement assessment)
```

The multi-model configuration allows the candidate answer and its semantic mutations to be verified by diverse external models, mitigating single-model bias. MetaQA internal consistency, Multi-Model Peer Review, and Web Evidence Grounding remain **strictly independent signals**. The final **Verification Summary** reports agreement/disagreement descriptively (`AGREE`, `DISAGREE`, `BOTH_CONCERNING`, `WEB_INSUFFICIENT`, `PARTIAL`).

---

## 4. Methodology Deep-Dive

### Branch 1: MetaQA (Internal Semantic Consistency)
1. **Atomic Claim Extraction**: Isolates core factual claims from the candidate answer.
2. **Synonym Mutations (Meaning-Preserving)**: Rephrased assertions that preserve the truth value of the original claim. A consistent model must agree (`YES`).
3. **Antonym Mutations (Meaning-Reversing)**: Controlled inversions or negations that contradict the original claim. A consistent model must reject (`NO`).
4. **Isolated Verification**: Evaluates each mutated statement without prompt leakage (the verifier is never told the mutation type or expected verdict).
5. **Deterministic Scoring**:
   - Synonym: `YES` = 0.0, `NO` = 1.0, `NOT SURE` = 0.5.
   - Antonym: `YES` = 1.0, `NO` = 0.0, `NOT SURE` = 0.5.
   - Aggregate Hallucination Score: $H = \frac{1}{N}\sum_{i=1}^N c_i \in [0.0, 1.0]$.
   - Classification: $H \ge 0.5 \implies$ **Hallucinated**; $H < 0.5 \implies$ **Reliable**.

### Branch 2: Direct-Answer Multi-Model Peer Review
1. **Independent Evaluation**: Multiple external LLMs from the configured verifier pool evaluate the original generated answer directly, completely unconditioned by the mutation transformations.
2. **Isolated Prompting**: Verifiers receive only the user question and the candidate answer, outputting structured verdicts (`YES`, `NO`, `UNCERTAIN`) and confidence rationales.
3. **Multi-Model Consensus**: Compiles consensus metrics across the independent judges to highlight cross-model agreement or dissent.

### Branch 3: Web Evidence (External Grounding)
1. **Important Claim Extraction**: Extracts testable factual assertions while filtering subjective opinions, greetings, and filler text.
2. **Question-Type Classification**: Categorizes the user's question into domain buckets (science, government, current events, statistics, technology, medicine, general facts, academic research).
3. **Trusted-Source Routing**: Selects category-specific preferred domains to prioritize authoritative evidence:
   - General facts → Britannica, Wikipedia, institutional encyclopedias
   - Science & space → NASA, NIH, Nature, Science, universities
   - Government & policy → Official government (`.gov`) portals, regulatory agencies
   - Current events → Reuters, AP News, BBC, major news outlets
   - Statistics → World Bank, UN, national census agencies, OECD
   - Technology → Official documentation, MDN, standard bodies
   - Medicine & health → WHO, CDC, PubMed, Cochrane
   - Academic research → JSTOR, arXiv, university archives (`.edu`)
4. **Tavily Search**: Executes targeted search per claim within configured credit caps. Automatically broadens search if preferred sources return empty.
5. **Snippet Verification**: Evaluates claims strictly against retrieved snippets → `SUPPORTED`, `CONTRADICTED`, or `INSUFFICIENT_EVIDENCE`.
6. **Web Consistency Score**: Average claim contribution (`SUPPORTED` = 1.0, `INSUFFICIENT_EVIDENCE` = 0.5, `CONTRADICTED` = 0.0). Evidence insufficiency is **never** treated as a hallucination.

---

## 5. Cloud-API-Only Architecture & Gemma 4:26B Implementation

- **100% Cloud-Only Inference**: VeriFact uses cloud HTTPS API endpoints for all model interactions. Gemma 4:26B is accessed via the official Ollama Cloud API (`https://ollama.com/api`); no local Ollama daemon or local GPU hardware is required.
- **Reasoning Control (`think: false`)**: Large reasoning models spend substantial token budgets on internal chain-of-thought traces. VeriFact explicitly configures the Ollama Cloud `/api/chat` client with `think: false` to guarantee well-formed, deterministic JSON outputs within tight latency budgets.
- **Progressive Detection Architecture**: VeriFact's progressive design returns the generated answer immediately upon completion (`answer_ready`), then runs MetaQA, Peer Review, and Web Evidence concurrently in background tasks while the frontend polls for progressive updates. A transient failure in one verification branch does not hide the generated answer or abort other branches.
- **Mock Mode for Development & CI**: Full deterministic mock support (`MOCK_OLLAMA=true`, `MOCK_GEMINI=true`, `MOCK_TAVILY=true`, etc.) allows running the complete suite of backend unit tests and frontend workflows without live API keys or network latency.

---

## 6. Current Limitations

1. **Semantic Consistency vs. Objective Reality**: MetaQA evaluates whether the model contradicts itself. If a model consistently reinforces a factual falsehood under both synonym and antonym transformations, the MetaQA score reflects high consistency; external web evidence and peer review are required to catch such errors.
2. **Cloud API Latency & Rate Quotas**: Concurrent evaluations across multiple cloud providers incur HTTPS network round-trip overhead and are subject to upstream provider availability and rate limits.
3. **Mutation Generation Fragility**: Prompt-based mutation generation may occasionally yield sentence fragments or duplicates; VeriFact filters these with validation heuristics and retries, but generation quality remains model-dependent.
4. **Search Coverage & API Budgets**: External search is bounded by Tavily API limits and snippet availability. Preferred sources improve quality but do not guarantee exhaustive coverage of obscure facts.

---

## 7. Archival Research Investigation (Historical 2×2 Offline Studies)

Prior research with VeriFact explored same-model versus cross-model verifier behaviors ($A \to A, A \to B, B \to A, B \to B$) with frozen mutation sets to isolate verifier calibration confounds. That experimental runner and its associated endpoints have been retired. The historical mock study is preserved as an immutable archive in [`experiments/results/58baff20-fb86-4f43-b20e-895a086ceb6b/`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/experiments/results/58baff20-fb86-4f43-b20e-895a086ceb6b/) and documented in [`docs/final_results_lock.md`](file:///c:/Users/Rohan/Desktop/mini-project/verifact/docs/final_results_lock.md). The active application focuses exclusively on the interactive three-branch verification pipeline.
