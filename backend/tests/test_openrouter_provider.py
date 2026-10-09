from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.config import Settings
from app.llm.base import LLMError, LLMRateLimitError
from app.llm.providers import GroqClient, OpenRouterClient
from app.llm.registry import MODEL_REGISTRY, get_model_client, get_verifier_pool
from app.metaqa.mutation import GeneratedMutation
from app.metaqa.scoring import MutationType, Verdict
from app.metaqa.multi_verifier import (
    evaluate_mutation_for_model,
    verify_mutation_across_models,
)
from app.services.independent_verifiers import evaluate_single_verifier


# 1. Successful OpenRouter verification
@pytest.mark.asyncio
async def test_openrouter_successful_verification() -> None:
    client = OpenRouterClient(
        api_key="sk-or-v1-mock-test-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        base_url="https://openrouter.ai/api/v1",
        max_retries=1,
    )
    assert client.base_url == "https://openrouter.ai/api/v1"
    assert client.model_name == "liquid/lfm-2.5-2.6b:free"

    mock_resp = {
        "choices": [
            {
                "message": {
                    "content": '{"verdict": "YES", "rationale": "Directly supported by facts."}'
                }
            }
        ]
    }

    async def mock_post(*args, **kwargs):
        headers = kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer sk-or-v1-mock-test-key"
        assert headers.get("HTTP-Referer") == "https://verifact.local"
        assert headers.get("X-Title") == "VeriFact"
        return httpx.Response(status_code=200, json=mock_resp)

    with patch.object(client._client, "post", side_effect=mock_post):
        result = await client.complete_json(
            system_prompt="verify",
            user_prompt="Evaluate claim.",
        )

    assert result["verdict"] == "YES"
    assert "Directly supported" in result["rationale"]
    await client.aclose()


# 2. Correct parsing of YES, NO, and NOT SURE
@pytest.mark.asyncio
@pytest.mark.parametrize("verdict_str", ["YES", "NO", "NOT SURE"])
async def test_openrouter_verdict_parsing(verdict_str: str) -> None:
    client = OpenRouterClient(
        api_key="mock-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=0,
    )

    async def mock_post(*args, **kwargs):
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": f'{{"verdict": "{verdict_str}", "rationale": "Testing {verdict_str}"}}'
                        }
                    }
                ]
            },
        )

    with patch.object(client._client, "post", side_effect=mock_post):
        res = await client.complete_json(system_prompt="sys", user_prompt="usr")

    assert res["verdict"] == verdict_str
    await client.aclose()


# 3. Missing or malformed model responses
@pytest.mark.asyncio
async def test_openrouter_malformed_json_response() -> None:
    client = OpenRouterClient(
        api_key="mock-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=0,
    )

    async def mock_post(*args, **kwargs):
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "This is plain text, not JSON."
                        }
                    }
                ]
            },
        )

    with patch.object(client._client, "post", side_effect=mock_post):
        with pytest.raises(LLMError) as exc_info:
            await client.complete_json(system_prompt="sys", user_prompt="usr")

    assert "JSON" in str(exc_info.value) or "parse" in str(exc_info.value).lower()
    await client.aclose()


@pytest.mark.asyncio
async def test_openrouter_missing_choices_in_response() -> None:
    client = OpenRouterClient(
        api_key="mock-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=0,
    )

    async def mock_post(*args, **kwargs):
        return httpx.Response(status_code=200, json={"choices": []})

    with patch.object(client._client, "post", side_effect=mock_post):
        with pytest.raises(LLMError) as exc_info:
            await client.complete_json(system_prompt="sys", user_prompt="usr")

    assert "choices" in str(exc_info.value).lower()
    await client.aclose()


