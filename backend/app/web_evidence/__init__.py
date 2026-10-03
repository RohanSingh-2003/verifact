"""Web Evidence Verification — independent of MetaQA mutation testing."""

from app.web_evidence.pipeline import build_web_search_client, run_web_evidence, unavailable_result
from app.web_evidence.types import EvidenceVerdict, WebEvidenceResult, WebEvidenceStatus

__all__ = [
    "EvidenceVerdict",
    "WebEvidenceResult",
    "WebEvidenceStatus",
    "build_web_search_client",
    "run_web_evidence",
    "unavailable_result",
]
