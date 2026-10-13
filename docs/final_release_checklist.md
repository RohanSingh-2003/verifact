# VeriFact v1.0.0 Final Release Checklist

> **Historical Document Notice**:
> This checklist records the original release verification performed on **2026-09-04** for VeriFact v1.0.0. Subsequent repository evolutions (such as Git repository initialization, CI workflows, and the retirement of the live 2×2 experiment runner/UI dashboard in favor of an archival file structure) are annotated below while preserving the historical release record.

**Original Verification Date**: 2026-09-04
**Preserved Frozen Experiment**: `58baff20-fb86-4f43-b20e-895a086ceb6b` (mock study)

---

## Research (Historical Study)

- [x] MetaQA implementation verified
- [x] Scoring verified
- [x] Zero-resource constraint preserved
- [x] 2×2 design verified
- [x] Fixed mutation control verified (A→A/A→B and B→A/B→B share answer + mutation_set_hash in locked CSV)
- [x] Results frozen (`experiments/results/58baff20-fb86-4f43-b20e-895a086ceb6b/`)
- [x] Statistical analysis verified against saved CSVs
- [x] Limitations documented

## Backend

- [x] FastAPI starts
- [x] API health works
- [x] Detection works (mock and cloud API)
- [x] Persistence works (SQLite storage)
- [x] Experiment results accessible *(Historical: verified during release; active runner and endpoints subsequently retired in post-v1.0 refactoring)*
- [x] Error handling works (empty question 422; missing resource 404; missing live key blocked)
- [x] Tests pass *(Historical: 252 tests passing at v1.0.0 release; 458 backend test items collected at the time of the post-cleanup audit)*

## Frontend

- [x] Detect works (API + progressive streaming flow)
- [x] History works (API + UI flow implemented)
- [x] Experiment dashboard works *(Historical: verified at v1.0.0; subsequently retired from active navigation in post-v1.0 cleanup)*
- [x] Loading states work
- [x] Error states work
- [x] Responsive layout checked (tables scroll; sidebar/mobile nav present)
- [ ] No console errors (browser pass)

## Security

- [x] No API keys committed in source/docs (test placeholders only)
- [x] `.env` ignored in `.gitignore`
- [x] `.env.example` safe
- [x] No frontend secrets (`/api/settings` exposes no secret values)
- [x] No secrets in docs/results

## Documentation

- [x] README complete
- [x] Methodology complete
- [x] Architecture complete
- [x] Demo script complete
- [x] Interview explanation complete
- [x] Viva questions complete
- [x] Release notes complete

## GitHub & Environment

- [x] `.gitignore` covers env, venv, node_modules, dist, db
- [x] No unnecessary new dependencies added
- [x] CI configured (`.github/workflows/ci.yml`, mock mode)
- [x] Setup instructions verified (`py -3` documented for Windows)
- [x] Clean git history / remote *(Status update: repository initialized, tracked on `main`, synchronized with `origin/main`)*

## Release Status

- [x] Version 1.0.0
- [x] Final release notes
- [x] Final results locked (`docs/final_results_lock.md`)
- [x] Final tests passed (pytest, ruff, frontend build)
