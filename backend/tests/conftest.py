import os

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LLM_MODE"] = "mock"
os.environ["MOCK_SCENARIO"] = "mixed"
os.environ["OPENAI_API_KEY"] = "sk-test"
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:5173")
os.environ.setdefault("GENERATOR_MODEL", "gpt-4o-mini")
os.environ.setdefault("VERIFIER_MODEL", "gpt-4o-mini")
os.environ.setdefault("ALLOWED_MODELS", "gpt-4o-mini,gpt-4o")

from app.config import get_settings

get_settings.cache_clear()
