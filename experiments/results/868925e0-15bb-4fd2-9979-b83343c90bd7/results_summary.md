# VeriFact results summary

This file is generated from stored experiment data. It is not a substitute for the raw traces.

**DEMO / MOCK DATA — not a live-model research result.**

### Dataset
- Name: mini
- Version: 1.0
- Questions used: 1

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
- A → A: mean=0.0 n=1 Reliable%=1.0 Hallucinated%=0.0
- A → B: mean=1.0 n=1 Reliable%=0.0 Hallucinated%=1.0
- B → A: mean=0.0 n=1 Reliable%=1.0 Hallucinated%=0.0
- B → B: mean=1.0 n=1 Reliable%=0.0 Hallucinated%=1.0

### Statistical results
- Generator model-a: same=0.0 cross=1.0 difference=-1.0 flip_rate=1.0 p=0.31731051 effect_size=-1.0 significant=False exploratory=True
- Generator model-b: same=1.0 cross=0.0 difference=1.0 flip_rate=1.0 p=0.31731051 effect_size=1.0 significant=False exploratory=True

### Classification flips
- Overall flip rate: 1.0

### Category analysis
- location / model-a: n=1 difference=-1.0 flip_rate=1.0
- location / model-b: n=1 difference=1.0 flip_rate=1.0

### Limitations
- Results apply only to the selected models, dataset, prompts, and mutation configuration.
- They do not establish a universal self-verification bias.
- Ground-truth matching is applied after detection and may mark items Needs Review.
- See docs/limitations.md.

### Key finding
DEMO / MOCK DATA. Empirical result on dataset 'mini'. Generator A: no statistically significant difference was detected between same-model and cross-model verification under these experimental conditions (p=0.31731051). This sample is small; treat the result as exploratory. Generator B: no statistically significant difference was detected between same-model and cross-model verification under these experimental conditions (p=0.31731051). This sample is small; treat the result as exploratory.
