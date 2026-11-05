# VeriFact README Documentation Audit Report

**Report Date**: 2026-11-05  
**Auditor**: Senior Software Architect & Technical Documentation Analyst  
**Target Repository**: `https://github.com/RohanSingh-2003/verifact`  
**Workspace Path**: `c:\Programming\Projects\verifact-main\verifact-main`

---

## 1. Executive Summary

This report documents the exhaustive audit, comprehensive rewriting, technical correction, and standardization of all README documentation across the VeriFact codebase.

Prior to this audit, repository documentation suffered from significant discrepancies between documented architectural claims and actual physical code:
- Outdated technology specifications (e.g., claiming React 18 / Tailwind 3.4 when the code uses React 19.2.8 and Tailwind v4).
- Stale machine-specific absolute URLs (`file:///c:/Users/Rohan/Desktop/mini-project/verifact/...`).
- Misleading claims of dynamic model selection when the backend permanently enforces Gemma 4:26B (`gemma4:26b`).
- Stale curl examples referencing the retired 40-question `pilot.json` dataset instead of the active 550-question `hallucination_benchmark_frozen.json`.
- Unindexed master technical audit artifacts and missing documentation for core test and script directories.

Through this audit, **11 README files** were discovered, rewritten, expanded, or created, and all relative links were verified to ensure zero broken references.

---

## 2. README Inventory & Action Summary

| # | File Path (Relative to Repository Root) | Initial Status & Quality | Audit Action Taken | Final Status |
| :---: | :--- | :--- | :--- | :--- |
| 1 | `README.md` (Root) | Stale, machine-specific paths, outdated React 18 / Tailwind 3 references, unverified test claims. | **Complete Rewrite** | Fully rewritten across Sections A through P with KaTeX math, Mermaid diagrams, and accurate contracts. |
| 2 | `backend/README.md` | Hardcoded local paths, incomplete endpoint list, outdated model identifiers. | **Complete Rewrite** | Fully rewritten developer guide covering async background tasks, SQLite WAL mode, dual engines, and REST endpoints. |
| 3 | `frontend/README.md` | Stale React 18 notes, dead model selector component referenced as active feature. | **Complete Rewrite** | Fully rewritten guide detailing React 19, Tailwind v4, Vite 8, polling hooks, and progressive rendering states. |
| 4 | `backend/data/datasets/README.md` | High quality but contained broken relative links to `docs/` and outdated verifier model. | **Targeted Improvements** | Fixed 3 relative links, updated benchmark API curl example to Phi-4 verifier, verified SHA-256 hashes. |
| 5 | `backend/tests/README.md` | **Missing** (Did not previously exist). | **Newly Created** | Comprehensive guide detailing 607 unit tests, Pytest flags, mock client fixtures, and test coverage domains. |
| 6 | `backend/scripts/README.md` | **Missing** (Did not previously exist). | **Newly Created** | Operational manual detailing all 7 database, dataset freezing, and diagnostic smoke testing scripts. |
| 7 | `experiments/README.md` | Clean archival guide, accurate mock disclosures. | **Audited & Verified** | Verified relative links and mock disclosures against `final_results_lock.md`. Left structurally preserved. |
| 8 | `analysis/README.md` | Outdated curl example referencing deleted `pilot.json` dataset. | **Complete Rewrite** | Updated curl commands to `hallucination_benchmark_frozen`, clarified mock artifact purposes, and updated links. |
| 9 | `analysis/output/README.md` | Brief 26-line stub with limited column descriptions. | **Targeted Improvements** | Enriched file descriptions, metric definitions, and cross-references to the audit lock. |
| 10 | `docs/README.md` | Outdated documentation index missing the 6 new master technical audit files. | **Complete Rewrite** | Rewritten as Master Technical Documentation Directory indexing all architecture dossiers and research files. |
| 11 | `docs/screenshots/README.md` | Minimal Windows-only guide. | **Targeted Improvements** | Added platform-neutral commands, complete visual element specifications, and parent documentation links. |

---

## 3. Detailed Statistics

- **Total README Files Discovered Initially**: 9
- **Total README Files Newly Created**: 2 (`backend/tests/README.md`, `backend/scripts/README.md`)
- **Total README Files in Final Repository**: 11
- **Total Files Completely Rewritten**: 5 (`README.md`, `backend/README.md`, `frontend/README.md`, `analysis/README.md`, `docs/README.md`)
- **Total Files Substantially Improved**: 5 (`backend/data/datasets/README.md`, `analysis/output/README.md`, `docs/screenshots/README.md`, `backend/tests/README.md`, `backend/scripts/README.md`)
- **Total Files Audited and Verified Unchanged**: 1 (`experiments/README.md` — verified as completely accurate and structurally intact)

---

## 4. Major Technical Discrepancies Discovered & Rectified

### Discrepancy 1: Machine-Specific Absolute File Paths
- **Discovered In**: Root `README.md` (lines 614–615, 649) and `backend/README.md` (lines 51, 65, 78, 89, 108).
- **Issue**: Links were hardcoded as absolute local paths belonging to a developer's machine (`file:///c:/Users/Rohan/Desktop/mini-project/verifact/...`).
- **Correction**: Replaced all instances with clean relative markdown repository links (`docs/COMPLETE_PROJECT_TECHNICAL_AUDIT.md`, `backend/app/llm/registry.py`).

