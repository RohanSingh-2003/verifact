"""Tests for strict cloud-API-only LLM architecture and provider clients.

Verifies the 10 requirements:
1. No local Ollama endpoint is used (localhost:11434 rejected).
2. Ollama Cloud uses https://ollama.com/api.
3. Ollama Cloud failure does not trigger local fallback.
4. Cloudflare GLM client works with mocked HTTP.
5. Groq Qwen client works with mocked HTTP.
6. OpenRouter client works with mocked HTTP.
7. Gemini client works with mocked API.
8. Dynamic verifier selection excludes the selected Answer Model.
9. All five providers participate in the common LLM interface.
10. Technical provider failures remain technical failures and are not converted to NOT SURE.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import Settings
from app.llm.base import LLMClient, LLMError
from app.llm.cloudflare import CloudflareClient
from app.llm.gemini import GeminiClient, MockGeminiClient
from app.llm.providers import (
    GroqClient,
    OpenRouterClient,
    ModelClient,
    ModelClientLLMAdapter,
    OllamaCloudClient,
)
from app.llm.registry import (
    MODEL_REGISTRY,
    get_model_client,
    get_verifier_pool,
)
from app.metaqa.scoring import Verdict


# 1. No local Ollama endpoint is used
def test_no_local_ollama_endpoint_used() -> None:
    with pytest.raises(ValueError, match="must NOT connect to localhost"):
        OllamaCloudClient(base_url="http://localhost:11434", api_key="test-key")

    with pytest.raises(ValueError, match="must NOT connect to localhost"):
        OllamaCloudClient(base_url="http://localhost:11434/v1", api_key="test-key")

    with pytest.raises(ValueError, match="must NOT connect to localhost"):
        OllamaCloudClient(base_url="http://127.0.0.1:11434", api_key="test-key")


# 2. Ollama Cloud uses https://ollama.com/api
def test_ollama_cloud_uses_cloud_base_url() -> None:
    client = OllamaCloudClient(api_key="ollama_secret_key")
    assert client.base_url == "https://ollama.com/api"
    assert client.model_name == "gemma4:26b"


# 3. Ollama Cloud failure does not trigger local fallback
@pytest.mark.asyncio
async def test_ollama_cloud_failure_does_not_fall_back() -> None:
    client = OllamaCloudClient(
        base_url="https://ollama.com/api",
        api_key="valid-test-key",
        max_retries=0,
    )

    async def _mock_post(*args, **kwargs):
        return httpx.Response(status_code=500, text="Internal Server Error")

    with patch.object(client._client, "post", side_effect=_mock_post):
        with pytest.raises(LLMError) as exc_info:
            await client.generate_answer("What is gravity?")
        assert "500" in str(exc_info.value)
        # Verify no fallback to localhost was attempted
        assert client.base_url == "https://ollama.com/api"


# 4. Cloudflare GLM client works with mocked HTTP
@pytest.mark.asyncio
async def test_cloudflare_glm_client_mocked_http() -> None:
    client = CloudflareClient(
        account_id="cf-acc-123",
        api_token="cf-token-456",
        model_name="@cf/zai-org/glm-4.7-flash",
        max_retries=0,
    )

    mock_resp_data = {
        "success": True,
        "result": {
            "response": "GLM answer from Cloudflare Workers AI"
        }
    }

    async def _mock_post(url, *args, **kwargs):
        assert "@cf/zai-org/glm-4.7-flash" in url
        auth_hdr = kwargs.get("headers", {}).get("Authorization", "")
        assert "Bearer cf-token-456" == auth_hdr
        return httpx.Response(status_code=200, json=mock_resp_data)

    with patch.object(client._client, "post", side_effect=_mock_post):
        ans = await client.generate_answer("Tell me about photosynthesis.")
        assert ans == "GLM answer from Cloudflare Workers AI"

        json_mock_data = {
            "success": True,
            "result": {
                "response": '{"verdict": "YES", "rationale": "Accurate."}'
            }
        }
        with patch.object(client._client, "post", return_value=httpx.Response(status_code=200, json=json_mock_data)):
            obj = await client.complete_json(
                system_prompt="system",
                user_prompt="user",
            )
            assert obj["verdict"] == "YES"
            assert obj["rationale"] == "Accurate."


# 5. Groq Qwen client works with mocked HTTP
@pytest.mark.asyncio
async def test_groq_qwen_client_mocked_http() -> None:
    client = GroqClient(
        api_key="gsk-test-key",
        model_name="qwen-2.5-32b",
        max_retries=0,
    )
    assert client.base_url == "https://api.groq.com/openai/v1"

    mock_resp = {
        "choices": [
            {
                "message": {
                    "content": "Qwen answer from Groq"
                }
            }
        ]
    }

    async def _mock_post(*args, **kwargs):
        auth_hdr = kwargs.get("headers", {}).get("Authorization", "")
        assert "Bearer gsk-test-key" == auth_hdr
        return httpx.Response(status_code=200, json=mock_resp)

    with patch.object(client._client, "post", side_effect=_mock_post):
        ans = await client.generate_answer("What is the speed of light?")
        assert ans == "Qwen answer from Groq"


# 6. OpenRouter client works with mocked HTTP
@pytest.mark.asyncio
async def test_openrouter_client_mocked_http() -> None:
    client = OpenRouterClient(
        api_key="openrouter-test-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=0,
    )
    assert client.base_url == "https://openrouter.ai/api/v1"

    mock_resp = {
        "choices": [
            {
                "message": {
                    "content": "OpenRouter answer from Liquid AI"
                }
            }
        ]
    }

    async def _mock_post(*args, **kwargs):
        headers = kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer openrouter-test-key"
        assert headers.get("HTTP-Referer") == "https://verifact.local"
        assert headers.get("X-Title") == "VeriFact"
        return httpx.Response(status_code=200, json=mock_resp)

    with patch.object(client._client, "post", side_effect=_mock_post):
        ans = await client.generate_answer("What is quantum computing?")
        assert ans == "OpenRouter answer from Liquid AI"


# 7. Gemini client works with mocked API
@pytest.mark.asyncio
async def test_gemini_client_mocked_api() -> None:
    from app.llm.providers import GeminiClientAdapter

    adapter = GeminiClientAdapter(api_key="AIza-mock-key", model_name="gemini-3.8-flash")
    with patch.object(adapter._inner, "complete_text", new_callable=AsyncMock) as mock_text, \
         patch.object(adapter._inner, "complete_json", new_callable=AsyncMock) as mock_json:
        mock_text.return_value = "Water boils at 100 degrees Celsius."
        mock_json.return_value = {"verdict": "YES", "rationale": "Accurate."}

        ans = await adapter.generate_answer("What is the boiling point of water?")
        assert ans == "Water boils at 100 degrees Celsius."

        json_result = await adapter.complete_json(
            system_prompt="verify",
            user_prompt="claim",
        )
        assert json_result["verdict"] == "YES"


# 8. Dynamic verifier selection excludes the selected Answer Model
def test_dynamic_verifier_selection_excludes_answer_model() -> None:
    settings = Settings(llm_mode="mock")
    all_models = ["gemma", "glm", "qwen", "openrouter", "gemini"]
    for answer_model in all_models:
        pool = get_verifier_pool(answer_model, settings)
        verifier_ids = [v["id"] for v in pool]
        assert answer_model not in verifier_ids
        expected = [m for m in all_models if m != answer_model]
        assert set(verifier_ids) == set(expected)
        assert len(verifier_ids) == 4


# 9. All five providers participate in the common LLM interface
def test_all_five_providers_participate_in_common_interface() -> None:
    settings = Settings(
        llm_mode="mock",
        ollama_api_key="k1",
        cloudflare_api_token="k2",
        cloudflare_account_id="acc2",
        groq_api_key="k3",
        openrouter_api_key="k4",
        gemini_api_key="k5",
    )
    for model_id in MODEL_REGISTRY:
        client = get_model_client(model_id, settings)
        assert isinstance(client, ModelClient)
        adapter = ModelClientLLMAdapter(client)
        assert isinstance(adapter, LLMClient)
        assert hasattr(adapter, "complete_text")
        assert hasattr(adapter, "complete_json")
        assert hasattr(adapter, "aclose")


# 10. Technical provider failures remain technical failures and are not converted to NOT SURE
def test_technical_failure_handling_does_not_convert_to_not_sure() -> None:
    from app.metaqa.scoring import Verdict

    # Verify Verdict enum contains exactly YES, NO, NOT SURE
    assert set(v.value for v in Verdict) == {"YES", "NO", "NOT SURE"}

    # An LLMError or Exception during verifier execution raises an error or records failure,
    # never returns a Verdict.NOT_SURE
    class BrokenModelClient(ModelClient):
        async def generate_answer(self, question: str, **kwargs) -> str:
            raise LLMError("API connection reset")

        async def complete_text(self, **kwargs) -> str:
            raise LLMError("Provider timeout")

        async def complete_json(self, **kwargs):
            raise LLMError("Provider 500 error")

    broken = BrokenModelClient()
    adapter = ModelClientLLMAdapter(broken)

    # Calling complete_json must raise LLMError, never return {"verdict": "NOT SURE"}
    with pytest.raises(LLMError) as exc_info:
        import asyncio
        asyncio.run(adapter.complete_json(model="test", system_prompt="", user_prompt=""))
    assert "Provider 500 error" in str(exc_info.value)
