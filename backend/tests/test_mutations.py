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
    assert llm.claim_calls == 0
    assert llm.mutation_calls == 1


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


def test_normalize_mutation_payload_standard_mutations_format() -> None:
    from app.metaqa.mutation import CoreClaim, normalize_mutation_payload

    claims = [CoreClaim(id="c1", text="Paris is the capital of France.")]
    payload = {
        "mutations": [
            {
                "type": "synonym",
                "original_text": "Paris is the capital of France.",
                "mutated_text": "The capital city of France is Paris.",
            },
            {
                "type": "antonym",
                "original_text": "Paris is the capital of France.",
                "mutated_text": "Lyon is the capital of France instead.",
            },
        ]
    }
    valid, canonical = normalize_mutation_payload(payload, claims=claims)
    assert len(valid) == 2
    assert len(canonical["synonym_mutations"]) == 1
    assert len(canonical["antonym_mutations"]) == 1
    assert canonical["synonym_mutations"][0] == "The capital city of France is Paris."
    assert canonical["antonym_mutations"][0] == "Lyon is the capital of France instead."


def test_normalize_mutation_payload_synonym_and_antonym_arrays() -> None:
    from app.metaqa.mutation import CoreClaim, normalize_mutation_payload

    claims = [CoreClaim(id="c1", text="New Delhi is the capital of India.")]
    payload = {
        "synonym_mutations": [
            "New Delhi is the official capital city of India.",
            "India's recognized seat of government is New Delhi.",
            "The capital city of the Indian nation is New Delhi.",
        ],
        "antonym_mutations": [
            "Mumbai is the capital city of India instead.",
            "New Delhi is not the capital of India.",
            "Kolkata currently serves as the capital of India.",
        ],
    }
    valid, canonical = normalize_mutation_payload(payload, claims=claims)
    assert len(valid) == 6
    assert len(canonical["synonym_mutations"]) == 3
    assert len(canonical["antonym_mutations"]) == 3
    assert all(item.original_text == "New Delhi is the capital of India." for item in valid)


def test_normalize_mutation_payload_with_markdown_fences() -> None:
    from app.metaqa.mutation import CoreClaim, normalize_mutation_payload

    claims = [CoreClaim(id="c1", text="Paris is the capital of France.")]
    fenced = """```json
{
  "synonyms": [
    "The capital city of France is Paris."
  ],
  "antonyms": [
    "Lyon is the capital of France instead."
  ]
}
```"""
    valid, canonical = normalize_mutation_payload(fenced, claims=claims)
    assert len(valid) == 2
    assert canonical["synonym_mutations"] == ["The capital city of France is Paris."]
    assert canonical["antonym_mutations"] == ["Lyon is the capital of France instead."]


def test_normalize_mutation_payload_missing_synonyms() -> None:
    from app.metaqa.mutation import CoreClaim, normalize_mutation_payload

    claims = [CoreClaim(id="c1", text="Paris is the capital of France.")]
    payload = {
        "antonym_mutations": ["Lyon is the capital of France instead."]
    }
    _valid, canonical = normalize_mutation_payload(payload, claims=claims)
    assert len(canonical["synonym_mutations"]) == 0
    assert len(canonical["antonym_mutations"]) == 1


def test_normalize_mutation_payload_missing_antonyms() -> None:
    from app.metaqa.mutation import CoreClaim, normalize_mutation_payload

    claims = [CoreClaim(id="c1", text="Paris is the capital of France.")]
    payload = {
        "synonym_mutations": ["The capital city of France is Paris."]
    }
    _valid, canonical = normalize_mutation_payload(payload, claims=claims)
    assert len(canonical["synonym_mutations"]) == 1
    assert len(canonical["antonym_mutations"]) == 0


