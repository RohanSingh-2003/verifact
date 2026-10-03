"""Web search providers (Tavily) used by Web Evidence Verification."""

from app.web_search.base import WebSearchClient, WebSource
from app.web_search.mock import MockTavilyClient
from app.web_search.tavily_client import TavilyClient

__all__ = [
    "MockTavilyClient",
    "TavilyClient",
    "WebSearchClient",
    "WebSource",
]
