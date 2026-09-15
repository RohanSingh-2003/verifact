# Evaluation datasets

Place curated evaluation files here.

## Local format (JSON)

```json
{
  "name": "pilot",
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

CSV is also supported. Required columns: `id`, `question`, `reference_answer`.
Optional: `ground_truth_label`, `category`, `source`, `aliases` (pipe-separated), `needs_review`, `mock_base_answer`, `mock_scenario`.

Categories: `named_entity`, `date`, `numeric`, `location`, `general_fact`.

`ground_truth_label` is a label of **generated-answer correctness** (`Reliable` or `Hallucinated`), not a property of the question.

Needs Review: if a generated answer cannot be labeled confidently (dataset flag, empty/uncertain answer, or ambiguous reference match), the evaluator stores `Needs Review` and excludes that item from automatic precision/recall/F1. The raw evaluation row is kept.

`mock_base_answer` / `mock_scenario` are used only when `LLM_MODE=mock`. They are never sent to live MetaQA prompts.

A machine-readable manifest (`*.manifest.json`) lists question IDs, categories, reference answers, and license/source information. Ground truth in that file is evaluation-layer metadata only.

## TruthfulQA

TruthfulQA is **not** bundled. To evaluate on it, export a curated subset into `truthfulqa.json` or `truthfulqa.csv` using this schema. VeriFact will not invent TruthfulQA items.
