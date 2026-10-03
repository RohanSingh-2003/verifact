"""Derive run-level overall status from independent MetaQA and Web Evidence branches."""

from __future__ import annotations

from app.schemas.detect import OverallStatus, RunStatus
from app.web_evidence.types import WebEvidenceStatus


def derive_overall_status(
    metaqa_status: RunStatus | str,
    web_status: WebEvidenceStatus | str | None,
    *,
    has_answer: bool,
) -> OverallStatus:
    """Overall status never treats a single verification failure as a total run failure.

    - failed: only when the AI answer itself is missing
    - running: either MetaQA or Web Evidence is still in progress
    - completed: both branches finished successfully (MetaQA completed + Web completed)
    - partial: both terminal, but at least one verification branch failed / unavailable
    """
    if not has_answer:
        return OverallStatus.FAILED

    metaqa = metaqa_status if isinstance(metaqa_status, RunStatus) else RunStatus(str(metaqa_status))
    if web_status is None:
        web = WebEvidenceStatus.PENDING
    elif isinstance(web_status, WebEvidenceStatus):
        web = web_status
    else:
        try:
            web = WebEvidenceStatus(str(web_status))
        except ValueError:
            web = WebEvidenceStatus.PENDING

    metaqa_done = RunStatus.is_terminal(metaqa)
    web_done = WebEvidenceStatus.is_terminal(web)
    if not metaqa_done or not web_done:
        return OverallStatus.RUNNING

    metaqa_ok = metaqa == RunStatus.COMPLETED
    web_ok = web == WebEvidenceStatus.COMPLETED
    if metaqa_ok and web_ok:
        return OverallStatus.COMPLETED
    return OverallStatus.PARTIAL
