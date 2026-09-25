# Project Description: VeriFact

## 1. Executive Summary

VeriFact is a research-oriented hallucination detection system that implements the **MetaQA** metamorphic testing methodology to identify **fact-conflicting hallucinations** in Large Language Model (LLM) outputs. Running locally using **Ollama** and **Gemma 4:26b**, VeriFact decouples answer generation from metamorphic verification through an interactive progressive workflow: users view the AI-generated answer immediately, while the system creates semantic mutations, verifies consistency in the background, and deterministically computes a hallucination score.

---

## 2. Problem Statement

Large Language Models (LLMs) frequently generate answers that appear authoritative and syntactically flawless, yet contain subtle or overt factual errors—commonly known as **hallucinations**.

In high-stakes domains (medicine, law, education, technical research), identifying whether an AI-generated answer is factually dependable is critical. However, automated hallucination detection faces major hurdles:
1. **Self-Confirmation Bias**: Asking an LLM whether its own answer is true typically results in affirmative sycophancy. The model tends to reinforce its own errors.
2. **Computational Expense of External Search**: Continually querying external search engines or vector databases incurs latency, financial cost, rate limits, and vulnerability to outdated or noisy search indices.
3. **Reference-Free Verification Need**: In many environments, an external reference or ground-truth document is unavailable at query time.

---

## 3. The VeriFact Solution: MetaQA-Based Detection

VeriFact addresses this problem through **metamorphic testing**. Instead of asking the model for self-validation or requiring external databases, VeriFact tests the **semantic consistency** of the model's knowledge under controlled linguistic mutations:

```text
The Problem: LLM generates fluent but fact-conflicting statements
                              ↓
The Failure of Direct Checking: Asking "Are you right?" triggers self-confirmation bias
                              ↓
The VeriFact Approach: Probe internal consistency using metamorphic mutations
                              ↓
Step 1: Extract atomic core claims from the base answer
                              ↓
Step 2: Generate synonym (meaning-preserving) & antonym (meaning-reversing) mutations
                              ↓
Step 3: Ask the verifier whether each statement is supported (YES / NO / NOT SURE)
                              ↓
Step 4: Deterministically score inconsistencies using the MetaQA matrix
                              ↓
Step 5: Classify answer as Reliable or Hallucinated against a calibrated threshold
```

---

## 4. Methodology Deep-Dive

### Mutation Generation
From the generated answer, VeriFact isolates 3–4 core factual claims. For each claim, it generates:
- **Synonym Mutations**: Rephrased assertions that preserve the truth value of the original claim. A consistent model must agree (`YES`).
- **Antonym Mutations**: Controlled inversions or negations that contradict the original claim. A consistent model must reject (`NO`).

### Independent Verification
The verifier evaluates each mutated statement without knowing whether it is a synonym or an antonym, and without access to the expected verdict. Allowed outputs are strictly `YES`, `NO`, or `NOT SURE`.

### Deterministic Scoring
Scoring is performed by VeriFact’s mathematical engine—not by prompting an LLM to evaluate itself:
- **Synonym Contribution**: `YES` = 0.0 (consistent), `NO` = 1.0 (inconsistent), `NOT SURE` = 0.5.
- **Antonym Contribution**: `YES` = 1.0 (inconsistent), `NO` = 0.0 (consistent), `NOT SURE` = 0.5.
- **Aggregate Hallucination Score**: Arithmetic mean of contributions:
  $$H = \frac{1}{N}\sum_{i=1}^N c_i \quad \in [0.0, 1.0]$$
- **Classification**: With default threshold $\theta = 0.5$:
  - $H \ge 0.5 \implies$ **Hallucinated**
  - $H < 0.5 \implies$ **Reliable**

---

## 5. Local Ollama & Gemma 4:26b Implementation

- **Hardware Autonomy**: VeriFact integrates directly with local **Ollama** instances (`http://localhost:11434`), executing Google's **Gemma 4:26b** model.
- **Reasoning Control (`think: false`)**: Gemma thinking models spend substantial token budgets on internal reasoning traces. VeriFact configures the native Ollama `/api/chat` client with `think: false` to guarantee well-formed, deterministic JSON outputs within concise token limits.
- **Progressive UI Architecture**: Because 26B inference can take tens of seconds locally, VeriFact's progressive design presents the generated answer immediately upon completion (`answer_ready`), then streams mutation generation and verification progress in the background on the same run.
- **Mock Mode for Development**: Full deterministic mock support allows running the complete suite of 162 automated backend unit tests and fast UI demonstrations without requiring GPU resources.

---

## 6. Current Limitations

1. **Semantic Consistency vs. Objective Reality**: MetaQA evaluates whether the model contradicts itself. If a model consistently believes and reinforces a factual error under both synonym and antonym transformations, the score will reflect high consistency.
2. **Local Inference Latency**: Running multiple verifications on 26B models requires capable GPU resources or patient CPU execution.
3. **Mutation Generation Fragility**: Prompt-based mutation generation may occasionally yield sentence fragments or duplicates; VeriFact filters these with heuristics and retry rounds, but generation quality remains model-dependent.

---

## 7. Planned Future Extension: External Web Evidence

A planned future version of VeriFact will introduce an external **Web Evidence** pipeline:
- Extract factual assertions from the base answer.
- Query external search APIs (e.g., Tavily or SerpAPI) for reputable sources.
- Extract relevant snippets and evaluate claims as **SUPPORTED**, **CONTRADICTED**, or **INSUFFICIENT EVIDENCE**.
- Contrast internal metamorphic consistency scores against external retrieval evidence.

*(Note: In the current repository release, the system is strictly reference-free, and external search features are not implemented.)*