def test_normalize_mutation_payload_malformed_json() -> None:
    from app.metaqa.mutation import CoreClaim, normalize_mutation_payload

    claims = [CoreClaim(id="c1", text="Paris is the capital of France.")]
    valid, canonical = normalize_mutation_payload("not valid json at all", claims=claims)
    assert valid == []
    assert canonical["synonym_mutations"] == []
    assert canonical["antonym_mutations"] == []


def test_mutation_count_validation_missing_either_type_raises() -> None:
    synonyms_only = [_item(MutationType.SYNONYM, i) for i in range(3)]
    with pytest.raises(ValueError, match="Expected 3 unique synonym and 3 unique antonym"):
        validate_mutation_counts(synonyms_only, 3, 3)

    antonyms_only = [_item(MutationType.ANTONYM, i) for i in range(3)]
    with pytest.raises(ValueError, match="Expected 3 unique synonym and 3 unique antonym"):
        validate_mutation_counts(antonyms_only, 3, 3)


@pytest.mark.asyncio
async def test_generate_mutations_ollama_failure_raises_llm_error() -> None:
    class FailingOllamaClient(MockLLMClient):
        async def complete_json(self, *, model: str, system_prompt: str, user_prompt: str, max_tokens: int | None = None):
            raise LLMError("Ollama daemon crashed or returned HTTP 500.")

    client = FailingOllamaClient()
    with pytest.raises(LLMError, match="Mutation generator did not return the required mutation set"):
        await generate_mutations(
            client,
            model="gemma4:26b",
            question="What is the capital of India?",
            answer="New Delhi is the capital of India.",
            synonym_count=3,
            antonym_count=3,
        )


@pytest.mark.asyncio
async def test_mutation_generation_followed_by_gemini_verification() -> None:
    from app.llm.gemini import MockGeminiClient
    from app.metaqa.detector import verify_mutations

    ollama_llm = MockLLMClient(scenario="reliable")
    mutations = await generate_mutations(
        ollama_llm,
        model="gemma4:26b",
        question="What is the capital of India?",
        answer=ollama_llm.answer,
        synonym_count=3,
        antonym_count=3,
    )
    assert len(mutations) == 6

    gemini_verifier = MockGeminiClient(scenario="reliable")
    scored = await verify_mutations(
        gemini_verifier,
        verifier_model="gemini-2.5-flash",
        question="What is the capital of India?",
        answer=ollama_llm.answer,
        mutations=mutations,
        concurrency=3,
    )
    assert len(scored) == 6
    assert all(item.verdict.value in {"YES", "NO", "NOT SURE"} for item in scored)


def test_gemini_failure_not_mistaken_for_mutation_generation_failure() -> None:
    from app.schemas.detect import RunStatus
    from app.services.run_service import classify_analysis_failure

    gemini_err = Exception("Gemini verification unavailable. Check GEMINI_API_KEY.")
    status_result, _msg = classify_analysis_failure(gemini_err, stage="verifying_mutations")
    assert status_result == RunStatus.VERIFICATION_FAILED
    assert status_result != RunStatus.MUTATION_GENERATION_FAILED

    gemini_key_err = Exception("GEMINI_API_KEY is not configured.")
    status_early, _msg_early = classify_analysis_failure(gemini_key_err, stage="answer_ready")
    assert status_early == RunStatus.VERIFICATION_FAILED
    assert status_early != RunStatus.MUTATION_GENERATION_FAILED


# ── Requirement 13 Verification Tests ──────────────────────────────────────────


async def test_requirement_13_1_exactly_one_llm_call() -> None:
    """1. Exactly one mutation-generation LLM call."""
    llm = MockLLMClient(scenario="reliable")
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="What is the capital of India?",
        answer="The capital of India is New Delhi. It is the seat of the government.",
        synonym_count=3,
        antonym_count=3,
    )
    assert len(mutations) == 6
    assert llm.mutation_calls == 1
    assert llm.claim_calls == 0


