from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.config import Settings
from app.llm.base import LLMClient, LLMModelNotFoundError, LLMUnavailableError
from app.llm.providers import MockModelClient, ModelClient, ModelClientLLMAdapter
from app.llm.registry import (
    DEFAULT_MODEL_ID,
    MODEL_REGISTRY,
    get_model_client,
    get_verifier_pool,
    resolve_model_id,
)
from app.services.independent_verifiers import evaluate_all_independent_verifiers, evaluate_single_verifier


class SpyModelClient(ModelClient):
    """Spy ModelClient that tracks all calls and parameters."""

    def __init__(self, model_id: str, display_name: str, model_name: str) -> None:
        self.model_id = model_id
        self.display_name = display_name
        self.model_name = model_name
        self.text_calls: list[dict] = []
        self.json_calls: list[dict] = []
        self.answer_calls: list[dict] = []
        self.closed = False

    async def generate_answer(self, question: str, *, max_tokens: int | None = None, temperature: float = 0.0) -> str:
        self.answer_calls.append({"question": question, "max_tokens": max_tokens, "temperature": temperature})
        return f"Answer from {self.display_name}"

    async def complete_text(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int | None = None, temperature: float = 0.0
    ) -> str:
        self.text_calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, "max_tokens": max_tokens})
        return f"Text from {self.display_name}"

    async def complete_json(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int | None = None, temperature: float = 0.0
    ) -> dict:
        self.json_calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, "max_tokens": max_tokens})
        return {
            "verdict": "Correct",
            "reasoning": f"Reviewed by {self.display_name}",
            "rationale": f"Reviewed by {self.display_name}",
            "contradictory_claims": [],
            "confidence": 0.95,
            "model_id": self.model_id,
        }

    async def aclose(self) -> None:
        self.closed = True


# ── 1. Canonical Model Registry & Alias Resolution ────────────────────────────

def test_all_five_models_registered_with_correct_providers() -> None:
    """Ensure all five required models exist in MODEL_REGISTRY with intended providers."""
    expected = {
        "gemma": ("Ollama Cloud", "gemma4:26b"),
        "glm": ("Cloudflare Workers AI", "@cf/zai-org/glm-4.7-flash"),
        "qwen": ("Alibaba / Groq", "qwen/qwen3.8-27b"),
        "openrouter": ("Liquid (Liquid AI)", "liquid/lfm-2.5-2.6b:free"),
        "phi": ("Microsoft", "microsoft/phi-4"),
    }
    for mid, (expected_provider, expected_model) in expected.items():
        assert mid in MODEL_REGISTRY, f"Missing model {mid} in registry"
        mdef = MODEL_REGISTRY[mid]
        assert mdef.provider_display == expected_provider
        assert mdef.default_model_name == expected_model


def test_alias_resolution_for_all_five_models() -> None:
    """Verify resolve_model_id resolves canonical IDs, full model names, and provider hints."""
    cases = [
        ("gemma", "gemma"),
        ("gemma4:26b", "gemma"),
        ("Gemma 4:26B", "gemma"),
        ("glm", "glm"),
        ("@cf/zai-org/glm-4.7-flash", "glm"),
        ("GLM-4.7-Flash", "glm"),
        ("qwen", "qwen"),
        ("qwen/qwen3.8-27b", "qwen"),
        ("groq", "qwen"),
        ("openrouter", "openrouter"),
        ("liquid/lfm-2.5-2.6b:free", "openrouter"),
        ("liquid", "openrouter"),
        ("phi", "phi"),
        ("microsoft/phi-4", "phi"),
        ("Phi-4 Reasoning", "phi"),
    ]
    for identifier, expected_id in cases:
        resolved = resolve_model_id(identifier)
        assert resolved == expected_id, f"Failed resolving '{identifier}': expected '{expected_id}', got '{resolved}'"


