import os

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LLM_MODE"] = "mock"
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["MOCK_SCENARIO"] = "mixed"
os.environ["SYNONYM_COUNT"] = "5"
os.environ["ANTONYM_COUNT"] = "5"
os.environ["VERIFY_CONCURRENCY"] = "5"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:5173"
os.environ["GENERATOR_MODEL"] = "gemma4:26b"
os.environ["VERIFIER_MODEL"] = "gemma4:26b"
os.environ["OLLAMA_CLOUD_BASE_URL"] = "https://ollama.com/api"
os.environ["GEMINI_VERIFIER_MODEL"] = "gemini-3.8-flash"
os.environ["GEMINI_API_KEY"] = ""
os.environ["TAVILY_API_KEY"] = ""

import pytest
from app.api.deps import get_llm_client
from app.config import get_settings

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_mock_test_environment():
    os.environ["LLM_MODE"] = "mock"
    get_settings.cache_clear()
    get_llm_client.cache_clear()
    yield
    os.environ["LLM_MODE"] = "mock"
    get_settings.cache_clear()
    get_llm_client.cache_clear()
