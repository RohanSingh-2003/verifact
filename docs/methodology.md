# VeriFact Methodology

## 1. Problem Definition & The Limits of Self-Reflection

Large Language Models (LLMs) can generate fluent, grammatical text that contradicts established facts—a phenomenon termed **fact-conflicting hallucination**.

When attempting to detect hallucinations without external ground-truth datasets, a common intuition is to prompt the LLM directly: *"Is the above statement true?"* However, empirical research and software testing show that this approach is ineffective due to:
- **Self-Confirmation Bias**: Models exhibit high confidence in their own previous completions.
- **Sycophancy**: If a false premise is already embedded in the conversation context, models tend to confirm and elaborate upon the falsehood rather than dispute it.
- **Superficial Fluency**: Direct self-checking fails to distinguish between well-grounded knowledge and plausible-sounding fabulations.

---

## 2. The MetaQA Metamorphic Testing Principle

VeriFact implements **MetaQA**, a metamorphic testing methodology designed to evaluate hallucination by testing **internal consistency under semantic perturbation**:

Instead of directly asking if an answer is correct, MetaQA tests whether the model behaves coherently when the core claims of its answer are restated in meaning-preserving and meaning-reversing forms.

- **MetaQA** refers to the theoretical metamorphic testing method (claim extraction, synonym/antonym mutations, independent verification, and deterministic score aggregation).
- **VeriFact** is the software framework that implements this methodology into an interactive progressive web application, local Ollama engine, and independent Web Evidence verification layer.

---

## 3. Base Answer Generation

Given a factual user query, the generator model (`gemma4:26b` in live Ollama mode) produces a concise factual answer. 

- Ground-truth references are **never** provided to the prompt.
- In the interactive Detect pipeline, answer generation is decoupled from verification: the answer is stored and returned immediately to the frontend (`status: answer_ready`), allowing the user to read the AI's response while MetaQA and Web Evidence proceed **in parallel** on the same run. Either branch may fail or encounter rate limits without blocking the other or hiding the answer.

---

## 4. Metamorphic Mutation Generation

To ensure reliable, focused testing, VeriFact does not attempt to rewrite an entire multi-sentence answer in a single prompt. Instead, it extracts **3–4 atomic core factual claims** (`CoreClaim`) and generates paired mutations from those claims:

### Synonym Mutations (Meaning-Preserving)
- **Definition**: A restatement that preserves the semantic meaning and factual assertions of the original claim using different vocabulary, voice, or sentence structure.
- **Purpose**: Tests whether the model recognizes its own assertion when stated in alternate words.
- **Expected Verifier Verdict**: `YES` (Supported)

### Antonym Mutations (Meaning-Reversing)
- **Definition**: A restatement that deliberately inverts, negates, or alters key factual entities (names, dates, locations, quantities, relationships) to contradict the original claim.
- **Purpose**: Tests whether the model rejects a statement that directly conflicts with what it previously asserted.
- **Expected Verifier Verdict**: `NO` (Not Supported)

### Mutation Counts
- **Interactive Detect**: Uses **3 synonym + 3 antonym = 6 mutations** (`SYNONYM_COUNT=3`, `ANTONYM_COUNT=3`) to maintain responsive latency on local 26B parameter hardware.
- **Offline Research Studies**: Configured for 5 synonym + 5 antonym = 10 mutations during previous offline 2×2 study trials.

### Syntactic & Semantic Heuristic Gates
Every candidate mutation is validated by strict heuristic filters before being accepted:
- Must be a complete declarative sentence (minimum 5 words, maximum 35 words).
- Cannot be an interrogative or end with a question mark.
- Cannot contain explanatory prefixes (e.g., *"Synonym mutation:"*, *"This means that"*).
- Cannot be a no-op identical copy of the original claim.
- If mutations are missing, VeriFact executes partial retry rounds (up to 4 rounds) requesting only the deficit count.

---

