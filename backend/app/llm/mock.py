from __future__ import annotations

import re
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


# ── Dynamic claim + mutation generation ────────────────────────────────

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_SYNONYM_TEMPLATES: list[str] = [
    "In other words, it is accurate that {claim}.",
    "To put it differently, the claim holds that {claim}.",
    "Stated another way, {claim}.",
    "That is to say, {claim}.",
    "Put simply, it means that {claim}.",
]

_ANTONYM_TEMPLATES: list[str] = [
    "It is not the case that {claim}.",
    "Contrary to that claim, {claim} is incorrect.",
    "The opposite is true: {claim} is wrong.",
    "This is false: {claim}.",
    "Actually, {claim} is a misconception.",
]


def _split_claim_sentences(answer: str, max_claims: int = 4) -> list[str]:
    cleaned = " ".join(answer.split()).strip()
    if not cleaned:
        return []
    parts = _SENTENCE_SPLIT_RE.split(cleaned)
    claims: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = part.strip()
        if not text:
            continue
        if text[-1] not in ".!?":
            text = f"{text}."
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        claims.append(text)
        if len(claims) >= max_claims:
            break
    if not claims and cleaned:
        short = cleaned if cleaned[-1] in ".!?" else f"{cleaned}."
        claims.append(short)
    return claims


def _claims_payload(answer: str, max_claims: int = 4) -> list[dict[str, str]]:
    return [
        {"id": f"claim_{index}", "text": text}
        for index, text in enumerate(_split_claim_sentences(answer, max_claims=max_claims), start=1)
    ]


def _generate_dynamic_mutations(
    claims: list[str],
    synonym_count: int,
    antonym_count: int,
    *,
    synonym_offset: int = 0,
    antonym_offset: int = 0,
) -> list[dict[str, str]]:
    """Generate deterministic mutations distributed across core claims."""
    if not claims:
        claims = [ORIGINAL]
    mutations: list[dict[str, str]] = []
    for i in range(synonym_count):
        claim = claims[(i + synonym_offset) % len(claims)]
        claim_clean = claim.rstrip(".")
        template = _SYNONYM_TEMPLATES[(i + synonym_offset) % len(_SYNONYM_TEMPLATES)]
        mutations.append({
            "type": MutationType.SYNONYM.value,
            "original_text": claim,
            "mutated_text": template.format(claim=claim_clean),
        })
    for i in range(antonym_count):
        claim = claims[(i + antonym_offset) % len(claims)]
        claim_clean = claim.rstrip(".")
        template = _ANTONYM_TEMPLATES[(i + antonym_offset) % len(_ANTONYM_TEMPLATES)]
        mutations.append({
            "type": MutationType.ANTONYM.value,
            "original_text": claim,
            "mutated_text": template.format(claim=claim_clean),
        })
    return mutations


def _extract_answer_from_claim_prompt(user_prompt: str) -> str:
    marker = "Answer:"
    if marker not in user_prompt:
        return ""
    remainder = user_prompt.split(marker, 1)[1]
    lines: list[str] = []
    for line in remainder.splitlines():
        stripped = line.strip()
        if stripped.casefold().startswith("extract "):
            break
        if stripped:
            lines.append(stripped)
    return " ".join(lines)


def _extract_claims_from_mutation_prompt(user_prompt: str) -> list[str]:
    marker = "Core claims"
    if marker not in user_prompt:
        return []
    remainder = user_prompt.split(marker, 1)[1]
    lines = remainder.splitlines()
    claims: list[str] = []
    for line in lines:
        stripped = line.strip()
        lower = stripped.casefold()
        if lower.startswith("create exactly") or lower.startswith("generate only"):
            break
        if lower.startswith("already accepted"):
            break
        if not stripped:
            # Blank line after the claim list ends the block (before rules / accepted section).
            if claims:
                break
            continue
        # Numbered list: "1. claim text"
        if stripped[0].isdigit() and "." in stripped[:4]:
            claims.append(stripped.split(".", 1)[1].strip())
        elif stripped.startswith("-"):
            claims.append(stripped.lstrip("- ").strip())
    return [item for item in claims if item]


_MUTATION_COUNT_RE = re.compile(
    r"Create exactly\s+(\d+)\s+synonym mutations and\s+(\d+)\s+antonym mutations",
    re.IGNORECASE,
)
_FILL_SYN_RE = re.compile(r"exactly\s+(\d+)\s+synonym mutation", re.IGNORECASE)
_FILL_ANT_RE = re.compile(r"exactly\s+(\d+)\s+antonym mutation", re.IGNORECASE)
_MAX_CLAIMS_RE = re.compile(r"Extract\s+(\d+)\s+important factual claims", re.IGNORECASE)


def _extract_mutation_counts(user_prompt: str) -> tuple[int, int]:
    match = _MUTATION_COUNT_RE.search(user_prompt)
    if match:
        return int(match.group(1)), int(match.group(2))
    syn_match = _FILL_SYN_RE.search(user_prompt)
    ant_match = _FILL_ANT_RE.search(user_prompt)
    if syn_match or ant_match:
        syn_n = int(syn_match.group(1)) if syn_match else 0
        ant_n = int(ant_match.group(1)) if ant_match else 0
        return syn_n, ant_n
    return 5, 5


