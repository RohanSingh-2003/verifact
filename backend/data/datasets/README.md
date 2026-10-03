# Evaluation Datasets

This directory contains benchmark and evaluation datasets used to measure VeriFact's hallucination detection accuracy against curated ground-truth data.

---

## Dataset Format Specifications

Datasets can be provided in either **JSON** or **CSV** format.

### 1. JSON Schema

```json
{
  "name": "pilot_evaluation",
  "version": "1.0",
  "examples": [
    {
      "id": "q001",
      "question": "What is the capital of Australia?",
      "reference_answer": "Canberra",
      "aliases": ["Canberra, Australia"],
      "ground_truth_label": null,
      "category": "location",
      "source": "curated",
      "needs_review": false
    }
  ]
}
```

### 2. CSV Schema

| Column | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `id` | string | **Yes** | Unique identifier for the question example (e.g., `q001`). |
| `question` | string | **Yes** | Factual question evaluated by the model. |
| `reference_answer` | string | **Yes** | Gold standard factual answer. |
| `aliases` | string | No | Pipe-delimited list of accepted equivalent answers (`Canberra\|Canberra, ACT`). |
| `ground_truth_label`| string | No | Evaluator label of answer correctness (`Reliable` or `Hallucinated`). |
| `category` | string | No | Question domain: `named_entity`, `date`, `numeric`, `location`, `general_fact`. |
| `source` | string | No | Dataset provenance or source tag. |
| `needs_review` | bool | No | Flags items requiring manual human review. |
| `mock_base_answer` | string | No | Deterministic answer used exclusively when `LLM_MODE=mock`. |
| `mock_scenario` | string | No | Deterministic scenario used exclusively when `LLM_MODE=mock`. |

---

## Evaluation Workflow

When an evaluation is triggered via `POST /api/evaluations/run`:

1. The candidate generator model answers each question in the dataset.
2. The generated answer is compared against the reference answer and aliases.
3. If an answer cannot be labeled automatically with high confidence, the system flags `needs_review=true` and excludes that row from automatic precision/recall metrics while preserving the raw row for inspection.
4. MetaQA executes across the generated answers to compute accuracy, precision, recall, and F1 scores against the ground-truth labels.

---

## External Benchmark Datasets

- **TruthfulQA**: Raw TruthfulQA files are **not** bundled in the repository due to licensing. To evaluate on TruthfulQA, export your curated subset into `truthfulqa.json` or `truthfulqa.csv` matching the schema above.
- **Mock Safety**: Mock answers and scenarios (`mock_base_answer`, `mock_scenario`) are used solely during automated test runs with `LLM_MODE=mock` and are never dispatched to live LLMs.
