from __future__ import annotations

import hashlib
import logging

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.llm.base import LLMClient, LLMError
from app.llm.prompts import MUTATION_SYSTEM, MUTATION_USER
from app.metaqa.scoring import MutationType

logger = logging.getLogger("verifact.metaqa.mutation")


class GeneratedMutation(BaseModel):
    type: MutationType
    original_text: str = Field(min_length=1)
    mutated_text: str = Field(min_length=1)

    @field_validator("original_text", "mutated_text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Mutation text cannot be empty.")
        return cleaned


class MutationBatch(BaseModel):
    mutations: list[GeneratedMutation]


def mutation_key(mutation: GeneratedMutation) -> tuple[str, str]:
    return mutation.type.value, mutation.mutated_text.casefold()


def collect_valid_mutations(raw_items: object) -> list[GeneratedMutation]:
    if not isinstance(raw_items, list):
        raise ValueError("Mutation payload must contain a list named mutations.")

    valid: list[GeneratedMutation] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_items):
        try:
            mutation = GeneratedMutation.model_validate(item)
        except ValidationError:
            logger.warning("Rejected malformed mutation at index %s.", index)
            continue
        key = mutation_key(mutation)
        if key in seen:
            logger.warning("Rejected duplicate mutation: %s", mutation.mutated_text[:160])
            continue
        if mutation.mutated_text.casefold() == mutation.original_text.casefold():
            logger.warning("Rejected no-op mutation (identical original and mutated text).")
            continue
        seen.add(key)
        valid.append(mutation)
    return valid


def hash_mutation_set(mutations: list[GeneratedMutation]) -> str:
    payload = "\n".join(f"{item.type.value}\t{item.mutated_text}" for item in mutations)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_mutation_counts(
    mutations: list[GeneratedMutation],
    synonym_count: int,
    antonym_count: int,
) -> list[GeneratedMutation]:
    synonyms = [item for item in mutations if item.type is MutationType.SYNONYM]
    antonyms = [item for item in mutations if item.type is MutationType.ANTONYM]
    if len(synonyms) < synonym_count or len(antonyms) < antonym_count:
        raise ValueError(
            f"Expected {synonym_count} unique synonym and {antonym_count} unique antonym mutations, "
            f"received {len(synonyms)} synonym and {len(antonyms)} antonym."
        )
    return synonyms[:synonym_count] + antonyms[:antonym_count]


async def generate_mutations(
    llm: LLMClient,
    *,
    model: str,
    question: str,
    answer: str,
    synonym_count: int,
    antonym_count: int,
) -> list[GeneratedMutation]:
    user_prompt = MUTATION_USER.format(
        question=question,
        answer=answer,
        synonym_count=synonym_count,
        antonym_count=antonym_count,
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            payload = await llm.complete_json(
                model=model,
                system_prompt=MUTATION_SYSTEM,
                user_prompt=user_prompt,
            )
            valid = collect_valid_mutations(payload.get("mutations") if isinstance(payload, dict) else None)
            selected = validate_mutation_counts(valid, synonym_count, antonym_count)
            logger.info(
                "mutations generated count=%s attempt=%s",
                len(selected),
                attempt + 1,
            )
            return selected
        except (ValidationError, ValueError, LLMError, AttributeError, TypeError) as exc:
            last_error = exc
            logger.warning("Mutation generation attempt %s failed: %s", attempt + 1, exc)
    raise LLMError("Mutation generator did not return the required mutation set.") from last_error
