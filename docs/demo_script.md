# VeriFact Demonstration Script

This script provides a structured 3-to-4 minute walkthrough of VeriFact demonstrating **features implemented in the current repository**, including MetaQA and the independent Web Evidence pipeline (Phases 1–2).

---

## Preparation Checklist
- [ ] Backend running (`uvicorn app.main:app --reload --port 8000`)
- [ ] Frontend running (`npm run dev`) at `http://localhost:5173`
- [ ] Ollama daemon running with `gemma4:26b` (if demonstrating Live Mode)
- [ ] Optional: `TAVILY_API_KEY` set in `backend/.env` for live Web Evidence (otherwise Web Evidence shows unavailable / mock sources in Demo Mode)
- [ ] If running in Mock Mode, note the amber banner

---

## Step-by-Step Demonstration Flow

### Step 1: Open the Application & Inspect the Header
- **Action**: Navigate to `http://localhost:5173`.
- **Spoken Talking Point**:
  > *"Welcome to VeriFact. Notice the badge in the top navigation bar. When running in Live Mode, it clearly identifies **Live Mode — Local Ollama · Model: gemma4:26b**. If running in development without a local GPU, it transparently indicates **Demo / Mock Mode** with deterministic test fixtures."*

### Step 2: Explain the Problem & MetaQA Methodology
- **Spoken Talking Point**:
  > *"When an LLM produces an answer, we cannot simply ask it 'Are you sure?' because of self-confirmation bias. VeriFact uses metamorphic testing: it restates the core claims of an answer into meaning-preserving synonyms and meaning-reversing antonyms to test if the model's knowledge behaves consistently."*

### Step 3: Enter a Factual Query
- **Action**: Enter a question into the Detect input box:
  - Example 1: `"What is the capital of India and why was it chosen?"`
  - Example 2: `"Who formulated the three laws of motion?"`
- **Action**: Click **Detect Hallucinations**.

### Step 4: Highlight Progressive Answer Display (The "Answer First" Feature)
- **Action**: Point out that the **Base AI Answer** renders within seconds (`status: answer_ready`).
- **Spoken Talking Point**:
  > *"Notice that the user does not have to sit and wait for the entire metamorphic pipeline. Local 26B inference is computationally heavy, so VeriFact displays the generated Gemma answer immediately. Meanwhile, MetaQA analysis continues asynchronously in the background on the exact same run ID."*

### Step 5: Observe Mutation Generation
- **Action**: As the UI updates, point to the **Generated Mutations** table appearing (`status: generating_mutations` → `mutations_ready`).
- **Spoken Talking Point**:
  > *"VeriFact has extracted core factual claims from the answer and generated 6 mutations: 3 synonym mutations and 3 antonym mutations."*
  > - Point to a **Synonym Mutation**: *"This rephrases the claim. A consistent verifier is expected to say YES."*
  > - Point to an **Antonym Mutation**: *"This deliberately inverts or negates the claim. A consistent verifier is expected to say NO."*

### Step 6: Observe Real-Time Verification Results
- **Action**: Point to the verification badges updating as background polling continues (`status: verifying_mutations`).
- **Spoken Talking Point**:
  > *"Each mutated statement is independently evaluated by the verifier model without being told whether it is a synonym or antonym. Notice the verdicts: YES, NO, or NOT SURE. Verifier rationales are also displayed for transparency, though only the verdict affects the score."*

### Step 7: Final Score & Classification
- **Action**: Point to the completed score card (`status: completed`).
- **Spoken Talking Point**:
  > *"Once all mutations are verified, VeriFact's mathematical engine deterministically calculates the hallucination score by averaging individual contributions. Because the score is below the 0.5 threshold, this answer is classified as **Reliable** (or if contradictions were detected, **Hallucinated**)."*

### Step 8: Web Evidence Analysis (independent)
- **Action**: Scroll to **Web Evidence Analysis**.
- **Spoken Talking Point**:
  > *"Alongside MetaQA, VeriFact classifies the question type — for example Science or Current event — picks preferred source categories, then checks each factual claim against retrieved snippets. Preferred domains are relevance hints, not automatic proof. Each claim is Supported, Contradicted, or Insufficient Evidence. The Verification Summary then compares MetaQA and Web Evidence side-by-side — for example ‘Signals agree’ or ‘Signals disagree’ — without inventing a combined percentage."*

### Step 9: Walk Through the Run History
- **Action**: Click **History** in the top navigation.
- **Spoken Talking Point**:
  > *"All detection runs, base answers, mutation sets, and stage execution timings are stored in a local SQLite database for auditing and research review."*

### Step 10: State the Research Boundary
- **Spoken Talking Point**:
  > *"MetaQA measures **semantic consistency**, not absolute real-world truth. Web Evidence reports whether retrieved snippets support or contradict a claim — it is an evidence report, not a truth oracle. Lack of evidence is not treated as hallucination."*