# 4. Authentication/configuration errors are NOT retried (401, 402, 403, 404)
@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 402, 403, 404])
async def test_openrouter_does_not_retry_non_transient_errors(status_code: int) -> None:
    client = OpenRouterClient(
        api_key="invalid-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=3,
        initial_retry_wait=0.01,
    )

    attempt_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        return httpx.Response(
            status_code=status_code,
            json={"error": {"message": f"Non-transient error {status_code}"}},
        )

    with patch.object(client._client, "post", side_effect=mock_post):
        with pytest.raises(LLMError) as exc_info:
            await client.complete_json(system_prompt="sys", user_prompt="usr")

    # Must fail immediately on attempt 1 without retries
    assert attempt_count == 1
    assert str(status_code) in str(exc_info.value)
    await client.aclose()


# 5. HTTP 429 and bounded retry behavior
@pytest.mark.asyncio
async def test_openrouter_429_followed_by_success() -> None:
    client = OpenRouterClient(
        api_key="test-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=2,
        initial_retry_wait=0.01,
        max_retry_wait=1.0,
        total_retry_timeout=10.0,
    )

    attempt_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            return httpx.Response(
                status_code=429,
                headers={"retry-after": "0.01"},
                json={"error": {"message": "Rate limit reached"}},
            )
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"verdict": "YES", "rationale": "Factually verified after backoff."}'
                        }
                    }
                ]
            },
        )

    with patch.object(client._client, "post", side_effect=mock_post):
        result = await client.complete_json(system_prompt="verify", user_prompt="statement")

    assert attempt_count == 2
    assert result["verdict"] == "YES"
    assert "Factually verified" in result["rationale"]
    await client.aclose()


@pytest.mark.asyncio
async def test_openrouter_repeated_429_bounded_retries() -> None:
    max_retries = 3
    client = OpenRouterClient(
        api_key="test-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=max_retries,
        initial_retry_wait=0.01,
        max_retry_wait=0.05,
        total_retry_timeout=5.0,
    )

    attempt_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        return httpx.Response(
            status_code=429,
            headers={"retry-after": "0.01"},
            json={"error": {"message": "Rate limit exceeded"}},
        )

    with patch.object(client._client, "post", side_effect=mock_post):
        with pytest.raises(LLMRateLimitError) as exc_info:
            await client.complete_json(system_prompt="verify", user_prompt="statement")

    assert attempt_count == max_retries + 1
    assert "429" in str(exc_info.value)
    assert "Retries exhausted" in str(exc_info.value)
    await client.aclose()


@pytest.mark.asyncio
async def test_openrouter_respects_retry_after_header() -> None:
    client = OpenRouterClient(
        api_key="test-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=2,
        initial_retry_wait=10.0,
        max_retry_wait=30.0,
    )

    attempt_count = 0
    slept_durations: list[float] = []

    async def mock_post(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            return httpx.Response(
                status_code=429,
                headers={"retry-after": "0.05"},
                json={"error": {"message": "Rate limited"}},
            )
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"verdict": "NO", "rationale": "Retry-After respected."}'
                        }
                    }
                ]
            },
        )

    original_sleep = asyncio.sleep

    async def mock_sleep(duration, *args, **kwargs):
        slept_durations.append(duration)
        await original_sleep(0.001)

    with patch.object(client._client, "post", side_effect=mock_post), \
         patch("asyncio.sleep", side_effect=mock_sleep):
        res = await client.complete_json(system_prompt="verify", user_prompt="statement")

    assert attempt_count == 2
    assert len(slept_durations) == 1
    assert 0.04 <= slept_durations[0] <= 0.06
    assert res["verdict"] == "NO"
    await client.aclose()


# 6. Free-model unavailability and rejection of auto-routing
def test_openrouter_rejects_auto_routing() -> None:
    with pytest.raises(ValueError) as exc:
        OpenRouterClient(
            api_key="key",
            model_name="openrouter/auto",
        )
    assert "auto" in str(exc.value).lower()

    with pytest.raises(ValueError):
        OpenRouterClient(
            api_key="key",
            model_name="auto",
        )


