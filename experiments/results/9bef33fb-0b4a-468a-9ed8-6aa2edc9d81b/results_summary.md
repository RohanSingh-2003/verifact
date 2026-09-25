# VeriFact results summary

This file is generated from stored experiment data. It is not a substitute for the raw traces.

**DEMO / MOCK DATA — not a live-model research result.**

### Dataset
- Name: pilot
- Version: 1.0
- Questions used: 40

### Models
- Generators: model-a, model-b
- Verifiers: model-a, model-b
- Mode: DEMO / MOCK DATA

### Experimental setup
- Mutations: 5 synonym + 5 antonym
- Threshold: 0.5
- Trials: 1
- Temperature: 0.0
- Mutation reuse valid: True

### MetaQA evaluation
Baseline detector metrics are stored on the separate evaluation run, not in this 2×2 experiment file.

### 2×2 experiment
- A → A: mean=0.0 n=40 Reliable%=1.0 Hallucinated%=0.0
- A → B: mean=1.0 n=40 Reliable%=0.0 Hallucinated%=1.0
- B → A: mean=0.0 n=40 Reliable%=1.0 Hallucinated%=0.0
- B → B: mean=1.0 n=40 Reliable%=0.0 Hallucinated%=1.0

### Statistical results
- Generator model-a: same=0.0 cross=1.0 difference=-1.0 flip_rate=1.0 p<0.001 effect_size=-1.0 significant=True exploratory=False
- Generator model-b: same=1.0 cross=0.0 difference=1.0 flip_rate=1.0 p<0.001 effect_size=1.0 significant=True exploratory=False

### Classification flips
- Overall flip rate: 1.0

### Category analysis
- date / model-a: n=8 difference=-1.0 flip_rate=1.0
- date / model-b: n=8 difference=1.0 flip_rate=1.0
- general_fact / model-a: n=8 difference=-1.0 flip_rate=1.0
- general_fact / model-b: n=8 difference=1.0 flip_rate=1.0
- location / model-a: n=8 difference=-1.0 flip_rate=1.0
- location / model-b: n=8 difference=1.0 flip_rate=1.0
- named_entity / model-a: n=8 difference=-1.0 flip_rate=1.0
- named_entity / model-b: n=8 difference=1.0 flip_rate=1.0
- numeric / model-a: n=8 difference=-1.0 flip_rate=1.0
- numeric / model-b: n=8 difference=1.0 flip_rate=1.0

### Limitations
- Results apply only to the selected models, dataset, prompts, and mutation configuration.
- They do not establish a universal self-verification bias.
- Ground-truth matching is applied after detection and may mark items Needs Review.
- See docs/limitations.md.

### Key finding
DEMO / MOCK DATA. Empirical result on dataset 'pilot'. Same-model verification produced lower hallucination scores for Generator A, with a statistically significant paired difference (p<0.001). Same-model verification produced higher hallucination scores for Generator B, with a statistically significant paired difference (p<0.001).
