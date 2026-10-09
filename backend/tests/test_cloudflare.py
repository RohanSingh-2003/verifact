from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.base import (
    LLMEmptyResponseError,
    LLMError,
    LLMMalformedResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.cloudflare import CloudflareClient
from app.llm.registry import (
    MODEL_REGISTRY,
    get_model_client,
    get_verifier_pool,
    is_model_configured,
    validate_answer_model,
)
from app.main import app
from app.metaqa.detector import score_mutation
from app.metaqa.mutation import GeneratedMutation
from app.metaqa.scoring import MutationType, Verdict
from app.metaqa.verifier import VerifierResult, verify_mutation


# 1. Cloudflare client initialization
def test_cloudflare_client_initialization() -> None:
    client = CloudflareClient(
        api_token="test-token-123",
        account_id="test-account-456",
        model_name="@cf/zai-org/glm-4.7-flash",
        base_url="https://api.cloudflare.com/client/v4",
    )
    assert client.account_id == "test-account-456"
    assert client.model_name == "@cf/zai-org/glm-4.7-flash"
    assert client.provider_name == "Cloudflare Workers AI"
    expected_url = "https://api.cloudflare.com/client/v4/accounts/test-account-456/ai/run/@cf/zai-org/glm-4.7-flash"
    assert client.endpoint_url == expected_url


# 2. Missing Cloudflare API token
@pytest.mark.asyncio
async def test_missing_cloudflare_api_token() -> None:
    client = CloudflareClient(
        api_token="",
        account_id="test-account-456",
    )
    with pytest.raises(LLMError, match="API token is not configured"):
        await client.generate_answer("What is gravity?")

    client_placeholder = CloudflareClient(
        api_token="replace-with-your-token",
        account_id="test-account-456",
    )
    with pytest.raises(LLMError, match="API token is not configured"):
        await client_placeholder.generate_answer("What is gravity?")


# 3. Missing Cloudflare Account ID
@pytest.mark.asyncio
async def test_missing_cloudflare_account_id() -> None:
    client = CloudflareClient(
        api_token="test-token-123",
        account_id="",
    )
    with pytest.raises(LLMError, match="Account ID is not configured"):
        await client.generate_answer("What is gravity?")

    client_placeholder = CloudflareClient(
        api_token="test-token-123",
        account_id="replace-with-your-account-id",
    )
    with pytest.raises(LLMError, match="Account ID is not configured"):
        await client_placeholder.generate_answer("What is gravity?")


# 4. Successful GLM generation using mocked HTTP
@pytest.mark.asyncio
async def test_successful_glm_generation() -> None:
    client = CloudflareClient(
        api_token="test-token-123",
        account_id="test-account-456",
    )

    mock_response = httpx.Response(
        200,
        json={
            "result": {
                "response": "Photosynthesis is the process by which green plants produce energy from sunlight."
            },
            "success": True,
            "errors": [],
            "messages": [],
        },
        request=httpx.Request("POST", client.endpoint_url),
    )

    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        answer = await client.generate_answer("What is photosynthesis?")
        assert "Photosynthesis is the process" in answer
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == client.endpoint_url
        assert kwargs["headers"]["Authorization"] == "Bearer test-token-123"
        assert "What is photosynthesis?" in kwargs["json"]["messages"][1]["content"]


# 5. Cloudflare API error handling
@pytest.mark.asyncio
async def test_cloudflare_api_error_handling() -> None:
    client = CloudflareClient(
        api_token="test-token-123",
        account_id="test-account-456",
        max_retries=0,
    )

    # 5a. HTTP 400 Bad Request
    mock_400 = httpx.Response(
        400,
        text='{"success": false, "errors": [{"message": "Invalid model parameter"}]}',
        request=httpx.Request("POST", client.endpoint_url),
    )
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_400
        with pytest.raises(LLMError, match="HTTP 400"):
            await client.complete_text(system_prompt="sys", user_prompt="usr")

    # 5b. Cloudflare API error payload with 200 OK
    mock_err_payload = httpx.Response(
        200,
        json={"success": False, "errors": [{"message": "Model execution failed"}], "result": None},
        request=httpx.Request("POST", client.endpoint_url),
    )
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_err_payload
        with pytest.raises(LLMError, match="Model execution failed"):
            await client.complete_text(system_prompt="sys", user_prompt="usr")

    # 5c. Rate limiting (429)
    mock_429 = httpx.Response(
        429,
        text="Rate limit exceeded",
        request=httpx.Request("POST", client.endpoint_url),
    )
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_429
        with pytest.raises(LLMRateLimitError):
            await client.complete_text(system_prompt="sys", user_prompt="usr")

    # 5d. Empty completion
    mock_empty = httpx.Response(
        200,
        json={"success": True, "result": {"response": ""}},
        request=httpx.Request("POST", client.endpoint_url),
    )
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_empty
        with pytest.raises(LLMEmptyResponseError):
            await client.complete_text(system_prompt="sys", user_prompt="usr")


# 6. GLM verifier usage
@pytest.mark.asyncio
async def test_glm_verifier_usage() -> None:
    client = CloudflareClient(
        api_token="test-token-123",
        account_id="test-account-456",
    )

    mock_response = httpx.Response(
        200,
        json={
            "result": {
                "response": '{"verdict": "YES", "rationale": "The statement logically agrees with the answer."}'
            },
            "success": True,
        },
        request=httpx.Request("POST", client.endpoint_url),
    )

    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await client.complete_json(
            system_prompt="verifier system prompt",
            user_prompt="verify statement against answer",
        )
        assert result["verdict"] == "YES"
        assert "logically agrees" in result["rationale"]


# 7. Dynamic verifier exclusion when GLM is the selected Answer Model
def test_dynamic_verifier_exclusion_when_glm_selected() -> None:
    settings = Settings(
        llm_mode="mock",
        cloudflare_api_token="token",
        cloudflare_account_id="account",
    )
    verifiers = get_verifier_pool("glm", settings)
    verifier_ids = [v["id"] for v in verifiers]

    # GLM must be excluded from its own verifiers
    assert "glm" not in verifier_ids
    # Gemma, Qwen, OpenRouter, Gemini must be in verifier pool
    assert "gemma" in verifier_ids
    assert "qwen" in verifier_ids
    assert "openrouter" in verifier_ids
    assert "gemini" in verifier_ids
    assert len(verifier_ids) == 4


# 8. GLM being included as a verifier when another model is selected
def test_glm_included_as_verifier_when_another_model_selected() -> None:
    settings = Settings(
        llm_mode="mock",
        cloudflare_api_token="token",
        cloudflare_account_id="account",
    )
    for other_model in ("gemini", "gemma", "qwen", "openrouter"):
        verifiers = get_verifier_pool(other_model, settings)
        verifier_ids = [v["id"] for v in verifiers]
        assert "glm" in verifier_ids, f"GLM was missing from verifiers when {other_model} was selected"
        assert other_model not in verifier_ids


# 9. Technical failures are NOT converted to NOT SURE
def test_glm_technical_failures_are_not_converted_to_not_sure() -> None:
    mutation = GeneratedMutation(
        type=MutationType.SYNONYM,
        original_text="The capital of Australia is Canberra.",
        mutated_text="Canberra is Australia's capital city.",
    )

    # Technical failure representation
    technical_failure = VerifierResult(
        verdict=None,
        rationale="Cloudflare Workers AI request timed out.",
        error="LLMTimeoutError",
        parse_failed=True,
    )

    scored = score_mutation(mutation, technical_failure)

    assert scored.verdict is None
    assert scored.verdict is not Verdict.NOT_SURE
    assert scored.unavailable is True
    assert scored.parse_failed is True
