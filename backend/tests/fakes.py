from app.config import Settings
from app.llm.mock import MockLLMClient


def detector_settings(**overrides: object) -> Settings:
    payload = {
        "environment": "test",
        "llm_mode": "mock",
        "generator_model": "gpt-4o-mini",
        "verifier_model": "gpt-4o-mini",
        "synonym_count": 5,
        "antonym_count": 5,
        "threshold": 0.5,
        "database_url": "sqlite:///:memory:",
    }
    payload.update(overrides)
    return Settings(**payload)


def mock_client(scenario: str = "reliable") -> MockLLMClient:
    return MockLLMClient(scenario=scenario)
