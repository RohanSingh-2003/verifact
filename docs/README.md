# VeriFact Technical Documentation Index

> **Master Directory of Architecture Specifications, Mathematical Formulations, Reverse Engineering Audits, and Research Artifacts**

This directory contains comprehensive technical architecture documents, reverse engineering reports, mathematical formulations, audit locks, and research specifications detailing the inner workings of the VeriFact system.

For initial setup, quick-start commands, and runtime configuration, refer to the root [README.md](../README.md).

---

## 1. Master Technical Audit & Architecture Dossier

These authoritative documents provide complete, line-by-line reverse engineering and architectural reconstruction of the VeriFact codebase:

| Document | Purpose & Contents |
| :--- | :--- |
| **[COMPLETE_PROJECT_TECHNICAL_AUDIT.md](COMPLETE_PROJECT_TECHNICAL_AUDIT.md)** | Exhaustive 15-phase reverse engineering audit covering system architecture, dual verification pipelines, multi-model pool, algorithms, database schema, evaluation benchmarks, and test coverage. |
| **[COMPLETE_SYSTEM_ARCHITECTURE.md](COMPLETE_SYSTEM_ARCHITECTURE.md)** | System architecture diagrams, component communication contracts, async threading models, reverse proxy setup, and data flow. |
| **[END_TO_END_PIPELINES.md](END_TO_END_PIPELINES.md)** | Step-by-step Mermaid sequence diagrams, data schemas, and runtime execution traces for all 7 application pipelines. |
| **[AI_MODELS_AND_ALGORITHMS.md](AI_MODELS_AND_ALGORITHMS.md)** | KaTeX mathematical proofs, worked numerical examples, and algorithm specifications for MetaQA Equation 5, Web Consistency, and Risk Fusion. |
| **[API_AND_DATABASE_REFERENCE.md](API_AND_DATABASE_REFERENCE.md)** | Complete REST endpoint catalogue, SQLite relational schema, JSON serialization strategy, and Pydantic schemas. |
| **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** | Rigorous code vs. documentation discrepancy matrix, test execution audit, honest limitations, and viva voce defense guide. |

---

## 2. Core Product & Methodology Documentation

These documents describe the operational design, mathematical foundations, and system boundaries:

| Document | Purpose & Contents |
| :--- | :--- |
| **[architecture.md](architecture.md)** | Software architecture, component topology, FastAPI background parallel execution, and multi-model cloud client adapters. |
| **[methodology.md](methodology.md)** | Mathematical formulation of MetaQA metamorphic relations, claim parsing, mutation types, scoring contribution matrix, Web Evidence domain strategies, and Overall Assessment synthesis. |
| **[project_description.md](project_description.md)** | Executive project description, problem statement, dual verification methodology, and cloud LLM implementation for evaluators and researchers. |
| **[limitations.md](limitations.md)** | Rigorous analysis of system boundaries, internal consistency vs. physical truth, retrieval constraints, and heuristic scoring disclaimers. |
| **[temporal_validation_policy.md](temporal_validation_policy.md)** | Formal temporal policy for evaluating FreshQA queries relative to the April 21, 2026 snapshot date. |
| **[demo_script.md](demo_script.md)** | Step-by-step walkthrough script demonstrating the interactive Detect experience. |
| **[interview_explanation.md](interview_explanation.md)** | Elevator pitches, technical architecture summaries, and comprehensive Q&A for project defense. |
| **[release_notes.md](release_notes.md)** | Milestone history, completed features, and roadmap for future extensions. |
| **[final_release_checklist.md](final_release_checklist.md)** | Release verification checklist recording release milestones and code audit notes. |

---

## 3. Historical Research & Evaluation Documents (Archival 2×2 Study)

Prior to final product release, VeriFact was used to evaluate same-model versus cross-model verifier behaviors ($A \to A, A \to B, B \to A, B \to B$) with frozen mutation sets. The experiment runner and endpoints have since been retired, and the historical records remain preserved for reproducible audit:

| Document | Purpose & Contents |
| :--- | :--- |
| **[final_results_lock.md](final_results_lock.md)** | Immutable research artifact audit lock for the frozen 40-question mock study (`58baff20-fb86-4f43-b20e-895a086ceb6b`). Records that the run used deterministic mock fixtures and that the live experiment configuration (`final_experiment.yaml`) was unexecuted. |

---

## 4. Visual Media & Screenshots

- **[screenshots/README.md](screenshots/README.md)**: Guide for capturing, naming, and adding screenshots of the live running web application.
