# Table 1. Dataset

**DEMO / MOCK DATA** for the locked 2×2 run. Dataset file is the same `pilot` v1.0 used for intended live experiments.

| Field | Value |
| --- | --- |
| Name | pilot |
| Version | 1.0 |
| Path | `backend/data/datasets/pilot.json` |
| Manifest | `backend/data/datasets/pilot.manifest.json` |
| License / source | Original curated items for VeriFact research. Not TruthfulQA. |
| Questions | 40 |
| Categories | named_entity (8), location (8), date (8), numeric (8), general_fact (8) |
| Ground-truth construction | Reference answer + aliases. Reliable = generated answer supported by the reference; Hallucinated = conflict. Ambiguous cases = Needs Review. |
| Needs Review IDs | q032, q039 |
| Items in automatic P/R/F1 | 38 |
| Detector input | question only (no reference text) |

Source: `backend/data/datasets/pilot.manifest.json`; locked experiment `58baff20-fb86-4f43-b20e-895a086ceb6b`.
