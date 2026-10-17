# VeriFact — Engineering Rules & Operational Guidelines

**Document Version**: 1.0.0 (Release Freeze)
**Target Audience**: Software Engineers, Research Contributors, and AI Coding Assistants (Google Antigravity, Claude, Cursor, Codex)
**Parent Authority**: This document operates in tandem with and formalizes the policies defined in [`AGENTS.md`](./AGENTS.md).

---

## 1. Prime Directives & Ironclad Constraints

The following rules are non-negotiable. Violations jeopardize project security, research validity, and repository integrity.

### 1.1 Secrets & Environment Security
1. **Never Expose Credentials**: Never print, log, stage, commit, or transmit API keys, tokens, passwords, or credentials in conversation, code, or documentation.
2. **Masked Inspection Only**: When inspecting environment variables or provider status, report only variable names and masked status indicators (e.g., `[CONFIGURED, length=N]`).
3. **No Secret Staging**: Real credentials reside strictly inside the local, unversioned `backend/.env` file. Never stage `.env` files.
4. **Placeholder Templates Only**: Only modify `.env.example`, `backend/.env.example`, or `frontend/.env.example` when introducing new configuration parameters, and ensure values remain strictly empty placeholders (e.g., `OLLAMA_API_KEY=`).

### 1.2 Git & Version Control Safeguards
1. **Destructive Commands Prohibited**: Never execute `git push --force`, `git push --force-with-lease`, `git reset --hard`, `git rebase`, `git clean`, or bulk filesystem deletions (`rm -rf`, `Remove-Item -Recurse -Force`) without obtaining explicit, written user approval first.
2. **Preserve Teammate Work**: Never discard, overwrite, revert, or modify uncommitted or committed changes made by teammates.
3. **No Unapproved History Rewrites**: Never amend past commits, delete remote branches, alter remotes, or modify repository visibility.
4. **Atomic & Focused Commits**: Commits must be scoped strictly to the approved task with clear conventional commit messages (e.g., `feat(frontend): ...`, `fix(backend): ...`, `docs: ...`).

### 1.3 Research Artifact & Benchmark Protection
1. **Protected Frozen Experiments**: Treat all files in `experiments/`—specifically the frozen mock run directory `experiments/results/58baff20-fb86-4f43-b20e-895a086ceb6b/` and configuration `experiments/config/final_experiment.yaml`—as immutable research artifacts. Never overwrite or delete them.
2. **Protected Analysis Outputs**: Never delete or overwrite generated charts, figures, and CSV tables in `analysis/output/`.
3. **Protected Benchmark Datasets**: Do not alter evaluation datasets (`backend/data/datasets/pilot.json` and `pilot.manifest.json`).
4. **Protected Documentation Locks**: Preserve research audit documentation in `docs/final_results_lock.md`.

---

## 2. Research & Algorithmic Integrity

1. **Algorithm Preservation**: Do not modify the MetaQA metamorphic testing operators (`backend/app/metaqa/mutation.py`), deterministic scoring matrix (`backend/app/metaqa/scoring.py`), or evaluation formulas during refactoring or UI updates.
2. **Threshold Lock**: The classification decision boundary is fixed at $\theta = 0.50$ (derived from Yang et al., *ACM FSE 2025*). Never alter this threshold to make tests pass.
3. **Metric Separation**: **Never blend, average, or collapse the Web Evidence Consistency Score into the MetaQA Hallucination Score.** They are orthogonal signals and must remain distinct.
4. **Role Architecture Integrity**: Gemma 4:26B generates answers and mutations. Configured cloud models act as the multi-model verifier pool and direct-answer reviewers. **The answer generator must never review itself.**
5. **Absence is Not Falsity**: In Web Evidence, an unretrieved or missing source must never be presented as proof that a claim is false. Claims without relevant sources must be classified as `NOT_ASSESSED_NO_RELEVANT_SOURCE` and excluded from consistency scoring.
6. **Failed Verifiers are Not Refutations**: When an API call to a verifier fails due to a rate limit or timeout, record status as `FAILED`. Never silently convert a failure into a negative or contradictory verdict.

---

## 3. Codebase Conventions & Standards