# ── 2. ModelClientLLMAdapter Routing Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_adapter_complete_text_routes_to_correct_provider() -> None:
    """complete_text() must dispatch strictly to the requested provider and model."""
    spies = {
        mid: SpyModelClient(mid, mdef.display_name, mdef.default_model_name)
        for mid, mdef in MODEL_REGISTRY.items()
    }
    adapter = ModelClientLLMAdapter(spies["gemma"], clients=spies)

    for mid, spy in spies.items():
        resp = await adapter.complete_text(
            model=mid,
            system_prompt="sys",
            user_prompt="user",
        )
        assert resp == f"Text from {spy.display_name}"
        assert len(spy.text_calls) == 1
        # Ensure no other spy was called
        for other_id, other_spy in spies.items():
            if other_id != mid:
                assert len(other_spy.text_calls) == 0, f"Model {other_id} was incorrectly called when requesting {mid}"
        spy.text_calls.clear()


@pytest.mark.asyncio
async def test_adapter_complete_json_routes_to_correct_provider() -> None:
    """complete_json() must dispatch strictly to the requested provider and model."""
    spies = {
        mid: SpyModelClient(mid, mdef.display_name, mdef.default_model_name)
        for mid, mdef in MODEL_REGISTRY.items()
    }
    adapter = ModelClientLLMAdapter(spies["gemma"], clients=spies)

    for mid, spy in spies.items():
        payload = await adapter.complete_json(
            model=mid,
            system_prompt="sys",
            user_prompt="user",
        )
        assert payload["model_id"] == mid
        assert payload["verdict"] == "Correct"
        assert len(spy.json_calls) == 1
        for other_id, other_spy in spies.items():
            if other_id != mid:
                assert len(other_spy.json_calls) == 0, f"Model {other_id} was incorrectly called when requesting {mid}"
        spy.json_calls.clear()


@pytest.mark.asyncio
async def test_adapter_routes_full_model_identifiers() -> None:
    """Full provider model strings (e.g. '@cf/zai-org/glm-4.7-flash') route to correct client."""
    spies = {
        mid: SpyModelClient(mid, mdef.display_name, mdef.default_model_name)
        for mid, mdef in MODEL_REGISTRY.items()
    }
    adapter = ModelClientLLMAdapter(spies["gemma"], clients=spies)

    test_queries = [
        ("@cf/zai-org/glm-4.7-flash", "glm"),
        ("qwen/qwen3.8-27b", "qwen"),
        ("liquid/lfm-2.5-2.6b:free", "openrouter"),
        ("microsoft/phi-4", "phi"),
        ("gemma4:26b", "gemma"),
    ]
    for model_str, expected_id in test_queries:
        payload = await adapter.complete_json(
            model=model_str,
            system_prompt="sys",
            user_prompt="user",
        )
        assert payload["model_id"] == expected_id
        assert len(spies[expected_id].json_calls) >= 1
        spies[expected_id].json_calls.clear()


# ── 3. Error Handling & Prevention of Silent Gemma Fallback ───────────────────

@pytest.mark.asyncio
async def test_adapter_raises_for_unknown_model_no_gemma_fallback() -> None:
    """Requesting an unregistered model must raise LLMModelNotFoundError, never fallback to Gemma."""
    gemma_spy = SpyModelClient("gemma", "Gemma 4:26B", "gemma4:26b")
    adapter = ModelClientLLMAdapter(gemma_spy)

    with pytest.raises(LLMModelNotFoundError) as exc_info:
        await adapter.complete_text(
            model="unsupported-claude-or-gpt",
            system_prompt="sys",
            user_prompt="user",
        )
    assert "not registered" in str(exc_info.value).lower()
    # Verify Gemma was NEVER called as a fallback
    assert len(gemma_spy.text_calls) == 0


@pytest.mark.asyncio
async def test_adapter_raises_for_unconfigured_live_provider_no_fallback() -> None:
    """If a provider's API key is missing in live mode, raise LLMUnavailableError, never fallback."""
    settings = Settings(
        llm_mode="live",
        ollama_api_key="valid-ollama-key",
        # Explicitly empty / unconfigured keys for other providers:
        cloudflare_api_token="",
        cloudflare_account_id="",
        groq_api_key="",
        openrouter_api_key="",
    )
    gemma_spy = SpyModelClient("gemma", "Gemma 4:26B", "gemma4:26b")
    adapter = ModelClientLLMAdapter(gemma_spy, settings=settings)

    # Calling unconfigured GLM must raise LLMUnavailableError
    with pytest.raises(LLMUnavailableError) as exc_info:
        await adapter.complete_json(
            model="glm",
            system_prompt="sys",
            user_prompt="user",
        )
    assert "not configured" in str(exc_info.value).lower()
    # Gemma was NEVER called as a fallback
    assert len(gemma_spy.json_calls) == 0