## 5. Independent Mutation Verification & Cross-Model Setup

Each accepted mutation is submitted independently to the verifier LLM:
- **Cross-Model Verification Architecture**:
  - **Generator**: Ollama / Gemma 4:26B generates the base answer and creates all synonym and antonym mutations.
  - **Verifier**: Google Gemini API (`gemini-2.5-flash` by default) verifies each mutation.
  - **Scoring Engine**: VeriFact's deterministic scoring engine evaluates verdicts against programmatically derived expectations.
- **Why Cross-Model Verification Exists**:
  > "The cross-model configuration allows the same generated answer and mutation set to be verified by a different LLM, enabling comparison between same-model and cross-model verifier behavior."
  > 
  > *Note on Research Validity*: We do not claim that Gemini is inherently more accurate than Gemma, nor that this setup proves verifier bias. Rather, keeping the generated answer and mutation set fixed while switching the verification model enables rigorous empirical comparison between same-model ($M_1 \to M_1$) and cross-model ($M_1 \to M_2$) verification.
- **Prompt Isolation & Zero Information Leakage**:
  - The verifier receives: original question, candidate answer, and the single mutated statement.
  - The verifier is **never told**:
    - whether the statement is a synonym or an antonym
    - what the expected verdict is
    - the MetaQA scoring rules or thresholds
    - whether the original answer is considered reliable or hallucinated
    - any ground-truth answers
- **Programmatically Derived Expected Verdicts**:
  - Synonym mutation: Expected = `YES`
  - Antonym mutation: Expected = `NO`
  - Expected verdicts are derived strictly in code, never provided to the model.
- **Verdict Vocabulary**:
  - `YES`: The statement is supported by the candidate answer.
  - `NO`: The statement is not supported by (or contradicts) the candidate answer.
  - `NOT SURE`: The verifier cannot determine support, or returned ambiguous text.
- **No Silent Fallback**:
  - If Gemini API is unconfigured, rate-limited, or unavailable, MetaQA explicitly reports that Gemini verification is unavailable. It **never** silently substitutes Ollama as the verifier, preserving the scientific integrity of the cross-model experiment.
- **Robust Parser**: If the verifier output contains malformed formatting, it safely parses to `NOT SURE` with `parse_failed=True`.

---

## 6. Deterministic MetaQA Scoring

Scoring is computed entirely in Python code—not by prompting an LLM to evaluate the run.

### 1. Contribution Matrix
Each mutation $i$ receives a contribution score $c_i \in [0.0, 1.0]$ based on its mutation type and observed verifier verdict:

| Mutation Type | Observed: `YES` | Observed: `NO` | Observed: `NOT SURE` |
| :--- | :---: | :---: | :---: |
| **Synonym** (Expected: `YES`) | **0.0** (Consistent) | **1.0** (Inconsistent) | **0.5** (Uncertain) |
| **Antonym** (Expected: `NO`) | **1.0** (Inconsistent) | **0.0** (Consistent) | **0.5** (Uncertain) |

### 2. Hallucination Score
The aggregate hallucination score $H$ is the arithmetic mean of all individual mutation contributions $c_i$:

$$H = \frac{1}{N} \sum_{i=1}^N c_i \quad \text{clamped to } [0.0, 1.0] \text{ and rounded to 4 decimals}$$

### 3. Classification
Given calibrated threshold $\theta$ (default $\theta = 0.5$):

$$\text{Classification} = \begin{cases} \mathbf{Hallucinated} & \text{if } H \ge \theta \\ \mathbf{Reliable} & \text{if } H < \theta \end{cases}$$

- Verifier rationales are stored for user inspection and explainability; they never influence the mathematical score.
- Classification names are strictly **Reliable** or **Hallucinated**.

---

## 7. Important Research Boundary: Semantic Consistency vs. Real-World Truth

