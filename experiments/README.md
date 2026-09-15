# Experiment artifacts

The locked research run is:

`58baff20-fb86-4f43-b20e-895a086ceb6b`

Mode: **mock** (DEMO / MOCK DATA). See `docs/final_results_lock.md`.

| Folder | Contents |
| --- | --- |
| `config/` | Intended live configuration (not executed) |
| `raw/` | Per-run generation traces |
| `processed/` | Condition tables, paired differences, sweeps |
| `results/` | `results_summary.md` and frozen config copies |
| `charts/` | Optional per-run chart exports |

Pytest can write additional short mock runs. Those are development traces, not live-model findings. Do not cite them as paper results.
