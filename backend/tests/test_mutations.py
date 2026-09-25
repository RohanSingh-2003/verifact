import pytest

from app.llm.base import LLMError
from app.llm.mock import MockLLMClient
from app.metaqa.mutation import (
    GeneratedMutation,
    collect_valid_mutations,
    extract_core_claims,
    fallback_claims_from_answer,
    generate_mutations,
    hash_mutation_set,
    looks_like_complete_sentence,
    validate_mutation_counts,
    word_count,
)
from app.metaqa.scoring import MutationType

VICTUS_ANSWER = (
    "Some users have reported hinge durability issues and structural fragility "
    "with certain HP Victus laptop models."
)

LONG_DELHI_ANSWER = (
    "New Delhi is the capital of India. The British government announced the "
    "transfer of the capital from Calcutta to Delhi in 1911. The new city was "
    "designed by Edwin Lutyens and Herbert Baker. The planned city included wide "
    "avenues and major government buildings."
)


def _item(kind: MutationType, index: int) -> GeneratedMutation:
    return GeneratedMutation(
        type=kind,
        original_text=f"The original claim number {index} is stated here.",
        mutated_text=f"The mutated claim number {index} is stated clearly.",
    )


def test_mutation_count_validation_accepts_exact_counts() -> None:
    mutations = [_item(MutationType.SYNONYM, i) for i in range(5)] + [
        _item(MutationType.ANTONYM, i) for i in range(5)
    ]
    result = validate_mutation_counts(mutations, 5, 5)
    assert len(result) == 10


def test_mutation_count_validation_trims_extras() -> None:
    mutations = [_item(MutationType.SYNONYM, i) for i in range(7)] + [
        _item(MutationType.ANTONYM, i) for i in range(6)
    ]
    result = validate_mutation_counts(mutations, 5, 5)
    assert len([item for item in result if item.type is MutationType.SYNONYM]) == 5
    assert len([item for item in result if item.type is MutationType.ANTONYM]) == 5


def test_mutation_count_validation_rejects_short_sets() -> None:
    mutations = [_item(MutationType.SYNONYM, i) for i in range(4)] + [
        _item(MutationType.ANTONYM, i) for i in range(5)
    ]
    with pytest.raises(ValueError):
        validate_mutation_counts(mutations, 5, 5)


def test_looks_like_complete_sentence_rejects_fragments() -> None:
    assert looks_like_complete_sentence("structural stability") is False
    assert looks_like_complete_sentence("Strong construction.") is False
    assert looks_like_complete_sentence("hinge problems") is False
    assert looks_like_complete_sentence("New Delhi") is False
    assert looks_like_complete_sentence("Synonym mutation: users reported issues") is False
    assert looks_like_complete_sentence("Is this a question about hinges?") is False
    assert looks_like_complete_sentence("What is the capital of India?") is False


def test_looks_like_complete_sentence_accepts_full_claims() -> None:
    assert looks_like_complete_sentence(
        "Some users have reported hinge durability problems and structural weakness "
        "in certain HP Victus laptop models."
    )
    assert looks_like_complete_sentence(
        "Certain HP Victus laptop models have strong structural stability and durable "
        "hinges, without the reported hinge problems."
    )
    assert looks_like_complete_sentence("New Delhi is the capital of India.")
    assert looks_like_complete_sentence("New Delhi is not the capital of India.")


def test_collect_valid_mutations_rejects_fragments_and_duplicates() -> None:
    raw = [
        {
            "type": "synonym",
            "original_text": VICTUS_ANSWER,
            "mutated_text": (
                "Some users have reported hinge durability problems and structural "
                "weakness in certain HP Victus laptop models."
            ),
        },
        {
            "type": "synonym",
            "original_text": VICTUS_ANSWER,
            "mutated_text": (
                "Some users have reported hinge durability problems and structural "
                "weakness in certain HP Victus laptop models."
            ),
        },
        {"type": "antonym", "original_text": VICTUS_ANSWER, "mutated_text": "structural stability"},
        {"type": "antonym", "original_text": VICTUS_ANSWER, "mutated_text": "Strong construction."},
        {"type": "paraphrase", "original_text": VICTUS_ANSWER, "mutated_text": "bad type sentence is here now."},
        {"type": "synonym", "original_text": VICTUS_ANSWER, "mutated_text": "   "},
        {
            "type": "antonym",
            "original_text": VICTUS_ANSWER,
            "mutated_text": (
                "Certain HP Victus laptop models have strong structural stability and "
                "durable hinges, without the reported hinge problems."
            ),
        },
        "not-an-object",
        {
            "type": "antonym",
            "original_text": VICTUS_ANSWER,
            "mutated_text": (
                "HP Victus models that users discuss do not suffer from hinge durability "
                "issues or structural fragility."
            ),
        },
    ]
    valid = collect_valid_mutations(raw)
    assert [item.type for item in valid] == [MutationType.SYNONYM, MutationType.ANTONYM, MutationType.ANTONYM]
    assert all(looks_like_complete_sentence(item.mutated_text) for item in valid)
    assert "structural stability" not in {item.mutated_text for item in valid}


