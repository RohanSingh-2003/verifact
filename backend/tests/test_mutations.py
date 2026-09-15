import pytest

from app.llm.base import LLMError
from app.llm.mock import MockLLMClient
from app.metaqa.mutation import (
    GeneratedMutation,
    collect_valid_mutations,
    generate_mutations,
    hash_mutation_set,
    validate_mutation_counts,
)
from app.metaqa.scoring import MutationType


def _item(kind: MutationType, index: int) -> GeneratedMutation:
    return GeneratedMutation(
        type=kind,
        original_text=f"original {index}",
        mutated_text=f"mutated {index}",
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


def test_collect_valid_mutations_rejects_malformed_and_duplicates() -> None:
    raw = [
        {"type": "synonym", "original_text": "A", "mutated_text": "A1"},
        {"type": "synonym", "original_text": "A", "mutated_text": "A1"},
        {"type": "paraphrase", "original_text": "A", "mutated_text": "bad type"},
        {"type": "synonym", "original_text": "A", "mutated_text": "   "},
        {"type": "antonym", "original_text": "A", "mutated_text": "B1"},
        "not-an-object",
        {"type": "antonym", "original_text": "A", "mutated_text": "B2"},
    ]
    valid = collect_valid_mutations(raw)
    assert [item.mutated_text for item in valid] == ["A1", "B1", "B2"]


def test_collect_valid_mutations_rejects_noop_copies() -> None:
    raw = [
        {"type": "synonym", "original_text": "Paris is the capital.", "mutated_text": "Paris is the capital."},
        {"type": "synonym", "original_text": "Paris is the capital.", "mutated_text": "The capital is Paris."},
        {"type": "antonym", "original_text": "Paris is the capital.", "mutated_text": "London is the capital."},
    ]
    valid = collect_valid_mutations(raw)
    assert [item.mutated_text for item in valid] == ["The capital is Paris.", "London is the capital."]


def test_collect_valid_mutations_rejects_non_list() -> None:
    with pytest.raises(ValueError):
        collect_valid_mutations({"type": "synonym"})


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


async def test_generate_mutations_fails_when_too_few_unique_items() -> None:
    llm = MockLLMClient(
        mutations=[
            {"type": "synonym", "original_text": "A", "mutated_text": "only one synonym"},
            {"type": "antonym", "original_text": "A", "mutated_text": "only one antonym"},
        ]
    )
    with pytest.raises(LLMError):
        await generate_mutations(
            llm,
            model="mock",
            question="What is the capital of Australia?",
            answer="A",
            synonym_count=5,
            antonym_count=5,
        )
