# Experiment Artifacts (Research Reference)

This directory stores offline research artifacts, frozen configuration copies, and raw/processed data from the earlier 2×2 same-model versus cross-model verifier investigation ($A \to A, A \to B, B \to A, B \to B$).

### Locked Research Run
- **Artifact ID**: `58baff20-fb86-4f43-b20e-895a086ceb6b`
- **Execution Mode**: `mock` (DEMO / MOCK DATA)
- **Reference Documentation**: Refer to [`docs/final_results_lock.md`](../docs/final_results_lock.md) and [`docs/experiment_methodology.md`](../docs/experiment_methodology.md).

---

## Directory Organization

| Directory | Contents |
| :--- | :--- |
| `config/` | Intended live configuration parameters. |
| `raw/` | Per-run generation and verification traces. |
| `processed/` | Formatted condition tables, paired score differences, and threshold sweeps. |
| `results/` | `results_summary.md` and frozen configuration snapshots. |
| `charts/` | Exported comparison charts and score distribution visualizations. |

---

## Relationship to Current Product

- **Independent from Main UI**: The 2×2 experiment matrix was an offline research study conducted during system development. It is not part of the primary user-facing Detect interface.
- **Backend Test Preservation**: Experiment data structures and orchestration logic are preserved in `backend/app/api/routes_experiments.py` and tested via `pytest backend/tests/test_experiments.py` to ensure historical reproducibility without cluttering the primary user product.
- **Trace Notice**: Test runs executed during automated CI/pytest runs may write temporary mock traces. Those are development traces and must not be cited as live research results.
