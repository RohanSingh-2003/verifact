# Documentation Index

This directory contains technical documentation detailing the methodology, software architecture, verification pipelines, and operational procedures for VeriFact.

For initial installation and quick-start instructions, refer to the root [README.md](../README.md).

---

## Core Product Documentation

| Document | Purpose |
| :--- | :--- |
| **[architecture.md](architecture.md)** | Full software architecture, component topology, FastAPI background parallel execution, and LLM clients. |
| **[methodology.md](methodology.md)** | Theoretical explanation of MetaQA, claim extraction, mutation types, scoring formulas, Web Evidence routing, claim-relevant evidence extraction, and Overall VeriFact Assessment. |
| **[project_description.md](project_description.md)** | Comprehensive project description tailored for evaluators, researchers, and visitors. |
| **[limitations.md](limitations.md)** | Honest discussion of system constraints, consistency vs. truth, hardware demands, and retrieval boundaries. |
| **[demo_script.md](demo_script.md)** | Step-by-step walkthrough demonstrating the interactive Detect experience. |
| **[interview_explanation.md](interview_explanation.md)** | Summary elevator pitches and detailed technical Q&A for oral examination. |
| **[release_notes.md](release_notes.md)** | Milestone history, completed features, and planned future extensions. |

---

## Research & Evaluation Documents (Previous Investigations)

Prior to product finalization, VeriFact was utilized to explore same-model versus cross-model verifier behaviors ($A \to A, A \to B, B \to A, B \to B$) with frozen mutation sets to evaluate verifier calibration. The following documents detail those offline research findings:

| Document | Purpose |
| :--- | :--- |
| **[final_results_lock.md](final_results_lock.md)** | Research artifact lock for the frozen 40-question mock study (`58baff20-fb86-4f43-b20e-895a086ceb6b`). |
| **[experiment_methodology.md](experiment_methodology.md)** | Historical specification of the 2×2 same-model vs. cross-model design, fixed mutation controls, and Wilcoxon testing. |
| **[results.md](results.md)** | Statistical analysis of the frozen 2×2 study and verifier calibration confounds. |
| **[discussion.md](discussion.md)** | Scientific interpretation of experimental findings and self-verification hypotheses. |
| **[research_audit.md](research_audit.md)** | Internal research integrity and reproducibility audit. |
| **[viva_questions.md](viva_questions.md)** | Supplementary viva voce defense questions and answers. |
| **[resume_bullets.md](resume_bullets.md)** | Curated project highlights for resumes and professional portfolios. |

---

## Screenshots

Refer to **[screenshots/README.md](screenshots/README.md)** for capturing and linking current UI screenshots of the running application.
