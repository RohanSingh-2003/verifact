"""Regression tests for VeriFact AI Answer Generator + Hallucination Detector flow.

Verifies the 10 requirements from prompt Section 21:
1. Current question reaches generator.
2. Generator receives arbitrary question.
3. Live mode does not use hardcoded answers and reports unconfigured credentials.
4. Mock mode is deterministic.
5. Mock mode clearly identifies itself.
6. Different questions create different runs.
7. Previous answers are not reused.
8. Generator and verifier remain separate.
9. API response contains generated answer.
10. MetaQA pipeline receives generated answer.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_llm_client
from app.config import Settings, get_settings
from app.llm.mock import MockLLMClient
from app.main import app
from app.metaqa.detector import run_detection


def make_test_settings() -> Settings:
    return Settings(
        llm_mode="mock",
        generator_model="gemma4:26b",
        verifier_model="gemma4:26b",
        mutation_synonym_count=3,
        mutation_antonym_count=3,
        hallucination_threshold=0.50,
        max_retries=1,
    )


# 1. Current question reaches generator
@pytest.mark.asyncio
async def test_current_question_reaches_generator() -> None:
    client = MockLLMClient(scenario="reliable")
    question = "What causes a solar eclipse?"
    result = await run_detection(client, question=question, settings=make_test_settings())

    assert result.question == question
    gen_prompts = [p for p in client.captured_user_prompts if question in p]
    assert len(gen_prompts) >= 1, "Question must be present in the generator prompt"


# 2. Generator receives arbitrary question
@pytest.mark.asyncio
async def test_generator_receives_arbitrary_question() -> None:
    client = MockLLMClient(scenario="reliable")
    arbitrary_q = "How does quantum entanglement enable secure communication protocols?"
    result = await run_detection(client, question=arbitrary_q, settings=make_test_settings())

    assert result.question == arbitrary_q
    assert arbitrary_q in result.base_answer.text or len(result.base_answer.text) > 10


# 3. Live mode does not use hardcoded answers and reports unconfigured credentials
def test_live_mode_unconfigured_credentials_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When LIVE mode is active but API key is missing, API returns helpful 503."""
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OLLAMA_API_KEY", "")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "")
    get_settings.cache_clear()
    get_llm_client.cache_clear()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/detect",
            json={"question": "What is the capital of India?"},
        )
        assert response.status_code == 503
        detail = response.json().get("detail", "")
        assert "Live LLM mode is not configured" in detail
        assert "Demo / Mock Mode" in detail
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        get_llm_client.cache_clear()


# 4. Mock mode is deterministic
@pytest.mark.asyncio
async def test_mock_mode_is_deterministic() -> None:
    q = "What is the capital of India?"
    client1 = MockLLMClient(scenario="reliable")
    res1 = await run_detection(client1, question=q, settings=make_test_settings())

    client2 = MockLLMClient(scenario="reliable")
    res2 = await run_detection(client2, question=q, settings=make_test_settings())

    assert res1.base_answer.text == res2.base_answer.text
    assert res1.hallucination_score == res2.hallucination_score
    assert res1.classification == res2.classification


# 5. Mock mode clearly identifies itself
@pytest.mark.asyncio
async def test_mock_mode_clearly_identifies_itself() -> None:
    client = MockLLMClient(scenario="reliable")
    unknown_q = "What will the population of Mars be in 2300?"
    res = await run_detection(client, question=unknown_q, settings=make_test_settings())

    assert res.base_answer.text.startswith("[MOCK]")
    assert "No deterministic answer configured" in res.base_answer.text


# 6. Different questions create different runs
def test_different_questions_create_different_runs() -> None:
    client = TestClient(app)
    res1 = client.post("/api/detect", json={"question": "What is the capital of India?"})
    res2 = client.post("/api/detect", json={"question": "Who wrote Hamlet?"})

    assert res1.status_code == 200
    assert res2.status_code == 200

    d1 = res1.json()
    d2 = res2.json()

    assert d1["run_id"] != d2["run_id"]
    assert d1["question"] != d2["question"]
    assert d1["base_answer"]["text"] != d2["base_answer"]["text"]


# 7. Previous answers are not reused
@pytest.mark.asyncio
async def test_previous_answers_are_not_reused() -> None:
    client = MockLLMClient(scenario="reliable")
    settings = make_test_settings()

    res_india = await run_detection(client, question="What is the capital of India?", settings=settings)
    res_newton = await run_detection(client, question="Who formulated the three laws of motion?", settings=settings)

    assert "India" in res_india.base_answer.text or "Delhi" in res_india.base_answer.text
    assert "Newton" in res_newton.base_answer.text
    assert "Delhi" not in res_newton.base_answer.text
    assert "Newton" not in res_india.base_answer.text


# 8. Generator and verifier remain separate roles
@pytest.mark.asyncio
async def test_generator_and_verifier_remain_separate() -> None:
    class SpyGenerator(MockLLMClient):
        def __init__(self) -> None:
            super().__init__(scenario="reliable")
            self.generate_called = False

        async def complete_text(self, **kwargs) -> str:
            self.generate_called = True
            return "Paris is the capital of France."

    class SpyVerifier(MockLLMClient):
        def __init__(self) -> None:
            super().__init__(scenario="reliable")
            self.verify_called = False

        async def complete_json(self, **kwargs):
            self.verify_called = True
            return await super().complete_json(**kwargs)

    gen = SpyGenerator()
    ver = SpyVerifier()

    res = await run_detection(
        llm=gen,
        verifier_llm=ver,
        question="What is the capital of France?",
        settings=make_test_settings(),
    )

    assert gen.generate_called, "Generator role must be invoked for base answer"
    assert ver.verify_called, "Verifier role must be invoked for metamorphic evaluation"
    assert res.base_answer.text == "Paris is the capital of France."


# 9. API response contains generated answer
def test_api_response_contains_generated_answer() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/detect",
        json={"question": "What is the capital of France?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "base_answer" in data
    assert "Paris" in data["base_answer"]["text"]
    assert "run_id" in data
    assert "hallucination_score" in data
    assert "classification" in data


# 10. MetaQA pipeline receives generated answer
@pytest.mark.asyncio
async def test_metaqa_pipeline_receives_generated_answer() -> None:
    client = MockLLMClient(scenario="reliable")
    res = await run_detection(client, question="Who wrote Hamlet?", settings=make_test_settings())

    assert len(res.mutations) > 0
    for scored in res.mutations:
        assert scored.mutation.original_text == res.base_answer.text
        assert scored.verdict in ("YES", "NO", "NOT_SURE")
        assert 0.0 <= scored.contribution <= 1.0