def test_collect_valid_mutations_rejects_noop_copies() -> None:
    raw = [
        {"type": "synonym", "original_text": "Paris is the capital.", "mutated_text": "Paris is the capital."},
        {
            "type": "synonym",
            "original_text": "Paris is the capital.",
            "mutated_text": "The capital city of France is Paris.",
        },
        {
            "type": "antonym",
            "original_text": "Paris is the capital.",
            "mutated_text": "London is the capital of France instead.",
        },
    ]
    valid = collect_valid_mutations(raw)
    assert [item.mutated_text for item in valid] == [
        "The capital city of France is Paris.",
        "London is the capital of France instead.",
    ]


def test_collect_valid_mutations_rejects_non_list() -> None:
    with pytest.raises(ValueError):
        collect_valid_mutations({"type": "synonym"})


def test_looks_like_complete_sentence_rejects_overlong_mutations() -> None:
    long = " ".join(["word"] * 40) + " is stated clearly here."
    assert looks_like_complete_sentence(long) is False


def test_fallback_claims_from_long_answer() -> None:
    claims = fallback_claims_from_answer(LONG_DELHI_ANSWER, max_claims=4)
    assert 3 <= len(claims) <= 4
    assert claims[0].text.startswith("New Delhi")
    assert all(looks_like_complete_sentence(c.text, min_words=4, max_words=40) for c in claims)


async def test_extract_core_claims_returns_short_claims() -> None:
    llm = MockLLMClient(scenario="reliable")
    claims = await extract_core_claims(
        llm,
        model="mock",
        question="What is the capital of India?",
        answer=LONG_DELHI_ANSWER,
        max_claims=4,
    )
    assert 1 <= len(claims) <= 4
    assert all(word_count(c.text) <= 40 for c in claims)
    assert llm.claim_calls >= 1


async def test_generate_mutations_uses_claims_not_full_long_answer() -> None:
    llm = MockLLMClient(scenario="reliable")
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="What is the capital of India?",
        answer=LONG_DELHI_ANSWER,
        synonym_count=3,
        antonym_count=3,
    )
    assert len(mutations) == 6
    assert all(looks_like_complete_sentence(item.mutated_text) for item in mutations)
    assert all(word_count(item.mutated_text) <= 35 for item in mutations)
    # Mutations must be based on short claims, not the entire multi-sentence answer.
    assert all(item.original_text.casefold() != LONG_DELHI_ANSWER.casefold() for item in mutations)
    assert all(word_count(item.original_text) <= 40 for item in mutations)
    assert llm.claim_calls >= 1
    assert llm.mutation_calls >= 1


async def test_generate_mutations_preserves_qualifiers_in_original_claim() -> None:
    qualified = (
        "Some users have reported hinge problems with certain HP Victus models."
    )
    llm = MockLLMClient(scenario="reliable")
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="Does Victus laptops have hinge problem?",
        answer=qualified,
        synonym_count=3,
        antonym_count=3,
    )
    assert len(mutations) == 6
    assert all("some users" in item.original_text.casefold() or "certain" in item.original_text.casefold() for item in mutations)


async def test_generate_mutations_returns_requested_counts() -> None:
    llm = MockLLMClient(scenario="reliable")
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="What is the capital of Australia?",
        answer=llm.answer,
        synonym_count=5,
        antonym_count=5,
    )
    assert len(mutations) == 10
    assert len([item for item in mutations if item.type is MutationType.SYNONYM]) == 5
    assert len([item for item in mutations if item.type is MutationType.ANTONYM]) == 5
    assert all(looks_like_complete_sentence(item.mutated_text) for item in mutations)


