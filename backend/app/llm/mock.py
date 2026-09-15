from __future__ import annotations

from typing import Any, Literal

from app.llm.base import LLMClient, LLMError
from app.metaqa.scoring import MutationType

MockScenario = Literal["reliable", "hallucinated", "uncertain", "mixed", "malformed_verifier"]

ORIGINAL = "Sydney is the capital of Australia."

DEFAULT_MUTATIONS: list[dict[str, str]] = [
    {"type": MutationType.SYNONYM.value, "original_text": ORIGINAL, "mutated_text": "Australia's capital city is Sydney."},
    {"type": MutationType.SYNONYM.value, "original_text": ORIGINAL, "mutated_text": "Sydney serves as the capital of Australia."},
    {"type": MutationType.SYNONYM.value, "original_text": ORIGINAL, "mutated_text": "The national capital of Australia is Sydney."},
    {"type": MutationType.SYNONYM.value, "original_text": ORIGINAL, "mutated_text": "Sydney is Australia's capital city."},
    {"type": MutationType.SYNONYM.value, "original_text": ORIGINAL, "mutated_text": "The Australian capital is the city of Sydney."},
    {"type": MutationType.ANTONYM.value, "original_text": ORIGINAL, "mutated_text": "The capital of Australia is Canberra."},
    {"type": MutationType.ANTONYM.value, "original_text": ORIGINAL, "mutated_text": "Sydney is not the capital of Australia."},
    {"type": MutationType.ANTONYM.value, "original_text": ORIGINAL, "mutated_text": "Canberra, not Sydney, is the capital of Australia."},
    {"type": MutationType.ANTONYM.value, "original_text": ORIGINAL, "mutated_text": "The capital of Australia is Melbourne."},
    {"type": MutationType.ANTONYM.value, "original_text": ORIGINAL, "mutated_text": "Australia does not have Sydney as its capital city."},
]

SCENARIO_VERDICTS: dict[str, list[str]] = {
    "reliable": ["YES"] * 5 + ["NO"] * 5,
    "hallucinated": ["NO"] * 5 + ["YES"] * 5,
    "uncertain": ["NOT SURE"] * 10,
    "mixed": ["YES", "YES", "NO", "NOT SURE", "YES", "NO", "YES", "NO", "NOT SURE", "NO"],
    "malformed_verifier": ["???"] * 10,
}

# ── Built-in question-aware answers for mock mode ──────────────────────
# These provide realistic deterministic answers so that different questions
# produce different, contextually appropriate mock responses.
_BUILTIN_ANSWERS: dict[str, str] = {
    "what is the capital of india": "New Delhi is the capital of India.",
    "what is the capital of france": "Paris is the capital of France.",
    "who formulated the three laws of motion": "Isaac Newton formulated the three laws of motion.",
    "who wrote hamlet": "William Shakespeare wrote Hamlet.",
    "what is 2 + 2": "2 + 2 equals 4.",
    "what is the capital of australia": "Sydney is the capital of Australia.",
    "explain recursion in simple terms": "Recursion is a programming technique where a function solves a problem by calling itself with a smaller input until it reaches a base case.",
    "what causes a solar eclipse": "A solar eclipse occurs when the Moon passes between the Earth and the Sun, temporarily blocking sunlight from reaching Earth.",
    "who wrote pride and prejudice": "Jane Austen wrote Pride and Prejudice.",
    "how does a refrigerator work": "A refrigerator works by circulating a refrigerant fluid that absorbs heat from inside the cabinet and expels it to the outside environment.",
    "why is the sky blue": "The sky appears blue because molecules in Earth's atmosphere scatter shorter blue wavelengths of sunlight more than longer wavelengths.",
    "can you explain how photosynthesis converts light energy into chemical energy": "Photosynthesis uses light energy captured by chlorophyll to convert carbon dioxide and water into oxygen and glucose.",
    "what is the speed of light": "The speed of light in a vacuum is approximately 299,792,458 meters per second.",
    "who painted the mona lisa": "Leonardo da Vinci painted the Mona Lisa.",
    "what is the largest planet in our solar system": "Jupiter is the largest planet in our solar system.",
    "who discovered penicillin": "Alexander Fleming discovered penicillin in 1928.",
    "what is the boiling point of water": "The boiling point of water is 100 degrees Celsius at standard atmospheric pressure.",
}