@pytest.mark.asyncio
async def test_provider_technical_failure_is_not_substituted_by_another_model() -> None:
    """If an independent verifier fails, the adapter/caller raises or records failure; never substitutes Gemma."""
    class FailingProvider(ModelClient):
        async def generate_answer(self, question: str, **kwargs) -> str:
            raise RuntimeError("Cloudflare 502 Bad Gateway")

        async def complete_text(self, **kwargs) -> str:
            raise RuntimeError("Cloudflare 502 Bad Gateway")

        async def complete_json(self, **kwargs) -> dict:
            raise RuntimeError("Cloudflare 502 Bad Gateway")

    gemma_spy = SpyModelClient("gemma", "Gemma 4:26B", "gemma4:26b")
    failing_glm = FailingProvider()
    adapter = ModelClientLLMAdapter(
        gemma_spy,
        clients={"gemma": gemma_spy, "glm": failing_glm},
    )

    with pytest.raises(RuntimeError) as exc_info:
        await adapter.complete_json(
            model="glm",
            system_prompt="sys",
            user_prompt="user",
        )
    assert "Cloudflare 502" in str(exc_info.value)
    # Gemma was NEVER substituted
    assert len(gemma_spy.json_calls) == 0


# ── 4. Gemma Preservation & Verifier Pool Integrity ───────────────────────────

def test_gemma_never_in_verifier_pool() -> None:
    """Gemma generates answers and must NEVER be selected as an independent verifier."""
    settings = Settings(
        llm_mode="mock",
        ollama_api_key="k1",
        cloudflare_api_token="k2",
        cloudflare_account_id="acc2",
        groq_api_key="k3",
        openrouter_api_key="k4",
    )
    pool = get_verifier_pool("gemma", settings)
    pool_ids = {v["id"] for v in pool}
    assert "gemma" not in pool_ids
    assert pool_ids == {"glm", "qwen", "openrouter", "phi"}

    # When Gemma generates the answer, it is completely excluded from verifier pool
    from app.api.routes_detect import _new_verifier_for_pool
    # Verify _new_verifier_for_pool never selects Gemma as a fallback verifier
    client, model_name = _new_verifier_for_pool(settings, selected_answer_model="glm")
    assert "gemma" not in model_name.lower()


@pytest.mark.asyncio
async def test_evaluate_all_independent_verifiers_never_includes_gemma() -> None:
    """evaluate_all_independent_verifiers must query only non-Gemma verifier models."""
    settings = Settings(llm_mode="mock")
    mock_llm = MockModelClient("mock", display_name="Mock", provider_display="Mock")
    adapter = ModelClientLLMAdapter(mock_llm, settings=settings)

    verdicts = await evaluate_all_independent_verifiers(
        question="What is the capital of Australia?",
        answer="Canberra is the capital of Australia.",
        selected_answer_model_id="gemma",
        settings=settings,
        test_llm=adapter,
    )
    evaluated_ids = {v.model_id for v in verdicts}
    assert "gemma" not in evaluated_ids
    assert evaluated_ids == {"glm", "qwen", "openrouter", "phi"}
    for v in verdicts:
        assert v.status == "completed"


# ── 5. Resource Cleanup Lifecycle ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_adapter_aclose_closes_all_instantiated_clients() -> None:
    """aclose() closes inner and all dynamically instantiated model clients cleanly."""
    c1 = SpyModelClient("c1", "Client 1", "c1")
    c2 = SpyModelClient("c2", "Client 2", "c2")
    c3 = SpyModelClient("c3", "Client 3", "c3")

    adapter = ModelClientLLMAdapter(c1, clients={"c2": c2, "c3": c3})
    assert not c1.closed and not c2.closed and not c3.closed

    await adapter.aclose()
    assert c1.closed
    assert c2.closed
    assert c3.closed