# 7. Failed OpenRouter calls excluded from scoring
@pytest.mark.asyncio
async def test_openrouter_failure_excluded_from_scoring() -> None:
    mutation = GeneratedMutation(
        type=MutationType.SYNONYM,
        original_text="The speed of sound in dry air at 20 C is 343 m/s.",
        mutated_text="Sound travels at roughly 343 meters per second in 20 C dry air.",
    )

    settings = Settings(
        llm_mode="live",
        openrouter_api_key="mock-openrouter-key",
        gemini_api_key="mock-gemini-key",
        groq_api_key="mock-groq-key",
        cloudflare_api_token="cf-token",
        cloudflare_account_id="cf-account",
        openrouter_max_retries=1,
    )

    async def fake_evaluate_mutation(model_id: str, **kwargs):
        from app.schemas.detect import ModelVerifierVerdict
        if model_id == "openrouter":
            return ModelVerifierVerdict(
                model_id="openrouter",
                model_name="OpenRouter",
                provider="OpenRouter",
                verdict="FAILED — Rate limit exceeded",
                rationale="",
                error="API Error: OpenRouter rate-limited the request (HTTP 429). Retries exhausted after 2 attempts.",
                status="failed",
                contribution=None,
            )
        return ModelVerifierVerdict(
            model_id=model_id,
            model_name=model_id.upper(),
            provider="Cloud Provider",
            verdict="YES",
            rationale="Accurate statement.",
            error=None,
            status="completed",
            contribution=0.0,
        )

    with patch("app.metaqa.multi_verifier.evaluate_mutation_for_model", side_effect=fake_evaluate_mutation):
        scored = await verify_mutation_across_models(
            mutation=mutation,
            question="What is the speed of sound?",
            answer="Sound travels at 343 m/s.",
            verifier_model_ids=["openrouter", "qwen", "gemini"],
            settings=settings,
        )

    assert scored.unavailable is False
    assert scored.parse_failed is False
    assert scored.verdict == Verdict.YES
    assert scored.contribution == 0.0

    or_record = next(v for v in scored.verdicts if v.model_id == "openrouter")
    assert or_record.verdict == "FAILED — Rate limit exceeded"
    assert or_record.status == "failed"
    assert or_record.contribution is None
    assert "429" in or_record.error


# 8. Other providers continuing when OpenRouter fails
@pytest.mark.asyncio
async def test_other_providers_continue_when_openrouter_fails() -> None:
    openrouter_client = OpenRouterClient(
        api_key="test-or-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=0,
    )
    groq_client = GroqClient(
        api_key="test-groq-key",
        max_retries=0,
    )

    async def mock_or_post(*args, **kwargs):
        await asyncio.sleep(0.01)
        return httpx.Response(status_code=401, json={"error": {"message": "Invalid API key"}})

    async def mock_groq_post(*args, **kwargs):
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": '{"verdict": "YES", "rationale": "Groq succeeds"}'}}]},
        )

    with patch.object(openrouter_client._client, "post", side_effect=mock_or_post), \
         patch.object(groq_client._client, "post", side_effect=mock_groq_post):
        results = await asyncio.gather(
            openrouter_client.complete_json(system_prompt="v", user_prompt="q1"),
            groq_client.complete_json(system_prompt="v", user_prompt="q2"),
            return_exceptions=True,
        )

    assert isinstance(results[0], LLMError)
    assert results[1]["verdict"] == "YES"
    await openrouter_client.aclose()
    await groq_client.aclose()