def _normalize_question_key(question: str) -> str:
    """Normalize question text for robust mock dictionary matching."""
    cleaned = question.strip().rstrip("?.!").strip().lower()
    return " ".join(cleaned.split())


def _builtin_answer(question: str) -> str:
    """Return a built-in answer or a deterministic clearly labeled mock response."""
    key = _normalize_question_key(question)
    if key in _BUILTIN_ANSWERS:
        return _BUILTIN_ANSWERS[key]
    # Backward compatibility with exact keys
    if question in _BUILTIN_ANSWERS:
        return _BUILTIN_ANSWERS[question]
    # Clearly labeled development mock response for unconfigured questions
    return f"[MOCK] No deterministic answer configured for this question: {question}"


# ── Dynamic mutation generation ────────────────────────────────────────

_SYNONYM_TEMPLATES: list[str] = [
    "In other words, {answer}",
    "To put it differently, {answer}",
    "Stated another way, {answer}",
    "That is to say, {answer}",
    "Put simply, {answer}",
]

_ANTONYM_TEMPLATES: list[str] = [
    "It is not the case that {answer}",
    "Contrary to popular belief, {answer} is incorrect.",
    "The opposite is true: {answer} is wrong.",
    "This is false: {answer}",
    "Actually, {answer} is a misconception.",
]


def _generate_dynamic_mutations(
    answer: str,
    synonym_count: int,
    antonym_count: int,
) -> list[dict[str, str]]:
    """Generate deterministic mutations from the actual base answer text."""
    answer_clean = answer.rstrip(".")
    mutations: list[dict[str, str]] = []
    for i in range(synonym_count):
        template = _SYNONYM_TEMPLATES[i % len(_SYNONYM_TEMPLATES)]
        mutations.append({
            "type": MutationType.SYNONYM.value,
            "original_text": answer,
            "mutated_text": template.format(answer=answer_clean),
        })
    for i in range(antonym_count):
        template = _ANTONYM_TEMPLATES[i % len(_ANTONYM_TEMPLATES)]
        mutations.append({
            "type": MutationType.ANTONYM.value,
            "original_text": answer,
            "mutated_text": template.format(answer=answer_clean),
        })
    return mutations


def _extract_base_answer(user_prompt: str) -> str:
    """Extract the base answer from a mutation-generation prompt."""
    marker = "Base answer:"
    if marker not in user_prompt:
        return ""
    remainder = user_prompt.split(marker, 1)[1]
    lines: list[str] = []
    for line in remainder.splitlines():
        stripped = line.strip()
        if stripped.startswith("Create exactly"):
            break
        if stripped:
            lines.append(stripped)
    return " ".join(lines)