### 3.1 Backend (Python & FastAPI)
- **Runtime**: Python 3.12 managed with virtual environment (`backend/.venv/`).
- **Framework**: FastAPI with Pydantic v2 schemas and SQLAlchemy 2.0 ORM.
- **Typing**: Strict type annotations on all functions (`def foo(param: str) -> bool:`). Use `from __future__ import annotations` where needed.
- **Formatting & Linting**: Ruff / Flake8 compliance. Keep imports sorted: standard library, third-party, application local.
- **Database Access**: Always use context managers or `try...finally` blocks with `db.close()` or dependency injection `db: Session = Depends(db_dep)`. Never leave database sessions open.
- **Async Concurrency**: Use `asyncio.gather` for concurrent network requests. Always wrap external provider HTTP calls in timeouts and defensive exception handlers.

### 3.2 Frontend (React & TypeScript)
- **Runtime**: React 19, TypeScript 5.7, Vite.
- **Styling**: Tailwind CSS v4 with semantic CSS variables defined in `frontend/src/index.css`.
- **Iconography**: Use `lucide-react`. Do not introduce arbitrary SVG strings or icons outside the design system.
- **Theme Support**: Every UI component must render correctly in Light, Dark, and System modes using semantic tokens (`bg-surface`, `text-ink`, `border-line`, `text-reliable`, etc.).
- **Component Scope**: Keep components focused. Reusable primitives reside in `components/ui/`, layout wrappers in `components/layout/`, and page-specific logic in `components/detect/` or `pages/`.
- **No Unused Code**: Avoid unused imports or orphan variables. Run `npm run lint` (`oxlint`) to verify.

### 3.3 API Schema Synchronization
- Whenever modifying API response models in `backend/app/schemas/detect.py` or `routes_settings.py`, update the corresponding TypeScript interfaces in `frontend/src/types/index.ts` and fetch mappers in `frontend/src/services/api.ts`.
- Field names in JSON must follow Python `snake_case` in backend schemas and map predictably to TypeScript `camelCase` in frontend types.

---

## 4. Verification & Testing Standards

1. **Pre-Implementation Inspection**: Always inspect existing code, schemas, and tests before making modifications. Base all changes on actual source-code behavior rather than assumptions.
2. **Run Tests After Every Modification**:
   - Backend: Run `pytest -q` inside `backend/` using the virtual environment (`.\.venv\Scripts\pytest -q`).
   - Frontend: Run `npm test` and `npm run lint` inside `frontend/`.
3. **Verify Production Builds**: Run `npm run build` in `frontend/` to confirm TypeScript typechecking (`tsc -b`) and Vite production bundle generation succeed.
4. **Accurate Reporting**:
   - Report every file modified or created.
   - Report actual pass/fail/skip counts.
   - **Never claim an issue is fixed or secure without verification.**
   - **Never claim a test passed unless it was actually executed.**
   - **Never claim live cloud provider integration was tested if only mocks were used.**

---

## 5. Summary Table: What to Do vs. What NOT to Do

| Action Category | Allowed & Required | Strictly Prohibited |
|---|---|---|
| **API Keys & Secrets** | Masked inspection, placeholder `.env.example` templates. | Printing keys, staging `.env`, committing credentials. |
| **Git Operations** | Atomic commits, clear commit messages, forward pushes. | `git push --force`, `git reset --hard`, rewriting past commits. |
| **Research Datasets** | Read-only inspection, benchmarking against `pilot.json`. | Editing `pilot.json`, altering frozen experiment UUIDs. |
| **Methodology** | Deterministic Eq. 5 scoring, threshold $\theta = 0.50$, metric separation. | Blending web scores into MetaQA, relaxing thresholds to pass tests. |
| **Verifier Pool** | Cross-model review (Phi-4, GLM, Qwen, Liquid), handling failures. | Allowing Gemma 4:26B to verify itself; treating failed calls as `NO`. |
| **Web Evidence** | 6-tier authority ranking, excluding unassessed claims. | Conflating missing evidence with proof of falsehood. |
| **User Interface** | Desaturated palette, accessible math rendering, light/dark themes. | Flashy neon colors, raw LaTeX entities, decorative clutter in settings. |