async def test_generate_mutations_detect_counts_remain_three_plus_three() -> None:
    llm = MockLLMClient(scenario="reliable")
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="Does Victus laptops have hinge problem?",
        answer=VICTUS_ANSWER,
        synonym_count=3,
        antonym_count=3,
    )
    assert len(mutations) == 6
    assert len([item for item in mutations if item.type is MutationType.SYNONYM]) == 3
    assert len([item for item in mutations if item.type is MutationType.ANTONYM]) == 3
    assert all(looks_like_complete_sentence(item.mutated_text) for item in mutations)
    assert all("structural stability" != item.mutated_text.casefold() for item in mutations)


async def test_generate_mutations_filters_fragments_then_meets_counts() -> None:
    good_syn = [
        {
            "type": "synonym",
            "original_text": VICTUS_ANSWER,
            "mutated_text": (
                f"Some users have reported hinge durability problems variant {i} "
                "with certain HP Victus laptop models."
            ),
        }
        for i in range(3)
    ]
    good_ant = [
        {
            "type": "antonym",
            "original_text": VICTUS_ANSWER,
            "mutated_text": (
                f"Certain HP Victus laptop models have durable hinges variant {i} "
                "and strong structural stability."
            ),
        }
        for i in range(3)
    ]
    llm = MockLLMClient(
        mutations=[
            {"type": "antonym", "original_text": VICTUS_ANSWER, "mutated_text": "structural stability"},
            {"type": "antonym", "original_text": VICTUS_ANSWER, "mutated_text": "Strong construction."},
            *good_syn,
            *good_ant,
        ]
    )
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="Does Victus laptops have hinge problem?",
        answer=VICTUS_ANSWER,
        synonym_count=3,
        antonym_count=3,
    )
    assert len(mutations) == 6
    assert all(looks_like_complete_sentence(m.mutated_text) for m in mutations)


async def test_generate_mutations_fills_only_missing_items() -> None:
    llm = MockLLMClient(scenario="reliable", incomplete_first_mutation_batch=True)
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="What is the capital of Australia?",
        answer=llm.answer,
        synonym_count=3,
        antonym_count=3,
    )
    assert len(mutations) == 6
    assert len([item for item in mutations if item.type is MutationType.SYNONYM]) == 3
    assert len([item for item in mutations if item.type is MutationType.ANTONYM]) == 3
    # First round incomplete + at least one fill round.
    assert llm.mutation_calls >= 2
    assert all(looks_like_complete_sentence(item.mutated_text) for item in mutations)


async def test_generate_mutations_deduplicates_before_verification() -> None:
    llm = MockLLMClient(scenario="reliable", include_duplicates=True)
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="What is the capital of Australia?",
        answer=llm.answer,
        synonym_count=5,
        antonym_count=5,
    )
    keys = {(item.type, item.mutated_text.casefold()) for item in mutations}
    assert len(keys) == 10


def test_mutation_set_hash_is_stable_for_identical_text() -> None:
    first = [_item(MutationType.SYNONYM, i) for i in range(5)] + [_item(MutationType.ANTONYM, i) for i in range(5)]
    second = [_item(MutationType.SYNONYM, i) for i in range(5)] + [_item(MutationType.ANTONYM, i) for i in range(5)]
    assert hash_mutation_set(first) == hash_mutation_set(second)
    second[-1] = _item(MutationType.ANTONYM, 99)
    assert hash_mutation_set(first) != hash_mutation_set(second)


async def test_generate_mutations_does_not_treat_malformed_items_as_valid() -> None:
    llm = MockLLMClient(scenario="reliable", include_malformed_items=True)
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="What is the capital of Australia?",
        answer=llm.answer,
        synonym_count=5,
        antonym_count=5,
    )
    assert all(item.type in {MutationType.SYNONYM, MutationType.ANTONYM} for item in mutations)
    assert all(item.mutated_text.strip() for item in mutations)
    assert all(looks_like_complete_sentence(item.mutated_text) for item in mutations)


async def test_generate_mutations_fails_when_too_few_unique_items() -> None:
    llm = MockLLMClient(
        mutations=[
            {
                "type": "synonym",
                "original_text": "Paris is the capital of France.",
                "mutated_text": "The capital city of France is Paris.",
            },
            {
                "type": "antonym",
                "original_text": "Paris is the capital of France.",
                "mutated_text": "Paris is not the capital of France.",
            },
        ]
    )
    with pytest.raises(LLMError):
        await generate_mutations(
            llm,
            model="mock",
            question="What is the capital of France?",
            answer="Paris is the capital of France.",
            synonym_count=5,
            antonym_count=5,
        )