async def test_requirement_13_2_and_3_three_synonyms_and_three_antonyms() -> None:
    """2 & 3. Three synonym mutations and three antonym mutations."""
    llm = MockLLMClient(scenario="reliable")
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="What is the capital of India?",
        answer="The capital of India is New Delhi. It is the seat of the government.",
        synonym_count=3,
        antonym_count=3,
    )
    synonyms = [m for m in mutations if m.type is MutationType.SYNONYM]
    antonyms = [m for m in mutations if m.type is MutationType.ANTONYM]
    assert len(synonyms) == 3
    assert len(antonyms) == 3


def test_requirement_13_4_think_false_configured() -> None:
    """4. think=false for Ollama Cloud client."""
    from app.llm.providers import OllamaCloudClient
    import inspect
    source = inspect.getsource(OllamaCloudClient._chat)
    assert '"think": False' in source


def test_requirement_13_5_mutation_token_limit_applied() -> None:
    """5. Mutation max token limit is correctly applied."""
    from app.config import get_settings
    settings = get_settings()
    assert settings.llm_mutation_max_tokens == 300


def test_requirement_13_6_ollama_cloud_gemma() -> None:
    """6. Gemma 4:26B is registered with Ollama Cloud provider."""
    from app.llm.registry import MODEL_REGISTRY
    assert "gemma" in MODEL_REGISTRY
    assert MODEL_REGISTRY["gemma"].provider_display == "Ollama Cloud"
    assert MODEL_REGISTRY["gemma"].default_model_name == "gemma4:26b"


def test_requirement_13_7_answer_generation_uses_cloud_registry() -> None:
    """7. Default answer model is Gemma 4:26B from the cloud registry."""
    from app.llm.registry import DEFAULT_MODEL_ID, MODEL_REGISTRY
    assert DEFAULT_MODEL_ID == "gemma"
    assert MODEL_REGISTRY[DEFAULT_MODEL_ID].display_name == "Gemma 4:26B"


async def test_requirement_13_8_gemini_verification_unchanged() -> None:
    """8. Gemini verification remains unchanged."""
    from app.llm.gemini import MockGeminiClient
    from app.metaqa.detector import verify_mutations
    gemini = MockGeminiClient(scenario="reliable")
    llm = MockLLMClient(scenario="reliable")
    mutations = await generate_mutations(
        llm,
        model="mock",
        question="What is the capital of India?",
        answer="The capital of India is New Delhi.",
        synonym_count=3,
        antonym_count=3,
    )
    scored = await verify_mutations(
        gemini,
        verifier_model="gemini-3.8-flash",
        question="What is the capital of India?",
        answer="The capital of India is New Delhi.",
        mutations=mutations,
        concurrency=3,
    )
    assert len(scored) == 6
    assert all(item.verdict is not None for item in scored)


def test_requirement_13_9_metaqa_scoring_unchanged() -> None:
    """9. MetaQA scoring remains unchanged."""
    from app.metaqa.scoring import contribution_score, Verdict, MutationType
    # Synonym YES=0, NO=1, NOT_SURE=0.5
    assert contribution_score(MutationType.SYNONYM, Verdict.YES) == 0.0
    assert contribution_score(MutationType.SYNONYM, Verdict.NO) == 1.0
    assert contribution_score(MutationType.SYNONYM, Verdict.NOT_SURE) == 0.5

    # Antonym YES=1, NO=0, NOT_SURE=0.5
    assert contribution_score(MutationType.ANTONYM, Verdict.YES) == 1.0
    assert contribution_score(MutationType.ANTONYM, Verdict.NO) == 0.0
    assert contribution_score(MutationType.ANTONYM, Verdict.NOT_SURE) == 0.5


def test_requirement_13_10_web_evidence_unchanged() -> None:
    """10. Web Evidence remains unchanged."""
    from app.config import get_settings
    settings = get_settings()
    assert settings.web_evidence_enabled is True
    assert settings.tavily_search_depth == "basic"



