# VeriFact v1.0.0 Final Release Checklist

Checked 2026-09-04 during release verification. Frozen experiment: `58baff20-fb86-4f43-b20e-895a086ceb6b` (mock).

## Research

- [x] MetaQA implementation verified
- [x] Scoring verified
- [x] Zero-resource constraint preserved
- [x] 2×2 design verified
- [x] Fixed mutation control verified (A→A/A→B and B→A/B→B share answer + mutation_set_hash in locked CSV)
- [x] Results frozen
- [x] Statistical analysis verified against saved CSVs
- [x] Limitations documented

## Backend

- [x] FastAPI starts
- [x] API health works
- [x] Detection works (mock)
- [x] Persistence works
- [x] Experiment results accessible (SQLite latest; frozen ID preferred when present)
- [x] Error handling works (empty question 422; missing experiment 404; missing live key blocked)
- [x] Tests pass

## Frontend

- [x] Detect works (API + UI flow implemented)
- [x] History works (API + UI flow implemented)
- [x] Experiment dashboard works (prefers frozen ID; DEMO banners)
- [x] Loading states work
- [x] Error states work
- [x] Responsive layout checked (tables scroll; sidebar/mobile nav present)
- [ ] No console errors (not verified in a browser this pass)

## Security

- [x] No API keys committed in source/docs (test placeholders only)
- [x] .env ignored (gitignore); this workspace is not a git repo yet
- [x] .env.example safe
- [x] No frontend secrets (`/api/settings` has no key)
- [x] No secrets in docs/results

## Documentation

- [x] README complete
- [x] Methodology complete
- [x] Experiment methodology complete
- [x] Results complete
- [x] Discussion complete
- [x] Architecture complete
- [x] Demo script complete
- [x] Interview explanation complete
- [x] Viva questions complete

## GitHub

- [x] .gitignore covers env, venv, node_modules, dist, db
- [x] No unnecessary new dependencies added this pass
- [x] CI configured (`.github/workflows/ci.yml`, mock mode)
- [x] Setup instructions verified (`py -3` documented for Windows)
- [ ] Clean git history / remote (no `.git` in this workspace)

## Release

- [x] Version 1.0.0
- [x] Final release notes
- [x] Final results locked
- [x] Final tests passed (pytest, ruff, frontend build)