# 9. OpenRouter verifies the same mutations generated by the selected generator
@pytest.mark.asyncio
async def test_openrouter_verifies_same_generator_mutations() -> None:
    settings = Settings(llm_mode="mock")
    mutation = GeneratedMutation(
        type=MutationType.SYNONYM,
        original_text="The boiling point of water is 100 C.",
        mutated_text="Water reaches its boiling point at 100 C.",
    )

    received_prompts: list[str] = []

    async def mock_evaluate(model_id: str, question: str, answer: str, mutation: GeneratedMutation, **kwargs):
        received_prompts.append(mutation.mutated_text)
        from app.schemas.detect import ModelVerifierVerdict
        return ModelVerifierVerdict(
            model_id=model_id,
            model_name="Model",
            provider="Provider",
            verdict="YES",
            rationale="Matches",
            status="completed",
            contribution=0.0,
        )

    with patch("app.metaqa.multi_verifier.evaluate_mutation_for_model", side_effect=mock_evaluate):
        await verify_mutation_across_models(
            mutation=mutation,
            question="What is boiling point of water?",
            answer="Water boils at 100 C.",
            verifier_model_ids=["openrouter", "gemini"],
            settings=settings,
        )

    assert len(received_prompts) == 2
    assert received_prompts[0] == mutation.mutated_text
    assert received_prompts[1] == mutation.mutated_text


# 10. Selected generator is excluded from the verifier pool
def test_openrouter_excluded_when_selected_as_generator() -> None:
    settings = Settings(llm_mode="mock")
    pool = get_verifier_pool("openrouter", settings)
    verifier_ids = [v["id"] for v in pool]
    assert "openrouter" not in verifier_ids
    assert set(verifier_ids) == {"gemma", "glm", "qwen", "gemini"}


# 11. evaluate_single_verifier produces FAILED — Rate limit exceeded for 429
@pytest.mark.asyncio
async def test_evaluate_single_verifier_openrouter_rate_limit() -> None:
    settings = Settings(
        llm_mode="live",
        openrouter_api_key="mock-key",
        openrouter_max_retries=1,
    )
    client = OpenRouterClient(
        api_key="mock-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=1,
        initial_retry_wait=0.01,
    )

    async def mock_post(*args, **kwargs):
        return httpx.Response(
            status_code=429,
            headers={"retry-after": "0.01"},
            json={"error": {"message": "Rate limit reached"}},
        )

    with patch("app.services.independent_verifiers.get_model_client", return_value=client), \
         patch.object(client._client, "post", side_effect=mock_post):
        verdict = await evaluate_single_verifier(
            "openrouter",
            question="What is gravity?",
            answer="Gravity is an attractive force.",
            settings=settings,
        )

    assert verdict.verdict == "FAILED — Rate limit exceeded"
    assert verdict.status == "failed"
    assert "API Error: OpenRouter rate-limited the request (HTTP 429)" in verdict.error
    assert verdict.verdict != "NOT SURE"
    await client.aclose()


# 12. evaluate_mutation_for_model produces FAILED — Rate limit exceeded for 429
@pytest.mark.asyncio
async def test_evaluate_mutation_openrouter_rate_limit() -> None:
    mutation = GeneratedMutation(
        type=MutationType.SYNONYM,
        original_text="Water boils at 100 C.",
        mutated_text="At 100 C, water boils.",
    )
    settings = Settings(
        llm_mode="live",
        openrouter_api_key="mock-key",
        openrouter_max_retries=0,
    )
    client = OpenRouterClient(
        api_key="mock-key",
        model_name="liquid/lfm-2.5-2.6b:free",
        max_retries=0,
    )

    async def mock_post(*args, **kwargs):
        return httpx.Response(
            status_code=429,
            headers={"retry-after": "0.01"},
            json={"error": {"message": "Rate limit reached"}},
        )

    with patch("app.metaqa.multi_verifier.get_model_client", return_value=client), \
         patch.object(client._client, "post", side_effect=mock_post):
        verdict = await evaluate_mutation_for_model(
            "openrouter",
            question="What is the boiling point of water?",
            answer="Water boils at 100 C.",
            mutation=mutation,
            settings=settings,
        )

    assert verdict.verdict == "FAILED — Rate limit exceeded"
    assert verdict.status == "failed"
    assert verdict.contribution is None
    assert "API Error: OpenRouter rate-limited the request (HTTP 429)" in verdict.error
    assert verdict.verdict != "NOT SURE"
    await client.aclose()