### Discrepancy 2: Frontend Tech Stack Version Desynchronization
- **Discovered In**: Root `README.md` and `frontend/README.md`.
- **Issue**: Documentation claimed React 18, Tailwind CSS 3.4.1, and React Router DOM v6.
- **Reality**: `frontend/package.json` specifies `"react": "^19.2.8"`, `"tailwindcss": "^4.3.3"`, `"@tailwindcss/vite": "^4.3.3"`, `"react-router-dom": "^7.18.3"`, and `"vite": "^8.2.2"`.
- **Correction**: Updated all frontend and root documentation to accurately reflect React 19, Tailwind CSS v4, and Vite 8.

### Discrepancy 3: Enforced Generator Baseline vs. Model Selector Dead Code
- **Discovered In**: Root `README.md` and `frontend/src/components/detect/AnswerModelSelector.tsx`.
- **Issue**: Documentation in some older sections claimed the user could choose their answer-generating model from a dropdown menu.
- **Reality**: `backend/app/api/routes_detect.py` hardcodes `model = "gemma4:26b"`. `AnswerModelSelector.tsx` is unreferenced dead code; the UI does not render any model dropdown.
- **Correction**: Documented Gemma 4:26B as the fixed, permanent answer generator and explicitly flagged `AnswerModelSelector.tsx` as unrendered dead code.

### Discrepancy 4: Stale Benchmark Dataset Name in CLI Examples
- **Discovered In**: `analysis/README.md` and `backend/data/datasets/README.md`.
- **Issue**: Example curl commands instructed users to pass `"dataset": "pilot"`, even though `pilot.json` was deleted in Task 3.1.1.
- **Reality**: The active formal benchmark is `hallucination_benchmark_frozen.json` (550 questions). Passing `"pilot"` to the API triggers a 404/400 error.
- **Correction**: Updated all API curl examples to pass `"dataset": "hallucination_benchmark_frozen"`.

### Discrepancy 5: Qwen Model Identifier Divergence
- **Discovered In**: `backend/app/config.py` vs. `backend/app/llm/registry.py`.
- **Issue**: `config.py` specifies `groq_model: str = "qwen-2.5-32b"`, whereas `registry.py` defines the default string as `"qwen/qwen3.8-27b"`.
- **Correction**: Transparently documented this configuration divergence in the root and backend model tables.

### Discrepancy 6: Database Storage Strategy
- **Discovered In**: `docs/architecture.md` §9 vs. `backend/app/database/models.py`.
- **Issue**: Architectural text diagrammed a distinct relational table `MODEL_VERDICTS`.
- **Reality**: `models.py` has no `ModelVerdict` table. Verdicts are serialized as JSON strings in `Run.ai_verdicts_json` and `Mutation.verdicts_json`.
- **Correction**: Documented the JSON blob serialization strategy honestly and removed references to a nonexistent SQL table.

---

## 5. Broken Links Discovered & Fixed

A programmatic audit of all markdown links across all 11 README files discovered and resolved the following broken relative links:

| Source File | Broken Link Target | Root Cause | Corrected Link Target |
| :--- | :--- | :--- | :--- |
| `backend/data/datasets/README.md` | `../../../../docs/temporal_validation_policy.md` | Traversed 4 levels up instead of 3, escaping the repository root. | `../../../docs/temporal_validation_policy.md` |
| `backend/data/datasets/README.md` | `../../../../docs/final_results_lock.md` | Traversed 4 levels up instead of 3, escaping the repository root. | `../../../docs/final_results_lock.md` |
| `backend/data/datasets/README.md` | `backend/app/evaluation/ground_truth.py` | Relative path assumed repository root instead of current directory. | `../../app/evaluation/ground_truth.py` |
| Root `README.md` | `file:///c:/Users/Rohan/...` | Machine-specific absolute path. | Relative repo path. |

**Final Link Verification**: Automated validation confirmed **0 broken links** across all 11 README files.

---

## 6. Validation Results

| Test / Check | Tool / Method | Scope | Result | Details |
| :--- | :--- | :--- | :--- | :--- |
| **Relative Link Verification** | Python regex link resolver script | All 11 README files | **PASSED** | 100% of internal links resolve to physical files on disk. |
| **Mermaid Syntax Validation** | AST parser & Mermaid CLI linter | Root `README.md` diagrams | **PASSED** | Topology `graph TB` and workflow `sequenceDiagram` syntax verified. |
| **LaTeX Math Formatting** | KaTeX delimiter check | Root & Backend READMEs | **PASSED** | Formulas formatted with proper `$...$` inline and `$$...$$` blocks. |
| **Code Block Syntax** | Language identifier check | All 11 README files | **PASSED** | All code blocks specify valid language tags (`bash`, `json`, `typescript`, `python`). |
| **Secret Scanning** | Regex credential scanner | All 11 README files | **PASSED** | Zero exposed API keys, tokens, passwords, or hashes. |

---

## 7. Remaining Documentation Gaps & Recommendations

1. **Frontend Codebase Cleanup**: Remove `frontend/src/components/detect/AnswerModelSelector.tsx` in a future PR to eliminate dead code confusion.
2. **Configuration String Alignment**: Unify the Qwen model string in `backend/app/config.py` and `backend/app/llm/registry.py` to `qwen-2.5-32b`.
3. **Execution of Live Benchmarks**: When API credits are available, execute the unexecuted 2×2 live experiment (`experiments/config/final_experiment.yaml`) against live commercial providers and store the results in `experiments/results/live_2x2/`.

