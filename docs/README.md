# VeriFact Technical Documentation Index

This directory contains technical architecture documents, methodological explanations, audit locks, and research papers detailing the inner workings of the VeriFact system.

For initial installation, quick-start commands, and runtime configuration, refer to the root [README.md](../README.md).

---

## Core Product & Architecture Documentation

These documents describe the current production architecture, three-branch detection pipeline (MetaQA, Direct-Answer Review, and Web Evidence), and operational procedures:

| Document | Purpose |
| :--- | :--- |
| **[architecture.md](architecture.md)** | Comprehensive software architecture, component topology, FastAPI background parallel execution, and multi-model cloud client adapters. |
| **[methodology.md](methodology.md)** | Mathematical formulation of MetaQA metamorphic relations, claim parsing, mutation types, scoring contribution matrix, Web Evidence domain strategies, and Overall Assessment synthesis. |
| **[project_description.md](project_description.md)** | Executive project description, problem statement, dual-pipeline methodology, and cloud LLM implementation for evaluators and researchers. |
| **[limitations.md](limitations.md)** | Rigorous analysis of system boundaries, internal consistency vs. physical truth, retrieval constraints, and heuristic scoring disclaimers. |
| **[demo_script.md](demo_script.md)** | Step-by-step walkthrough script demonstrating the interactive Detect experience. |
| **[interview_explanation.md](interview_explanation.md)** | Elevator pitches, technical architecture summaries, and comprehensive Q&A for oral defense or interviews. |
| **[release_notes.md](release_notes.md)** | Milestone history, completed features, and roadmap for future extensions. |
| **[final_release_checklist.md](final_release_checklist.md)** | Pre-release verification checklist covering tests, lints, and documentation integrity. |

---

## Historical Research & Evaluation Documents (2×2 Study)

Prior to final product release, VeriFact was used to evaluate same-model versus cross-model verifier behaviors ($A \to A, A \to B, B \to A, B \to B$) with frozen mutation sets. The following documents record that offline research study:

| Document | Purpose |
| :--- | :--- |
| **[final_results_lock.md](final_results_lock.md)** | Research artifact lock for the frozen 40-question mock study (`58baff20-fb86-4f43-b20e-895a086ceb6b`). Highlights that the study used mock fixtures and that the live experiment was frozen as not executed. |

---

## Visual Media & Screenshots

- **[screenshots/README.md](screenshots/README.md)**: Guide for capturing, naming, and adding screenshots of the live running web application.
