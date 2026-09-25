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
- **VeriFact** is the software framework that implements this methodology into an interactive progressive web application, local Ollama engine, and controlled 2×2 experiment harness.

---

## 3. Base Answer Generation

Given a factual user query, the generator model (`gemma4:26b` in live Ollama mode) produces a concise factual answer. 

- Ground-truth references are **never** provided to the prompt.
- In the interactive Detect pipeline, answer generation is decoupled from metamorphic analysis: the answer is stored and returned immediately to the frontend (`status: answer_ready`), allowing the user to read the AI's response while downstream verification proceeds asynchronously on the same run.

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

### Mutation Counts: Detect vs. Experiments
VeriFact explicitly differentiates between interactive user detection and research experiments:
- **Interactive Detect**: Uses **3 synonym + 3 antonym = 6 mutations** (`SYNONYM_COUNT=3`, `ANTONYM_COUNT=3`) to maintain responsive latency on local 26B parameter hardware.
- **Research Experiments**: Default to **5 synonym + 5 antonym = 10 mutations** (`ExperimentRunRequest`), generating a frozen mutation set once per question cell to evaluate same-model versus cross-model verifier consistency.

### Syntactic & Semantic Heuristic Gates
Every candidate mutation is validated by strict heuristic filters before being accepted:
- Must be a complete declarative sentence (minimum 5 words, maximum 35 words).
- Cannot be an interrogative or end with a question mark.
- Cannot contain explanatory prefixes (e.g., *"Synonym mutation:"*, *"This means that"*).
- Cannot be a no-op identical copy of the original claim.
- If mutations are missing, VeriFact executes partial retry rounds (up to 4 rounds) requesting only the deficit count.

---

## 5. Independent Mutation Verification

Each accepted mutation is submitted independently to the verifier LLM:
- **Prompt Isolation**: The verifier receives the original question, candidate answer, and the single mutated statement.
- **Zero Information Leakage**: The verifier is **never told** whether the statement is a synonym or an antonym, nor what verdict is expected.
- **Verdict Vocabulary**:
  - `YES`: The statement is supported by the candidate answer.
  - `NO`: The statement is not supported by (or contradicts) the candidate answer.
  - `NOT SURE`: The verifier cannot determine support, or returned ambiguous text.
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
> VeriFact's detector is strictly **reference-free** (zero-resource) and does not consult external databases or search indices during detection.

---

## 8. Future Extensions (Planned Work)

External fact retrieval is planned as a future extension:
- Extracting individual factual assertions.
- Querying search providers (such as Tavily or SerpAPI) for primary web sources.
- Evaluating evidence support levels (**SUPPORTED**, **CONTRADICTED**, **INSUFFICIENT EVIDENCE**).
- Merging metamorphic internal consistency scores with external source confidence.