def _extract_max_claims(user_prompt: str) -> int:
    match = _MAX_CLAIMS_RE.search(user_prompt)
    if not match:
        return 4
    return int(match.group(1))


def _is_claim_extraction_prompt(system_prompt: str, user_prompt: str) -> bool:
    if "extract a small set of important factual claims" in system_prompt.casefold():
        return True
    return "extract " in user_prompt.casefold() and "important factual claims" in user_prompt.casefold()


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
        incomplete_first_mutation_batch: bool = False,
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
        self.incomplete_first_mutation_batch = incomplete_first_mutation_batch
        self.answers_by_question = dict(answers_by_question or {})
        self.scenarios_by_question = dict(scenarios_by_question or {})
        self.answers_by_model = {key: dict(value) for key, value in (answers_by_model or {}).items()}
        self.verdicts_by_model = {key: list(value) for key, value in (verdicts_by_model or {}).items()}
        self.mutations_by_model = {key: list(value) for key, value in (mutations_by_model or {}).items()}
        self._verify_index = 0
        self._current_question = ""
        self._last_claims: list[str] = []
        self.answer_calls = 0
        self.claim_calls = 0
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

    async def complete_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> str:
        del max_tokens  # Mock responses are deterministic; token caps are ignored.
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
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        del max_tokens
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

        if _is_claim_extraction_prompt(system_prompt, user_prompt):
            self.claim_calls += 1
            if self.fail_on == "claims":
                raise LLMError("mock claim extraction failure")
            answer_text = _extract_answer_from_claim_prompt(user_prompt) or self.answer
            max_claims = _extract_max_claims(user_prompt)
            # Prefer unique original_text values from fixture mutations so later
            # mutation payloads remain valid against the allowed-claim set.
            fixture_mutations: list[dict[str, str]] | None = None
            if model in self.mutations_by_model:
                fixture_mutations = self.mutations_by_model[model]
            elif self._explicit_mutations:
                fixture_mutations = self.mutations
            if fixture_mutations is not None:
                seen: set[str] = set()
                claims: list[dict[str, str]] = []
                for item in fixture_mutations:
                    text = (item.get("original_text") or "").strip()
                    if not text or text.casefold() in seen:
                        continue
                    seen.add(text.casefold())
                    claims.append({"id": f"claim_{len(claims) + 1}", "text": text})
                    if len(claims) >= max_claims:
                        break
                if claims:
                    self._last_claims = [item["text"] for item in claims]
                    return {"claims": claims}
            claims = _claims_payload(answer_text, max_claims=max_claims)
            self._last_claims = [item["text"] for item in claims]
            return {"claims": claims}

        if self.fail_on == "mutations":
            raise LLMError("mock mutation failure")
        self.mutation_calls += 1

        # If explicit mutations were provided (tests) or model-specific mutations
        # exist, use them. Otherwise generate dynamic mutations from core claims.
        if model in self.mutations_by_model:
            payload: list[dict[str, Any]] = list(self.mutations_by_model[model])
        elif self._explicit_mutations:
            payload = list(self.mutations)
        else:
            claims = _extract_claims_from_mutation_prompt(user_prompt) or self._last_claims
            syn_n, ant_n = _extract_mutation_counts(user_prompt)
            syn_offset = 0
            ant_offset = 0
            # Simulate an incomplete first batch so fill rounds can complete the set.
            if self.incomplete_first_mutation_batch:
                if self.mutation_calls == 1:
                    self.mutations = []
                    if ant_n > 0:
                        ant_n = max(0, ant_n - 1)
                else:
                    syn_offset = sum(
                        1 for item in self.mutations if item.get("type") == MutationType.SYNONYM.value
                    )
                    ant_offset = sum(
                        1 for item in self.mutations if item.get("type") == MutationType.ANTONYM.value
                    )
            if claims:
                payload = _generate_dynamic_mutations(
                    claims,
                    syn_n,
                    ant_n,
                    synonym_offset=syn_offset,
                    antonym_offset=ant_offset,
                )
                # Update self.mutations so _mutation_index works during verification
                if self.incomplete_first_mutation_batch:
                    combined = list(self.mutations) + payload
                    seen_texts: set[str] = set()
                    deduped: list[dict[str, str]] = []
                    for item in combined:
                        text = item.get("mutated_text", "")
                        if text in seen_texts:
                            continue
                        seen_texts.add(text)
                        deduped.append(item)
                    self.mutations = deduped
                else:
                    self.mutations = payload
            else:
                payload = list(self.mutations)

        if self.include_malformed_items and self.mutation_calls == 1:
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
    stop_prefixes = (
        "base answer:",
        "candidate answer:",
        "statement to judge:",
        "core claims",
        "answer:",
        "write a concise factual answer.",
        "answer the question directly",
        "create exactly",
        "extract ",
    )
    lines: list[str] = []
    for line in remainder.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                # Blank line after the question body ends the question block.
                break
            continue
        if stripped.casefold().startswith(stop_prefixes):
            break
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
