from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_llm_client
from app.config import Settings, get_settings
from app.llm.cloudflare import CloudflareClient
from app.llm.mock import MockLLMClient
from app.llm.providers import (
    GroqClient,
    OpenRouterClient,
    OllamaCloudClient,
)
from app.llm.registry import (
    DEFAULT_MODEL_ID,
    MODEL_REGISTRY,
    get_model_client,
    get_verifier_pool,
    validate_answer_model,
)
from app.main import app


def _client() -> TestClient:
    return TestClient(app)


# 1. Default model = Gemma
def test_default_model_is_gemma() -> None:
    client = _client()
    resp = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_model"] is not None
    assert data["answer_model"]["id"] == "gemma"
    assert data["answer_model"]["name"] == "Gemma 4:26B"
    assert data["answer_model"]["provider"] == "Ollama Cloud"


# 2. Selecting Gemma
def test_selecting_gemma() -> None:
    client = _client()
    resp = client.post("/api/detect", json={"question": "What is photosynthesis?", "answer_model": "gemma"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_model"]["id"] == "gemma"
    assert data["answer_model"]["name"] == "Gemma 4:26B"
    verifier_ids = [v["id"] for v in data["verifiers"]]
    assert "gemma" not in verifier_ids


# 3. Selecting Qwen
def test_selecting_qwen() -> None:
    client = _client()
    resp = client.post("/api/detect", json={"question": "What is gravity?", "answer_model": "qwen"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_model"]["id"] == "qwen"
    assert data["answer_model"]["name"] == "Qwen"
    assert data["answer_model"]["provider"] == "Alibaba / Groq"
    verifier_ids = [v["id"] for v in data["verifiers"]]
    assert "qwen" not in verifier_ids
    assert "gemma" in verifier_ids


# 4. Selecting GLM-4.7-Flash
def test_selecting_glm() -> None:
    client = _client()
    resp = client.post("/api/detect", json={"question": "Explain relativity.", "answer_model": "glm"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_model"]["id"] == "glm"
    assert data["answer_model"]["name"] == "GLM-4.7-Flash"
    assert data["answer_model"]["provider"] == "Cloudflare Workers AI"
    verifier_ids = [v["id"] for v in data["verifiers"]]
    assert "glm" not in verifier_ids
    assert "gemma" in verifier_ids


# 5. Selecting OpenRouter
def test_selecting_openrouter() -> None:
    client = _client()
    resp = client.post("/api/detect", json={"question": "Explain thermodynamics.", "answer_model": "openrouter"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_model"]["id"] == "openrouter"
    assert data["answer_model"]["name"] == "OpenRouter"
    assert data["answer_model"]["provider"] == "OpenRouter"
    verifier_ids = [v["id"] for v in data["verifiers"]]
    assert "openrouter" not in verifier_ids
    assert "gemini" in verifier_ids


# 6. Selecting Gemini
def test_selecting_gemini() -> None:
    client = _client()
    resp = client.post("/api/detect", json={"question": "What is quantum computing?", "answer_model": "gemini"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_model"]["id"] == "gemini"
    assert data["answer_model"]["name"] == "Gemini Flash 3.8"
    assert data["answer_model"]["provider"] == "Google"
    verifier_ids = [v["id"] for v in data["verifiers"]]
    assert "gemini" not in verifier_ids
    assert "gemma" in verifier_ids


# 7. Selected answer model is excluded from verifier pool
@pytest.mark.parametrize("model_id", ["gemini", "gemma", "glm", "qwen", "openrouter"])
def test_selected_answer_model_excluded_from_verifier_pool(model_id: str) -> None:
    client = _client()
    resp = client.post("/api/detect", json={"question": "What is speed of light?", "answer_model": model_id})
    assert resp.status_code == 200
    data = resp.json()
    verifiers = data["verifiers"]
    verifier_ids = [v["id"] for v in verifiers]

    # Selected model MUST be excluded
    assert model_id not in verifier_ids, f"Answer model {model_id} was improperly included in verifier pool"
    # Exactly 4 other models should be present
    assert len(verifiers) == 4
    for other_id in MODEL_REGISTRY:
        if other_id != model_id:
            assert other_id in verifier_ids


# 8. Invalid model ID is rejected
def test_invalid_model_id_is_rejected() -> None:
    client = _client()
    resp = client.post("/api/detect", json={"question": "What is 2+2?", "answer_model": "non_existent_model"})
    assert resp.status_code in {400, 422}


# 9. Missing answer_model falls back to Gemma
def test_missing_or_empty_answer_model_falls_back_to_gemma() -> None:
    client = _client()
    resp1 = client.post("/api/detect", json={"question": "What is oxygen?", "answer_model": ""})
    assert resp1.status_code == 200
    assert resp1.json()["answer_model"]["id"] == "gemma"

    resp2 = client.post("/api/detect", json={"question": "What is hydrogen?"})
    assert resp2.status_code == 200
    assert resp2.json()["answer_model"]["id"] == "gemma"


# 10. Provider failure does not become NOT SURE
def test_provider_failure_does_not_become_not_sure() -> None:
    from app.metaqa.detector import score_mutation
    from app.metaqa.mutation import GeneratedMutation
    from app.metaqa.scoring import MutationType, Verdict
    from app.metaqa.verifier import VerifierResult

    mutation = GeneratedMutation(
        type=MutationType.SYNONYM,
        original_text="The capital of France is Paris.",
        mutated_text="Paris is France's capital city.",
    )

    # Simulated technical error (API timeout / rate limit / 500)
    failed_result = VerifierResult(
        verdict=None,
        rationale="",
        error="LLM provider returned HTTP 500.",
        parse_failed=True,
    )

    scored = score_mutation(mutation, failed_result)

    # Must be marked failed/unavailable, NEVER NOT_SURE
    assert scored.parse_failed is True
    assert scored.unavailable is True
    assert scored.verdict is not Verdict.NOT_SURE
    assert scored.verdict is None


# 11. API keys are never returned in API responses
def test_api_keys_are_never_returned_in_api_responses() -> None:
    client = _client()

    endpoints = [
        client.get("/api/models"),
        client.get("/api/health"),
        client.get("/api/settings"),
        client.post("/api/detect", json={"question": "What is water?", "answer_model": "gemma"}),
    ]

    # Sensitive patterns to check
    sensitive_markers = ["AQ.", "tvly-", "ollama-cloud-secret", "sk-proj-", "cf-token-"]

    for resp in endpoints:
        text = resp.text
        for marker in sensitive_markers:
            assert marker not in text, f"Found sensitive marker {marker!r} in response from {resp.request.url}"
        assert "api_key" not in text.lower() or "configured" in text.lower()


# 12. Ollama Cloud never calls localhost:11434
def test_ollama_cloud_client_rejects_localhost() -> None:
    with pytest.raises(ValueError, match="must NOT connect to localhost"):
        OllamaCloudClient(base_url="http://localhost:11434", api_key="secret")

    with pytest.raises(ValueError, match="must NOT connect to localhost"):
        OllamaCloudClient(base_url="http://127.0.0.1:11434", api_key="secret")

    # Cloud endpoint is valid
    cloud_client = OllamaCloudClient(base_url="https://ollama.com/api", api_key="secret")
    assert cloud_client.base_url == "https://ollama.com/api"


# 13. Available models endpoint
def test_get_models_endpoint() -> None:
    client = _client()
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "default_model" in data
    assert data["default_model"] == "gemma"
    ids = [m["id"] for m in data["models"]]
    assert ids == ["gemma", "glm", "qwen", "openrouter", "gemini"]
    for m in data["models"]:
        assert "api_key" not in m
        assert "name" in m
        assert "provider_display" in m


# 14. Test 1: Selected = Gemma
def test_selected_gemma_generates_and_all_others_verify() -> None:
    client = _client()
    resp = client.post(
        "/api/detect",
        json={"question": "What is the speed of sound in air?", "answer_model": "gemma"},
    )
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    data = client.get(f"/api/runs/{run_id}").json()

    assert data["answer_model"]["id"] == "gemma"
    assert data["answer_model"]["name"] == "Gemma 4:26B"
    assert "gemma" in data["mutation_generator_model"].lower() or "gemma" in data["base_answer"]["model"].lower()

    mutations = data.get("mutations", [])
    assert len(mutations) > 0, "Mutations must be generated"
    for m in mutations:
        verifier_ids = {v["model_id"] for v in m["verdicts"]}
        assert verifier_ids == {"glm", "qwen", "openrouter", "gemini"}
        assert "gemma" not in verifier_ids, "Gemma must NOT verify its own mutations"


# 15. Test 2: Selected = Qwen
def test_selected_qwen_generates_and_all_others_verify() -> None:
    client = _client()
    resp = client.post(
        "/api/detect",
        json={"question": "What is the speed of sound in air?", "answer_model": "qwen"},
    )
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    data = client.get(f"/api/runs/{run_id}").json()

    assert data["answer_model"]["id"] == "qwen"
    assert data["answer_model"]["name"] == "Qwen"

    mutations = data.get("mutations", [])
    assert len(mutations) > 0, "Mutations must be generated"
    for m in mutations:
        verifier_ids = {v["model_id"] for v in m["verdicts"]}
        assert verifier_ids == {"gemma", "glm", "openrouter", "gemini"}
        assert "qwen" not in verifier_ids, "Qwen must NOT verify its own mutations"


# 16. Test 3: Selected = Gemini
def test_selected_gemini_generates_and_all_others_verify() -> None:
    client = _client()
    resp = client.post(
        "/api/detect",
        json={"question": "What is the speed of sound in air?", "answer_model": "gemini"},
    )
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    data = client.get(f"/api/runs/{run_id}").json()

    assert data["answer_model"]["id"] == "gemini"
    assert data["answer_model"]["name"] == "Gemini Flash 3.8"

    mutations = data.get("mutations", [])
    assert len(mutations) > 0, "Mutations must be generated"
    for m in mutations:
        verifier_ids = {v["model_id"] for v in m["verdicts"]}
        assert verifier_ids == {"gemma", "glm", "qwen", "openrouter"}
        assert "gemini" not in verifier_ids, "Gemini must NOT verify its own mutations"


# 17. Test 4: Verifier models never receive mutation-generation instructions
def test_verifier_models_never_receive_mutation_generation_instructions() -> None:
    from app.llm.prompts import VERIFY_SYSTEM, VERIFY_USER

    forbidden_prompts = [
        "generate mutations",
        "generate synonym mutations",
        "generate antonym mutations",
        "generate exactly",
        "create mutations",
        "already accepted mutations",
        "extract factual claims",
    ]

    verifier_prompt = f"{VERIFY_SYSTEM}\n{VERIFY_USER}".lower()
    for phrase in forbidden_prompts:
        assert phrase not in verifier_prompt, (
            f"Verifier prompt improperly contains mutation generation instruction: '{phrase}'"
        )


# 18. Test 5: Verify that each verifier makes an independent API call
@pytest.mark.asyncio
async def test_each_verifier_makes_independent_api_call() -> None:
    from app.metaqa.mutation import GeneratedMutation
    from app.metaqa.scoring import MutationType
    from app.metaqa.multi_verifier import verify_mutation_across_models

    mutation = GeneratedMutation(
        type=MutationType.SYNONYM,
        original_text="Paris is the capital of France.",
        mutated_text="The capital of France is Paris.",
    )

    mock_llm = MockLLMClient()
    settings = get_settings()
    scored = await verify_mutation_across_models(
        mutation=mutation,
        question="What is the capital of France?",
        answer="Paris is the capital of France.",
        verifier_model_ids=["glm", "qwen", "openrouter", "gemini"],
        settings=settings,
        test_llm=mock_llm,
    )

    assert len(scored.verdicts) == 4
    model_ids = [v.model_id for v in scored.verdicts]
    assert model_ids == ["glm", "qwen", "openrouter", "gemini"]
    for v in scored.verdicts:
        assert v.status in {"completed", "failed"}
        assert v.verdict in {"YES", "NO", "NOT SURE", "FAILED"}


# 19. Test 6: Verify that a failed verifier is not converted into NOT SURE
@pytest.mark.asyncio
async def test_failed_verifier_is_not_converted_into_not_sure() -> None:
    from app.metaqa.mutation import GeneratedMutation
    from app.metaqa.scoring import MutationType
    from app.metaqa.multi_verifier import evaluate_mutation_for_model

    mutation = GeneratedMutation(
        type=MutationType.SYNONYM,
        original_text="The Earth revolves around the Sun.",
        mutated_text="The Sun is orbited by the Earth.",
    )

    mock_llm = MockLLMClient(fail_on="verify")
    settings = get_settings()

    result = await evaluate_mutation_for_model(
        "qwen",
        question="Does the Earth revolve around the Sun?",
        answer="Yes, the Earth revolves around the Sun.",
        mutation=mutation,
        settings=settings,
        test_llm=mock_llm,
    )

    assert result.verdict == "FAILED"
    assert result.status == "failed"
    assert result.verdict != "NOT SURE", "Failed verifier call must NEVER be converted to NOT SURE"
    assert result.contribution is None, "Failed verifier must have contribution None (excluded from score)"
    assert result.error is not None


# 20. Test 7: Verify that the expected verdict is NOT included in the verifier prompt
def test_expected_verdict_not_included_in_verifier_prompt() -> None:
    from app.llm.prompts import VERIFY_SYSTEM, VERIFY_USER

    forbidden_leakage = [
        "expected verdict",
        "expected:",
        "expected answer",
        "the correct verdict is",
        "ground truth",
        "synonym mutation",
        "antonym mutation",
        "expected outcome",
    ]

    combined = f"{VERIFY_SYSTEM}\n{VERIFY_USER}".lower()
    for leak in forbidden_leakage:
        assert leak not in combined, (
            f"Verifier prompt improperly reveals expected verdict or test type: '{leak}'"
        )