class MockLLMClient(LLMClient):
    """Deterministic LLM stand-in for development and tests. Not a live provider."""

    def __init__(
        self,
        *,
        scenario: str = "reliable",
        answer: str | None = None,
        mutations: list[dict[str, str]] | None = None,
        verdicts: list[str] | None = None,
        fail_on: str | None = None,
        fail_verify_indices: set[int] | None = None,
        include_duplicates: bool = False,
        include_malformed_items: bool = False,
        answers_by_question: dict[str, str] | None = None,
        scenarios_by_question: dict[str, str] | None = None,
        answers_by_model: dict[str, dict[str, str]] | None = None,
        verdicts_by_model: dict[str, list[str]] | None = None,
        mutations_by_model: dict[str, list[dict[str, str]]] | None = None,
    ) -> None:
        self.scenario = scenario
        self._explicit_answer = answer is not None
        self.answer = answer or ORIGINAL
        self._explicit_mutations = mutations is not None
        self.mutations = list(mutations if mutations is not None else DEFAULT_MUTATIONS)
        self._explicit_verdicts = verdicts is not None
        self.verdicts = list(verdicts if verdicts is not None else SCENARIO_VERDICTS.get(scenario, SCENARIO_VERDICTS["reliable"]))
        self.fail_on = fail_on
        self.fail_verify_indices = set(fail_verify_indices or set())
        self.include_duplicates = include_duplicates
        self.include_malformed_items = include_malformed_items
        self.answers_by_question = dict(answers_by_question or {})
        self.scenarios_by_question = dict(scenarios_by_question or {})
        self.answers_by_model = {key: dict(value) for key, value in (answers_by_model or {}).items()}
        self.verdicts_by_model = {key: list(value) for key, value in (verdicts_by_model or {}).items()}
        self.mutations_by_model = {key: list(value) for key, value in (mutations_by_model or {}).items()}
        self._verify_index = 0
        self._current_question = ""
        self.answer_calls = 0
        self.mutation_calls = 0
        self.verify_calls = 0
        self.captured_system_prompts: list[str] = []
        self.captured_user_prompts: list[str] = []

    def _mutation_index(self, statement: str) -> int | None:
        needle = statement.strip()
        for index, item in enumerate(self.mutations):
            if item.get("mutated_text", "").strip() == needle:
                return index
        return None

    async def complete_text(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        self.captured_system_prompts.append(system_prompt)
        self.captured_user_prompts.append(user_prompt)
        if self.fail_on == "answer":
            raise LLMError("mock generator failure")
        self.answer_calls += 1
        question = extract_question(user_prompt)
        model_answers = self.answers_by_model.get(model, {})
        if question and question in model_answers:
            return model_answers[question]
        if question and question in self.answers_by_question:
            return self.answers_by_question[question]
        if question:
            norm_q = _normalize_question_key(question)
            matched_key = next((k for k in self.answers_by_question if _normalize_question_key(k) == norm_q), None)
            if matched_key:
                return self.answers_by_question[matched_key]
        # If no explicit answer was set, use the built-in question-aware mapping
        if not self._explicit_answer and question:
            return _builtin_answer(question)
        return self.answer

    async def complete_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        self.captured_system_prompts.append(system_prompt)
        self.captured_user_prompts.append(user_prompt)
        question = extract_question(user_prompt)
        self._apply_question_scenario(question)
        if "Statement to judge:" in user_prompt:
            self.verify_calls += 1
            statement = _extract_statement(user_prompt)
            index = self._mutation_index(statement)
            if index is None:
                index = self._verify_index
            self._verify_index += 1
            if self.fail_on == "verify" or index in self.fail_verify_indices:
                raise LLMError("mock verifier failure")

            # 1. If explicit model-specific verdicts were supplied, prioritize them
            if model in self.verdicts_by_model:
                v_list = self.verdicts_by_model[model]
                verdict = v_list[index % len(v_list)]
                return {"verdict": verdict, "rationale": "Deterministic mock rationale."}

            # 2. If caller passed explicit verdicts list, respect that
            if self._explicit_verdicts:
                verdict = self.verdicts[index % len(self.verdicts)]
                return {"verdict": verdict, "rationale": "Deterministic mock rationale."}

            # 3. Input-aware semantic verification:
            # Determine effective scenario for this question (stateless, question-specific)
            norm_q = _normalize_question_key(question) if question else ""
            scenario_key = next((k for k in self.scenarios_by_question if _normalize_question_key(k) == norm_q), None) if norm_q else None
            effective_scenario = self.scenarios_by_question[scenario_key] if scenario_key else self.scenario

            # Determine whether statement is meaning-reversing (antonym) or meaning-preserving (synonym)
            is_antonym = False
            if index is not None and index < len(self.mutations):
                is_antonym = (self.mutations[index].get("type") == MutationType.ANTONYM.value)
            else:
                is_antonym = _is_meaning_reversing(statement)

            verdict, rationale = _mock_verdict_for_scenario(effective_scenario, is_antonym, index)
            return {"verdict": verdict, "rationale": rationale}

        if self.fail_on == "mutations":
            raise LLMError("mock mutation failure")
        self.mutation_calls += 1

        # If explicit mutations were provided (tests) or model-specific mutations
        # exist, use them. Otherwise generate dynamic mutations from the actual
        # base answer found in the prompt.
        if model in self.mutations_by_model:
            payload: list[dict[str, Any]] = list(self.mutations_by_model[model])
        elif self._explicit_mutations:
            payload = list(self.mutations)
        else:
            base_answer = _extract_base_answer(user_prompt)
            if base_answer:
                payload = _generate_dynamic_mutations(base_answer, 5, 5)
                # Update self.mutations so _mutation_index works during verification
                self.mutations = payload
            else:
                payload = list(self.mutations)

        if self.include_malformed_items:
            payload = [
                {"type": "paraphrase", "original_text": "", "mutated_text": ""},
                {"type": "synonym", "original_text": ORIGINAL, "mutated_text": "   "},
                *payload,
            ]
        if self.include_duplicates and payload:
            payload = [*payload, payload[0], payload[-1]]
        return {"mutations": payload}

    def _apply_question_scenario(self, question: str) -> None:
        if not question or question not in self.scenarios_by_question:
            # Safely reset when question is not in scenarios_by_question
            if self._current_question:
                self._current_question = ""
                self._verify_index = 0
                if not self._explicit_verdicts:
                    self.verdicts = list(SCENARIO_VERDICTS.get(self.scenario, SCENARIO_VERDICTS["reliable"]))
            return
        if question == self._current_question:
            return
        self._current_question = question
        self._verify_index = 0
        scenario = self.scenarios_by_question[question]
        self.verdicts = list(SCENARIO_VERDICTS.get(scenario, SCENARIO_VERDICTS["reliable"]))


_REVERSAL_MARKERS: tuple[str, ...] = (
    "not the case",
    "contrary to",
    "is incorrect",
    "is wrong",
    "this is false",
    "misconception",
    "is not",
    "are not",
    "was not",
    "were not",
    "not the capital",
    "does not",
    "did not",
    "cannot",
    "never",
    "opposite is true",
    ", not ",
)


def _is_meaning_reversing(statement: str) -> bool:
    """Detect whether a statement contains semantic negation or refutation markers."""
    lower = statement.lower()
    return any(marker in lower for marker in _REVERSAL_MARKERS)


def _mock_verdict_for_scenario(scenario: str, is_antonym: bool, index: int) -> tuple[str, str]:
    if scenario == "reliable":
        if not is_antonym:
            return "YES", "The statement is consistent with the candidate answer and correctly resolves the question."
        return "NO", "The statement contradicts or negates the candidate answer."
    if scenario == "hallucinated":
        if not is_antonym:
            return "NO", "The statement asserts an unsupported or factually incorrect claim."
        return "YES", "The statement correctly refutes or denies the inaccurate claim."
    if scenario == "uncertain":
        return "NOT SURE", "Insufficient confidence to verify the statement."
    if scenario == "malformed_verifier":
        return "???", "Malformed verifier output."
    if scenario == "mixed":
        v_list = SCENARIO_VERDICTS["mixed"]
        verdict = v_list[index % len(v_list)]
        return verdict, "Deterministic mock rationale."
    # Default fallback to reliable
    if not is_antonym:
        return "YES", "The statement is consistent with the candidate answer."
    return "NO", "The statement contradicts the candidate answer."


def extract_question(user_prompt: str) -> str:
    if "Question:" not in user_prompt:
        return ""
    remainder = user_prompt.split("Question:", 1)[1]
    lines: list[str] = []
    for line in remainder.splitlines():
        stripped = line.strip()
        if stripped in {
            "Base answer:",
            "Candidate answer:",
            "Statement to judge:",
            "Write a concise factual answer.",
        }:
            break
        if stripped:
            lines.append(stripped)
    return " ".join(lines)


def _extract_statement(user_prompt: str) -> str:
    marker = "Statement to judge:"
    if marker not in user_prompt:
        return ""
    remainder = user_prompt.split(marker, 1)[1]
    for line in remainder.splitlines():
        if line.strip():
            return line.strip()
    return remainder.strip()
