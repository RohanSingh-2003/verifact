# Demo script (about 3 minutes)

Use **Demo / Mock Mode** unless a live key is configured. Say so out loud.

### 0:00–0:20 — Problem

LLMs can generate confident but factually incorrect answers. Checking every claim on the web is a different system. VeriFact asks whether the answer is **internally consistent** under restatement.

### 0:20–0:45 — What VeriFact does

VeriFact implements **MetaQA** (an existing metamorphic method). Generate an answer, create synonym and antonym mutations, ask a verifier YES / NO / NOT SURE, average the MetaQA table, classify with threshold 0.5. No search, Wikipedia, or RAG in the detector.

### 0:45–1:20 — Detection demo

On **Detect**, enter a factual question (for example, “What is the capital of Australia?”). Show:

- generated answer
- hallucination score and HALLUCINATED / Reliable
- Synonym / Antonym tabs
- actual vs expected verdicts
- “Why was this answer flagged?” built from the run, not canned copy

If the banner says Demo / Mock Mode, say the answers are deterministic fixtures.

### 1:20–2:00 — Research experiment

Open **Experiments**. Show the 2×2:

- A→A and B→B = same-model
- A→B and B→A = cross-model

Explain that the answer and mutation set are frozen; only verifier identity changes.

### 2:00–2:30 — Results

Locked run `58baff20-fb86-4f43-b20e-895a086ceb6b`, 40 pilot questions, **mock**.

Mean scores: A→A 0.0, A→B 1.0, B→A 0.0, B→B 1.0. Difference signs reverse across generators. That is a **verifier-calibration** pattern, not a live-LLM self-verification finding. Hypothesis: **inconclusive** for real models.

### 2:30–3:00 — Limitations and future work

Small dataset, mock client, two placeholder models, prompt-based mutations. Next step is a confirmed live 2×2 with real provider models, without changing MetaQA scoring.
