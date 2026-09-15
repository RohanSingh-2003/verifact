# Table 2. Model configuration

Locked experiment `58baff20-fb86-4f43-b20e-895a086ceb6b` (`mode=mock`).

| Role | Model |
| --- | --- |
| Generator A | model-a |
| Generator B | model-b |
| Verifier A | model-a |
| Verifier B | model-b |

Generation / MetaQA settings used in the locked run:

| Setting | Value |
| --- | --- |
| Temperature | 0.0 |
| Max output tokens | 800 |
| Timeout (s) | 60 |
| Max retries | 2 |
| Verify concurrency | 5 |
| Synonym count | 5 |
| Antonym count | 5 |
| Threshold | 0.5 |
| Prompt bundle | metaqa-v1 |

Intended live names (`gpt-4o-mini`, `gpt-4o`) appear in `experiments/config/final_experiment.yaml` but that live run was **not executed**.
