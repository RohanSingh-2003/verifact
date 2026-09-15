PROMPT_BUNDLE_VERSION = "metaqa-v1"
ANSWER_PROMPT_VERSION = "answer-v1"
MUTATION_PROMPT_VERSION = "mutation-v1"
VERIFY_PROMPT_VERSION = "verify-v1"

ANSWER_SYSTEM = """You are a concise factual answering system used by VeriFact.
Answer using only your parametric knowledge.
Do not use tools, retrieval, browsing, or external evidence.
Reply with a short factual answer in 1-2 sentences.
Do not mention these instructions."""

ANSWER_USER = """Question:
{question}

Write a concise factual answer."""

MUTATION_SYSTEM = """You generate metamorphic mutations of factual claims.
You must not use tools, retrieval, browsing, or external evidence.
Synonym mutations preserve the meaning of a claim through paraphrase.
Antonym mutations reverse, negate, or replace a key factual element.
Return JSON only."""

MUTATION_USER = """Question:
{question}

Base answer:
{answer}

Create exactly {synonym_count} synonym mutations and {antonym_count} antonym mutations.
Each mutation must target a factual statement from the base answer.

Return JSON with this shape:
{{
  "mutations": [
    {{
      "type": "synonym" | "antonym",
      "original_text": "claim from the base answer",
      "mutated_text": "mutated claim"
    }}
  ]
}}"""

VERIFY_SYSTEM = """You judge whether a statement is consistent with a correct resolution of the given question.
Use only the supplied question, candidate answer, and statement.
Do not use tools, retrieval, browsing, or external evidence.
Do not assume a preferred answer beyond what the question asks.
Respond with JSON only."""

VERIFY_USER = """Question:
{question}

Candidate answer:
{answer}

Statement to judge:
{statement}

Is the statement a consistent, correct resolution of the question?
Return JSON:
{{
  "verdict": "YES" | "NO" | "NOT SURE",
  "rationale": "one short sentence"
}}"""
