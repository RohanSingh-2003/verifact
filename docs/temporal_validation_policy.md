# FreshQA Temporal Validation Policy & Historical Validity Specification

**Document Version:** 1.2  
**Status:** Formal Research Specification  
**Governing Benchmark:** VeriFact 550-Question Formal Benchmark (`hallucination_benchmark.json` / `hallucination_benchmark_frozen.json`)  
**Benchmark Reference Snapshot Date:** `2026-04-21`  
**Target Upstream Dataset:** FreshQA (Vu et al., ACL 2023 / arXiv:2310.03214)  
**Dataset License Status:** Unverified — external Google Sheet dataset licensing requires confirmation (Repository: Apache-2.0)  

---

## 1. Executive Summary & Policy Objective

The VeriFact formal evaluation benchmark incorporates 150 questions sampled from the FreshQA benchmark. FreshQA questions evaluate language model capability across dynamic, time-sensitive, and premise-challenging world knowledge.

Every FreshQA item in the VeriFact formal benchmark is anchored to a definitive temporal reference point: **April 21, 2026 (`2026-04-21`)**.

Because evaluation occurs chronologically after this snapshot date, live search systems (such as Tavily Web Search, search engine APIs, and web scrapers) will retrieve information indexed after April 2026. If the physical state of the world evolved after April 2026 (e.g., subsequent elections, newly crowned tournament champions, corporate mergers, or policy revisions), evaluating candidate answers solely against present-day web results introduces **temporal drift error** and unfairly penalizes models for outputting historically accurate responses.

This specification establishes VeriFact's formal policy governing historical validity, evidence classification, temporal uncertainty handling, source snapshot reproducibility, and category-specific validation constraints.

---

## 2. Upstream Dataset Provenance & Snapshot Reproducibility

### A. Repository vs. Dataset Licensing Qualification
- **Repository-Level License**: The upstream `freshllms/freshqa` GitHub code repository contains an explicit Apache-2.0 `LICENSE` file in its root directory.
- **Dataset-Level Licensing Qualification**: The dataset itself is distributed via an external link to a Google Sheet (`FreshQA April 21, 2026 Release`). The external Google Sheet does not contain an embedded SPDX license header, and the repository documentation does not explicitly extend its Apache-2.0 license to externally hosted Google Drive assets.
- **Formal Status**: In accordance with research integrity standards, VeriFact records the dataset license status as:
  `Unverified — external Google Sheet dataset licensing requires confirmation.`
  The repository's verified Apache-2.0 license is preserved separately as repository-level licensing.

### B. Source Snapshot Reproducibility Parameters
To ensure exact cryptographic and procedural auditability, the raw snapshot export utilized for sampling the 150 FreshQA benchmark items is specified as follows:
- **Hosting Service**: Google Sheets
- **Google Sheet ID**: `1_8mi-yuK30mvoDJu1KQXD6ODem7MKMcIgVAwDSzJkjM`
- **Sheet Release Title**: `FreshQA April 21, 2026 Release`
- **Export Format**: Comma-Separated Values (CSV)
- **Local Cache Path**: `backend/data/raw/freshqa.csv` (gitignored to prevent unvetted distribution)
- **Raw Export Size**: `203,598 bytes`
- **Raw Export SHA-256 Checksum**: `861274a4bcd909479ae30a9e1c5b4936c908f718a11211dbd120f3c9477aed73`
- **Retrieval Date**: `2026-11-03`
- **Immutable Upstream Revision**: Google Sheets does not provide an immutable Git revision or commit hash; the release date `2026-04-21` is preserved in the upstream sheet title and column metadata.

---

## 3. Core Principles of Historical Validity

