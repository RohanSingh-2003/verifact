# VeriFact AI Agent Guidelines & Safety Guardrails

This document establishes operational rules, security constraints, and safety guardrails for AI coding agents (including Google Antigravity, Claude, Cursor, and similar assistant tools) working within the VeriFact codebase.

> **Important Limitation Notice:**  
> These guidelines provide clear directives to compatible AI coding assistants; they do **not** constitute an automated security sandbox or a cryptographically enforced restriction mechanism. They rely on the agent's prompt compliance. Human review, verified repository settings, and Git branch protection rules remain essential.

---

## 1. Secrets, Credentials, and Environment Protection
1. **Never Expose Credentials**: Never print, copy into conversational responses, commit, or transmit API keys, tokens, passwords, or credentials.
2. **Masked Inspection Only**: If checking environment configuration or health status, report only variable names and masked status indicators (e.g. `[CONFIGURED, length=N]`). Never print raw secret values.
3. **Never Stage Secrets**: Never stage or commit `.env`, `backend/.env`, or any file containing real credentials. Real keys must remain exclusively inside the local, unversioned `backend/.env` file.
4. **Template Files Only**: Only update `.env.example`, `backend/.env.example`, or `frontend/.env.example` when documenting new configuration keys, and ensure template values remain strictly empty placeholders.

---

## 2. Git & Version Control Safety
1. **Destructive Commands Prohibited**: Never execute `git push --force`, `git push --force-with-lease`, `git reset --hard`, `git rebase`, `git clean`, or bulk deletion commands (`rm -rf`, `Remove-Item -Recurse -Force`) without explaining the exact consequences and obtaining explicit user approval first.
2. **No Unapproved History Rewrites**: Never rewrite Git history, amend past commits, delete branches, alter remotes, or change repository visibility without explicit user consent.
3. **Atomic & Focused Commits**: When committing approved changes, keep commits focused strictly on the approved task.

---

## 3. Protection of Research Artifacts & Benchmarks
1. **Protected Frozen Experiments**: Treat all files in `experiments/`—specifically frozen mock run `experiments/results/58baff20-fb86-4f43-b20e-895a086ceb6b/` and configuration `experiments/config/final_experiment.yaml`—as immutable research artifacts. Never overwrite, edit, or delete them without explicit approval.
2. **Protected Analysis Outputs**: Do not overwrite or delete generated charts, figures, and CSV tables in `analysis/output/`.
3. **Protected Benchmark Datasets**: Do not alter evaluation datasets (`backend/data/datasets/pilot.json` and `pilot.manifest.json`).
4. **Documentation Locks**: Preserve research audit documentation in `docs/final_results_lock.md` and related evaluation specifications.

---

## 4. Preservation of Core Detection Methodologies
1. **Algorithm Integrity**: Do not modify the MetaQA metamorphic testing operators (`backend/app/metaqa/mutation.py`), deterministic scoring matrix (`backend/app/metaqa/scoring.py`), classification thresholds ($\theta = 0.5$), or evaluation formulas during security or refactoring tasks unless explicitly requested by the user.
2. **Architecture Contract**: Preserve the dedicated model roles where Gemma 4:26B generates answers and mutations while configured cloud models act as the multi-model verifier pool and direct-answer reviewers.
3. **Metric Separation**: Never blend or collapse the Web Evidence Consistency Score into the MetaQA Hallucination Score.

---

## 5. Scope Boundaries & Change Minimization
1. **Strict Task Scoping**: Do not touch files, components, or configurations outside the scope of the approved user instruction.
2. **Minimal & Reversible Edits**: Prefer the smallest, cleanest, and most reversible change that satisfies the requirement. Avoid unsolicited bulk refactoring.
3. **Dependency Discipline**: Do not add, remove, or upgrade dependencies in `backend/requirements.txt` or `frontend/package.json` without explicit approval.

---

## 6. Pre-Implementation Inspection
1. **Inspect Before Modifying**: Always read and inspect existing code, schemas, and tests before making modifications.
2. **Verify Execution Flow**: Base all documentation, diagrams, and changes on actual source-code behavior rather than assumptions.

---

## 7. Post-Implementation Verification & Reporting
1. **Run Relevant Automated Tests**: After every code modification, execute existing test suites:
   - Backend: `pytest` in `backend/`
   - Frontend: `npm test` and `npm run build` in `frontend/`
2. **Accurate Reporting**: Report every file modified or created, all checks performed, and any warnings or failures. Never claim an issue is fixed or secure without verification.
