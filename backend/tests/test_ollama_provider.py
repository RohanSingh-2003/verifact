"""Provider selection and Ollama wiring tests. Does not call a live Ollama server."""

from __future__ import annotations

import pytest
from pytest import MonkeyPatch

from app.api.deps import get_llm_client
from app.config import Settings, get_settings
from app.llm.client import OpenAICompatibleClient, parse_json_object
from app.llm.mock import MockLLMClient
from app.llm.ollama import OllamaClient, native_ollama_base_url
from app.metaqa.detector import run_detection
from tests.fakes import detector_settings


@pytest.fixture(autouse=True)
def clear_llm_caches() -> None:
    get_llm_client.cache_clear()
    get_settings.cache_clear()
    yield
    get_llm_client.cache_clear()
    get_settings.cache_clear()


def test_mock_mode_selects_mock_client(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    get_settings.cache_clear()
    get_llm_client.cache_clear()
    client = get_llm_client()
    assert isinstance(client, MockLLMClient)


def test_ollama_provider_selects_ollama_client(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("GENERATOR_MODEL", "gemma4:26b")
    monkeypatch.setenv("VERIFIER_MODEL", "gemma4:26b")
    monkeypatch.setenv("OLLAMA_ALLOWED_MODELS", "gemma4:26b")
    get_settings.cache_clear()
    get_llm_client.cache_clear()
    client = get_llm_client()
    assert isinstance(client, OllamaClient)
    assert native_ollama_base_url(client._settings) == "http://localhost:11434"


def test_openai_compatible_provider_still_selected(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-live")
    monkeypatch.setenv("GENERATOR_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("ALLOWED_MODELS", "gpt-4o-mini,gpt-4o")
    get_settings.cache_clear()
    get_llm_client.cache_clear()
    client = get_llm_client()
    assert isinstance(client, OpenAICompatibleClient)
    assert client._settings.is_ollama is False


def test_ollama_allowlist_accepts_gemma_not_openai_ids() -> None:
    settings = Settings(
        llm_mode="live",
        llm_provider="ollama",
        generator_model="gemma4:26b",
        verifier_model="gemma4:26b",
        ollama_allowed_models="gemma4:26b",
        allowed_models="gpt-4o-mini,gpt-4o",
    )
    assert settings.require_model("gemma4:26b") == "gemma4:26b"
    with pytest.raises(ValueError, match="OLLAMA_ALLOWED_MODELS"):
        settings.require_model("gpt-4o-mini")


def test_openai_allowlist_unchanged() -> None:
    settings = Settings(
        llm_mode="live",
        llm_provider="openai_compatible",
        openai_api_key="sk-test",
        allowed_models="gpt-4o-mini,gpt-4o",
    )
    assert settings.require_model("gpt-4o-mini") == "gpt-4o-mini"
    with pytest.raises(ValueError, match="ALLOWED_MODELS"):
        settings.require_model("gemma4:26b")


def test_ollama_live_ready_without_openai_key() -> None:
    settings = Settings(
        llm_mode="live",
        llm_provider="ollama",
        openai_api_key="replace-with-your-key",
        generator_model="gemma4:26b",
        verifier_model="gemma4:26b",
    )
    assert settings.api_key_configured is True
    assert settings.live_ready is True
    assert settings.effective_api_key == "ollama"


@pytest.mark.asyncio
async def test_generator_and_verifier_model_names_passed() -> None:
    class RecordingClient(MockLLMClient):
        def __init__(self) -> None:
            super().__init__(scenario="reliable")
            self.text_models: list[str] = []
            self.json_models: list[str] = []

        async def complete_text(self, *, model: str, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
            self.text_models.append(model)
            return await super().complete_text(
                model=model, system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens
            )

        async def complete_json(self, *, model: str, system_prompt: str, user_prompt: str, max_tokens: int | None = None):
            self.json_models.append(model)
            return await super().complete_json(
                model=model, system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens
            )

    client = RecordingClient()
    settings = detector_settings(
        llm_mode="mock",
        generator_model="gemma4:26b",
        verifier_model="gemma4:26b",
    )
    result = await run_detection(client, question="What is the capital of India?", settings=settings)
    assert result.generator_model == "gemma4:26b"
    assert result.verifier_model == "gemma4:26b"
    assert client.text_models == ["gemma4:26b"]
    assert all(model == "gemma4:26b" for model in client.json_models)
    assert not result.base_answer.text.startswith("[MOCK]")


@pytest.mark.asyncio
async def test_live_ollama_connection_failure_is_clear(monkeypatch: MonkeyPatch) -> None:
    settings = Settings(
        llm_mode="live",
        llm_provider="ollama",
        ollama_base_url="http://127.0.0.1:9/v1",
        generator_model="gemma4:26b",
        verifier_model="gemma4:26b",
        ollama_allowed_models="gemma4:26b",
        llm_timeout_seconds=5,
        llm_max_retries=0,
    )
    client = OllamaClient(settings)
    from app.llm.base import LLMError

    with pytest.raises(LLMError):
        await client.complete_text(
            model="gemma4:26b",
            system_prompt="Answer briefly.",
            user_prompt="Question:\nping\n\nWrite a concise factual answer.",
        )


def test_parse_json_object_still_strict() -> None:
    assert parse_json_object('{"verdict":"YES","rationale":"ok"}')["verdict"] == "YES"
    assert parse_json_object("not json") is None