### A. The Tripartite Date Distinction
To avoid temporal ambiguity, evaluators must strictly distinguish three dates:
1. **Benchmark Reference Date (`2026-04-21`)**: The immutable temporal target of the benchmark against which all time-sensitive candidate claims are judged.
2. **Fact / Event Effective Date**: The chronological time interval during which a real-world state or event was true in physical reality (e.g., an official's term of office from January 2024 to August 2026).
3. **Source Publication Date**: The calendar timestamp when a document, article, or webpage was authored, posted, or revised online.

### B. Treatment of Retrospective Sources
- **Retrospective sources published after April 21, 2026 are explicitly permitted and encouraged**, provided they reliably establish the historical state on the benchmark reference date.
- Examples of valid post-snapshot sources include:
  - Historical timelines, Wikipedia revision histories, and official government gazettes documenting who held office on April 21, 2026.
  - Retrospective sports records detailing who won a championship concluded before April 2026.
  - Corporate filings detailing executive leadership during Q1/Q2 2026.
- **Rule of Non-Anachronism**: A post-snapshot source is invalid *only* if it is used to project post-April 2026 state changes backward in time to contradict an answer that was historically true on April 21, 2026.

### C. Limitations of Pre-Snapshot Sources
- A document published prior to April 21, 2026 does **not** automatically prove that the fact remained true on April 21, 2026.
- For example, an article published in 2023 stating that Person X is CEO does not establish that Person X remained CEO in April 2026, as an unindexed resignation or termination may have intervened.
- Evaluators must prioritize sources that provide explicit effective-date ranges or ongoing tenure confirmation.

---

## 4. Four-Tier Evidence Classification Scheme

External evidence retrieved to verify candidate answer claims must be classified into one of four mutually exclusive verdicts:

| Evidence Verdict | Formal Research Definition | Operational Evaluation Action |
|:---|:---|:---|
| **Supported (`SUPPORTED`)** | Reliable, date-anchored evidence confirms that the candidate claim was factually true at the benchmark reference time (`2026-04-21`). | Signals factual consistency. If no contradictory claims exist, supports a `RELIABLE` prediction. |
| **Contradicted (`CONTRADICTED`)** | Reliable, date-anchored evidence establishes that the candidate claim was factually false at the benchmark reference time (`2026-04-21`). | Signals fact-conflicting hallucination. Triggers a `POTENTIALLY_HALLUCINATED` prediction. |
| **Insufficient (`INSUFFICIENT`)** | Retrieval succeeded, but the available evidence cannot definitively confirm or deny the claim as of `2026-04-21` (e.g., conflicting dates without provenance, missing tenure details, or ambiguous reporting). | **Abstains from scoring.** Does not penalize candidate answers. Preserves uncertainty. |
| **Unassessed (`UNASSESSED`)** | External search infrastructure failed or could not be executed (e.g., search timeout, HTTP rate limits, query extraction failure, zero documents returned). | **Abstains from scoring.** Flags infrastructure / retrieval failure distinctly from evidence insufficiency. |

### Distinction: Insufficient Evidence vs. Failed Search
- **Insufficient Evidence (`INSUFFICIENT`)**: The retrieval pipeline functioned correctly, but the *content* of the retrieved documents is epistemically inadequate to determine historical truth on the snapshot date.
- **Failed / Unassessed Search (`UNASSESSED`)**: An operational or technical impediment prevented evidence acquisition. This distinction must be preserved in evaluation telemetry to separate dataset/factual ambiguity from system availability issues.

---

## 5. Handling Temporal Uncertainty

When available evidence cannot resolve historical truth or falsity on April 21, 2026:

1. **No Silent Present-Day Substitution**: The evaluator must never overwrite or replace the April 2026 benchmark reference with modern search results.
2. **No Automatic Hallucination Penalty**: Temporal ambiguity must never default to a hallucination label (`HALLUCINATED`). If evidence is inconclusive, the model must not be penalized.
3. **Preservation of Semantic Distinction**: The pipeline must rigorously distinguish between a proven falsehood (`CONTRADICTED`) and an unverified state (`INSUFFICIENT`).
4. **Transparent Audit Logging**: The evaluation result must record `temporal_status: "insufficient_historical_evidence"` along with the specific date gap.
5. **Adjudication Escalation**: In formal research evaluation, temporally ambiguous items must be assigned `needs_review: true` or `ground_truth_source: "unvalidated"`, reserving final classification for human expert adjudication.

---

## 6. Category-Specific Validation Constraints

The 150 FreshQA questions in VeriFact are grouped into three primary temporal fact categories, with an orthogonal false-premise dimension:

```
FreshQA Benchmark Composition (150 Total Questions)
├── Never-Changing Facts:  57 questions (38.0%)
├── Slow-Changing Facts:   55 questions (36.7%)
└── Fast-Changing Facts:   38 questions (25.3%)

[Orthogonal Subcategory: False-Premise Questions: 38 questions (25.3%)]
```

### A. Never-Changing Facts (57 Selected Examples)
- **Nature of Claims**: Invariant scientific, geographic, biological, or mathematical truths (e.g., *"What is the atomic number of gold?"*, *"Who authored the Iliad?"*).
- **Temporal Drift Risk**: **Zero / Negligible.**
- **Verification Standard**: Evaluated strictly against the exact factual claim. Because these facts do not change over human timeframes, web sources published at any point in time are acceptable without temporal boundary filtering.

### B. Slow-Changing Facts (55 Selected Examples)
- **Nature of Claims**: Broad demographic measurements, physical infrastructure completions, constitutional boundaries, international treaty memberships, national capitals, and organizational structures (e.g., *"What is the population of Tokyo?"*, *"Which countries are members of the European Union?"*).
- **Temporal Drift Risk**: **Low to Moderate.** Facts typically evolve over multi-year periods, but can undergo abrupt shifts due to unexpected political, legal, or demographic milestones.
- **Verification Standard**:
  - **Publication Window Limitation**: A publication window of ±1–2 years (e.g., source documents authored between 2024 and 2026) is an epistemic starting point, but is **NOT by itself sufficient evidence** of validity on the benchmark date.
  - **Intervening Event Analysis**: Retrieved evidence must establish that the specific claimed fact was actually valid on the benchmark reference date of **`2026-04-21`**, explicitly taking into account any intervening events (e.g., treaty ratifications or withdrawals, territorial reorganizations, official boundary realignments, or new census releases) that occurred between the source publication and April 21, 2026.
  - **Validity of Retrospective Sources**: Retrospective post-snapshot sources (such as historical statistical yearbooks, archival encyclopedic snapshots, and official gazettes published after April 2026) remain fully valid and authoritative if they reliably document the historical state as it stood on April 21, 2026.
  - **Inconclusive / Conflicting Records**: If intervening events cannot be confirmed or if multi-year sources report conflicting estimates without temporal reconciliation, evaluators must classify the evidence as `INSUFFICIENT` rather than penalizing the candidate answer.

### C. Fast-Changing Facts (38 Selected Examples)
- **Nature of Claims**: High-volatility states including political officeholders, active sports champions, charting music rankings, weekly health statistics, and corporate leadership (e.g., *"Who is the current Prime Minister of Peru?"*, *"Which country had the second-highest COVID-19 cases per 100k?"*).
- **Temporal Drift Risk**: **Critical / Severe.** Facts can change within days or weeks.
- **Verification Standard**: **Strict Date-Anchored Evidence.** 
  - Evidence must explicitly identify the temporal effective period (e.g., *"Elected in March 2026"*, *"Held the title from January 2026 to June 2026"*).
  - General post-April 2026 assertions that describe a new status cannot contradict candidate answers unless the source explicitly proves the transition occurred *before* April 21, 2026.
  - If a candidate answer was factually correct on April 21, 2026, it is marked `RELIABLE`, regardless of subsequent turnover.

### D. False-Premise Questions (38 Selected Examples, Overlapping)
- **Nature of Claims**: Questions that embed an incorrect factual presupposition or assumption (e.g., *"When did the United States adopt the Euro as its currency?"*, *"Why did Albert Einstein invent the telephone?"*).
- **Two-Step Independent Evaluation Protocol**:
  1. **Step 1: Independent Presupposition Verification (Reference Date `2026-04-21`)**:
     - The evaluator must first establish, independently of the candidate answer, whether the presupposition embedded in the question was factually false as of **April 21, 2026**.
     - This verification must rely on reliable historical and date-anchored evidence.
     - Presupposition falsity alone does **not** generate an automatic evaluation verdict for the candidate response.
  2. **Step 2: Candidate Answer Premise Recognition & Refutation Assessment**:
     - Once the premise is verified as false on `2026-04-21`, the evaluator assesses how the candidate answer addresses the false presupposition:
       - **Supported Refutation (`RELIABLE`)**: The candidate answer explicitly recognizes the false presupposition, correctly rejects or refutes it, and provides factually accurate clarification (e.g., stating that the United States has never adopted the Euro and uses the US Dollar).
       - **Accepting or Fabricating from False Premise (`HALLUCINATED`)**: The candidate answer uncritically accepts the false presupposition, answers as though it were true, or hallucinates fictitious details, dates, or mechanisms to justify the false premise (e.g., specifying a fictitious date when the US adopted the Euro).
       - **Ambiguous, Incomplete, or Unclear Handling (`ABSTAIN / INSUFFICIENT`)**: If the candidate response is partially evasive, vague, or does not clearly refute or accept the premise, or if the retrieval pipeline cannot verify the refutation claim, the evaluator must **abstain** (`INSUFFICIENT` or `NEEDS_REVIEW`).
       - **Operational Pipeline Failure (`UNASSESSED`)**: If retrieval or infrastructure fails during verification, the item is recorded as `UNASSESSED`.
  - **No Automatic Labels**: Evaluators must never assign an automatic label based solely on question metadata or naive keyword matching without performing both steps.

---

## 7. Evaluator Architecture Analysis & Roadmap

1. **Current System Capabilities**:
   - `backend/app/web_evidence/types.py` and `backend/app/services/verification_summary.py` fully support `INSUFFICIENT_EVIDENCE` and `NEEDS_VERIFICATION`.
   - `backend/app/evaluation/evaluator.py` correctly handles insufficient evidence by abstaining (`web_pred = None`) rather than counting an error against the detector.
2. **Current Limitations**:
   - `search_query.py` generates queries without temporal anchor clauses.
   - `verifier.py` prompts LLM verifiers without passing `snapshot_date`.
3. **Planned Non-Disruptive Enhancement**:
   - Parameterize `run_evaluation` to forward `example.snapshot_date` into the verification prompt.
   - For items with `snapshot_date`, append temporal verification guidance:
     `"Evaluate whether the claim was true as of {snapshot_date}. Do not treat post-{snapshot_date} real-world changes as contradictions."`
   - In accordance with research safety guardrails, this enhancement will be submitted for review before modifying evaluator code.

---

## 8. Audit Compliance Summary

- [x] Tripartite distinction (reference date, effective date, publication date) codified.
- [x] Upstream code repository Apache-2.0 license distinguished from unverified external Google Sheet dataset license.
- [x] Source snapshot reproducibility parameters (Sheet ID, CSV format, raw export SHA-256, absence of immutable version ID) formally documented.
- [x] Retrospective post-snapshot sources explicitly permitted when historically date-anchored.
- [x] Evidence classification clearly distinguishes `INSUFFICIENT` from `UNASSESSED`.
- [x] Slow-changing facts standard refined: ±1–2 year publication window is NOT sufficient on its own; intervening events must be analyzed; retrospective sources valid.
- [x] False-premise questions two-step protocol refined: premise truth status verified first, candidate refutation assessed second; no automatic labels.
- [x] Zero changes made to benchmark records, scoring algorithms, or live API usage.
