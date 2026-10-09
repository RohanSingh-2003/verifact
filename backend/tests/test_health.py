from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_mode"] == "mock"
    assert "llm_provider" in body
    assert body["live_ready"] is False
    assert "generator_model" in body
    assert "verifier_model" in body
    assert "web_evidence_ready" in body
    assert "web_evidence_enabled" in body
    assert "providers" in body
    assert "ollama" in body["providers"]
    assert "cloudflare" in body["providers"]
    assert "groq" in body["providers"]
    assert "openrouter" in body["providers"]
    assert "gemini" in body["providers"]
    assert "openai_api_key" not in body
    assert "OLLAMA_API_KEY" not in response.text
    assert "TAVILY_API_KEY" not in response.text
    assert "tavily_api_key" not in body
    assert "gemini_api_key" not in body
    assert "GEMINI_API_KEY" not in response.text
    assert "gemini_verifier_ready" in body
    assert "gemini_verifier_model" in body
