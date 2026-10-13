# VeriFact Demonstration Script

This script provides a structured 3-to-4 minute walkthrough of VeriFact demonstrating **features implemented in the current application**, including the Answer-First progressive UI, MetaQA metamorphic testing, Direct-Answer Multi-Model Peer Review, and the independent Web Evidence grounding pipeline.

---

## Preparation Checklist
- [ ] Backend running (`uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`) in `backend/`
- [ ] Frontend running (`npm run dev`) at `http://localhost:5173` in `frontend/`
- [ ] Cloud API credentials configured in `backend/.env` (e.g., `OLLAMA_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`) for Live Mode
- [ ] Alternatively, set `LLM_MODE=mock` in `backend/.env` to demonstrate offline with deterministic test fixtures (noted by the amber status badge in the UI)

---

## Step-by-Step Demonstration Flow

### Step 1: Open the Application & Inspect the Header
- **Action**: Navigate to `http://localhost:5173`.
- **Spoken Talking Point**:
  > *"Welcome to VeriFact. Notice the runtime status indicator in the top navigation bar. When running in Live Mode, it connects to configured cloud providers with **Gemma 4:26B** (via Ollama Cloud) permanently designated as the answer generator. If demonstrating offline without live credentials, it transparently indicates **Demo / Mock Mode** with deterministic test fixtures."*

### Step 2: Explain the Problem & Self-Confirmation Bias
- **Spoken Talking Point**:
  > *"When an LLM produces an answer, we cannot simply ask it 'Are you sure?' because of self-confirmation bias and sycophancy. VeriFact addresses this through structural separation: rather than self-checking, it evaluates answers using three independent concurrent verification branches: metamorphic consistency testing (MetaQA), direct-answer peer review across independent cloud models, and external factual grounding via Tavily search."*

### Step 3: Enter a Factual Query
- **Action**: Enter a question into the Detect input box:
  - Example 1: `"What is the capital of Australia and why was it chosen?"`
  - Example 2: `"Who formulated the three laws of motion?"`
- **Action**: Click **Detect Hallucinations**.

### Step 4: Highlight Progressive Answer Display (The "Answer First" Feature)
- **Action**: Point out that the **Candidate AI Answer** renders within seconds (`status: answer_ready`).
- **Spoken Talking Point**:
  > *"Notice that the user does not have to wait for lengthy multi-stage verification before seeing the generated answer. VeriFact displays Gemma's answer immediately. Meanwhile, three verification branches launch concurrently in the background on the exact same run ID."*

### Step 5: Branch 1 — MetaQA Mutation Generation & Scoring
- **Action**: As the UI updates, point to the **Generated Mutations** tab appearing (`status: generating_mutations` → `verifying_mutations`).
- **Spoken Talking Point**:
  > *"VeriFact extracts core factual claims from the answer and generates paired mutations: meaning-preserving synonyms and meaning-reversing antonyms."*
  > - Point to a **Synonym Mutation**: *"This rephrases the claim. A consistent verifier is expected to say YES."*
  > - Point to an **Antonym Mutation**: *"This inverts or negates the claim. A consistent verifier is expected to say NO."*
  > *"Each mutated statement is independently evaluated by the verifier pool without knowing whether it is a synonym or antonym. VeriFact deterministically calculates the MetaQA Hallucination Score by averaging contributions against threshold 0.5."*

### Step 6: Branch 2 — Direct-Answer Multi-Model Peer Review
- **Action**: Point to the **Multi-Model Independent Reviews** card (`IndependentVerdictsCard`).
- **Spoken Talking Point**:
  > *"Concurrently with MetaQA, independent peer models — including Gemini 3.8 Flash, GLM-4.7-Flash, Qwen-2.5-32B, and Liquid/OpenRouter — review Gemma's complete answer text directly. The UI displays an executive consensus badge (such as 'Consensus: Correct' or 'Disagreement Detected'), the agreement ratio, and expandable peer rationales highlighting any disputed or contradictory claims."*

### Step 7: Branch 3 — Web Evidence Analysis
- **Action**: Scroll to the **Web Evidence Analysis** panel.
- **Spoken Talking Point**:
  > *"In parallel, VeriFact's Web Evidence pipeline classifies the question domain (e.g., Science, Government, or General Facts), routes targeted queries toward authoritative domains, and extracts concise 1–2 sentence evidence summaries from retrieved Tavily search snippets. Each claim is labeled SUPPORTED, CONTRADICTED, or INSUFFICIENT_EVIDENCE. Crucially, lack of search evidence is never treated as a hallucination."*

### Step 8: Final Result & Overall VeriFact Assessment
- **Action**: Point to the completed **Overall VeriFact Assessment** panel (`status: completed`).
- **Spoken Talking Point**:
  > *"When all three branches finish, VeriFact synthesizes the signals into an Overall Assessment: an executive verdict badge (such as 'Likely Reliable' or 'Potentially Hallucinated') and a 3-column summary contrasting the MetaQA Inconsistency Score, Web Consistency Score, and Combined Risk heuristic. The underlying research scores remain mathematically separate."*

### Step 9: Walk Through the Run History & Documentation Pages
- **Action**: Click **History** in the top navigation.
- **Spoken Talking Point**:
  > *"All detection runs, base answers, mutation statements, peer reviews, and stage timings are persisted in a local SQLite database for auditing and trace inspection. The navigation also provides dedicated educational guides: the **MetaQA Guide** (`/metaqa`) explaining metamorphic testing theory and the **Web Analysis Guide** (`/web-analysis`) detailing domain classification and evidence scoring."*

### Step 10: State the Research Boundary
- **Spoken Talking Point**:
  > *"MetaQA evaluates **internal semantic consistency**, not absolute real-world truth. Web Evidence reports whether retrieved snippets support or contradict a claim. Neither pipeline is an infallible truth oracle, which is why presenting both signals side-by-side provides transparent, explainable AI verification."*