> [!IMPORTANT]
> **Academic Integrity Notice:**
> MetaQA evaluates the **semantic self-consistency** of an LLM's generated output under controlled perturbations.
>
> It does **not** independently prove that an answer is factual in the physical world. If a model generates an internally consistent fictional story and consistently rejects antonym inversions of that fiction, MetaQA will record high consistency ($H = 0.0$).
>
> MetaQA itself remains **reference-free**. VeriFact’s separate **Web Evidence** pipeline retrieves external sources (Tavily) and reports claim-level SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE. Those results are external evidence reports, not an absolute truth oracle, and are not merged into the MetaQA score.

---

## 8. Web Evidence Verification

Independent of MetaQA, after the AI answer is ready:

```text
Generated AI Answer
        ↓
Important Claim Extraction (filters opinions, greetings, filler)
        ↓
Question-Type Classification (rule-based)
        ↓
Trusted-Source Strategy (category-specific preferred domains)
        ↓
Tavily Search (targeted query per claim within credit budget)
        ↓
Evidence Retrieval & Snippet Extraction
        ↓
Claim Verification (strictly from retrieved snippets)
        ↓
Verdict Assignment: SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE
        ↓
Web Evidence Consistency Score
```

### Trusted Source Routing
The system classifies the user's question into domain categories and prioritizes trusted source categories:
- **General facts** → Britannica, Wikipedia, institutional references
- **Science & space** → NASA, NIH, scientific organizations, universities
- **Government & policy** → Official government (`.gov`) and regulatory sources
- **Current events** → Reputable news agencies, primary wire sources
- **Statistics** → Official statistical agencies, original datasets
- **Technology** → Official documentation, MDN, standard bodies
- **Medicine & health** → WHO, NIH, CDC, authoritative medical institutions
- **Academic research** → Papers, university repositories, recognized research sources

> [!NOTE]
> Preferred sources are used to improve retrieval relevance and source quality. A domain is not automatically considered truthful merely because it is preferred. If preferred domains return empty results, the search automatically broadens.

### Tavily's Role & Evidence Insufficiency
- Tavily provides targeted web search and snippet retrieval; the system does not crawl the entire web.
- Searches are credit-budgeted (`WEB_MAX_CLAIMS=3`, `WEB_MAX_SEARCHES=3`).
- **Evidence Insufficiency Rule**: Missing or inconclusive snippets yield **`INSUFFICIENT_EVIDENCE`**. Insufficient evidence is **never** treated as a hallucination.

### Web Evidence Consistency Score
A deterministic claim-level summary:

$$\text{Web Consistency Score} = \frac{1}{N}\sum_{i=1}^{N} c_i$$

where each claim contribution is:
- `SUPPORTED`: **1.0**
- `INSUFFICIENT_EVIDENCE`: **0.5**
- `CONTRADICTED`: **0.0**

Higher values mean more checked claims were supported by retrieved snippets. This is **not** a calibrated hallucination probability and is **never** averaged with the MetaQA score.

---

## 9. Verification Summary (Side-by-Side Signal Synthesis)

After both pipelines finish (or one fails/becomes unavailable), VeriFact synthesizes a **Verification Summary** that contrasts MetaQA and Web Evidence:
- `AGREE`: Both internal consistency and external sources indicate reliability or both indicate hallucination.
- `DISAGREE`: Internal consistency conflicts with external evidence (e.g., model is internally consistent but contradicted externally, or vice versa).
- `BOTH_CONCERNING`: Both internal inconsistency and external contradictions are detected.
- `WEB_INSUFFICIENT`: MetaQA completed, but external search yielded insufficient evidence.
- `PARTIAL`: One pipeline completed successfully while the other experienced an error or missing configuration.

There is strictly **no fused single percentage**. Both perspectives are maintained clearly.

---

## 10. Future Extensions (Planned Work)

- Principled multi-signal statistical fusion models.
- Browser extension for on-page text verification.
- Dynamic claim-directed search query expansion.
- Automated multi-model benchmark evaluation suites.
