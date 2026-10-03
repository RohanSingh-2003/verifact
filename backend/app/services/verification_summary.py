"""Deterministic MetaQA ↔ Web Evidence comparison (no fused score)."""

from __future__ import annotations

from enum import Enum

from app.metaqa.scoring import Classification
from app.schemas.detect import RunStatus
from app.schemas.web_evidence import WebClaimOut, WebEvidenceOut
from app.web_evidence.types import EvidenceVerdict, WebEvidenceStatus


class MetaqaSignal(str, Enum):
    CONSISTENT = "CONSISTENT"
    INCONSISTENT = "INCONSISTENT"
    UNAVAILABLE = "UNAVAILABLE"
    PENDING = "PENDING"


class WebSignal(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT = "INSUFFICIENT"
    UNAVAILABLE = "UNAVAILABLE"
    PENDING = "PENDING"


class SignalRelationship(str, Enum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"
    BOTH_CONCERNING = "BOTH_CONCERNING"
    WEB_INSUFFICIENT = "WEB_INSUFFICIENT"
    METAQA_UNAVAILABLE = "METAQA_UNAVAILABLE"
    WEB_UNAVAILABLE = "WEB_UNAVAILABLE"
    BOTH_UNAVAILABLE = "BOTH_UNAVAILABLE"
    PENDING = "PENDING"


class OverallVerdict(str, Enum):
    LIKELY_RELIABLE = "LIKELY_RELIABLE"
    POTENTIALLY_HALLUCINATED = "POTENTIALLY_HALLUCINATED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNAVAILABLE = "UNAVAILABLE"
    PENDING = "PENDING"


_METAQA_LABELS = {
    MetaqaSignal.CONSISTENT: "Consistent",
    MetaqaSignal.INCONSISTENT: "Inconsistent",
    MetaqaSignal.UNAVAILABLE: "Unavailable",
    MetaqaSignal.PENDING: "Pending",
}

_WEB_LABELS = {
    WebSignal.SUPPORTED: "Supported",
    WebSignal.PARTIALLY_SUPPORTED: "Partially supported",
    WebSignal.CONTRADICTED: "Potential factual contradiction",
    WebSignal.INSUFFICIENT: "Insufficient evidence",
    WebSignal.UNAVAILABLE: "Unavailable",
    WebSignal.PENDING: "Pending",
}

_RELATIONSHIP_LABELS = {
    SignalRelationship.AGREE: "Signals agree",
    SignalRelationship.DISAGREE: "Signals disagree",
    SignalRelationship.BOTH_CONCERNING: "Both signals indicate a potential problem",
    SignalRelationship.WEB_INSUFFICIENT: "External evidence was insufficient",
    SignalRelationship.METAQA_UNAVAILABLE: "MetaQA unavailable — Web Evidence only",
    SignalRelationship.WEB_UNAVAILABLE: "Web Evidence unavailable — MetaQA only",
    SignalRelationship.BOTH_UNAVAILABLE: "Both verification signals unavailable",
    SignalRelationship.PENDING: "Verification still in progress",
}

_OVERALL_LABELS = {
    OverallVerdict.LIKELY_RELIABLE: "Likely Reliable",
    OverallVerdict.POTENTIALLY_HALLUCINATED: "Potentially Hallucinated",
    OverallVerdict.NEEDS_VERIFICATION: "Needs Verification",
    OverallVerdict.INSUFFICIENT_EVIDENCE: "Insufficient Evidence",
    OverallVerdict.UNAVAILABLE: "Unavailable",
    OverallVerdict.PENDING: "Pending",
}

OVERALL_RESEARCH_NOTE = (
    "MetaQA and Web Evidence are independent verification signals. "
    "The combined risk is an application-level fusion used by VeriFact "
    "and is not a metric defined by the MetaQA or ClaimCheck research papers."
)


def metaqa_signal_from_run(
    *,
    status: RunStatus | str,
    classification: Classification | str | None,
    score: float | None,
) -> MetaqaSignal:
    status_raw = status.value if isinstance(status, RunStatus) else str(status or "")
    if RunStatus.is_failure(status_raw):
        return MetaqaSignal.UNAVAILABLE
    if status_raw != RunStatus.COMPLETED.value:
        return MetaqaSignal.PENDING
    if score is None or classification is None:
        return MetaqaSignal.UNAVAILABLE
    class_raw = classification.value if isinstance(classification, Classification) else str(classification)
    if class_raw == Classification.RELIABLE.value:
        return MetaqaSignal.CONSISTENT
    if class_raw == Classification.HALLUCINATED.value:
        return MetaqaSignal.INCONSISTENT
    return MetaqaSignal.UNAVAILABLE


def web_signal_from_evidence(web: WebEvidenceOut | None) -> WebSignal:
    if web is None:
        return WebSignal.PENDING
    status = web.status if isinstance(web.status, WebEvidenceStatus) else WebEvidenceStatus(str(web.status))
    if status in {WebEvidenceStatus.UNAVAILABLE, WebEvidenceStatus.FAILED}:
        return WebSignal.UNAVAILABLE
    if not WebEvidenceStatus.is_terminal(status):
        return WebSignal.PENDING
    contradicted = int(web.contradicted_claims or 0)
    supported = int(web.supported_claims or 0)
    insufficient = int(web.insufficient_claims or 0)
    if contradicted > 0:
        return WebSignal.CONTRADICTED
    if supported > 0 and insufficient > 0:
        return WebSignal.PARTIALLY_SUPPORTED
    if supported > 0:
        return WebSignal.SUPPORTED
    return WebSignal.INSUFFICIENT


def relationship_for(metaqa: MetaqaSignal, web: WebSignal) -> SignalRelationship:
    if metaqa is MetaqaSignal.PENDING or web is WebSignal.PENDING:
        return SignalRelationship.PENDING
    if metaqa is MetaqaSignal.UNAVAILABLE and web is WebSignal.UNAVAILABLE:
        return SignalRelationship.BOTH_UNAVAILABLE
    if metaqa is MetaqaSignal.UNAVAILABLE:
        return SignalRelationship.METAQA_UNAVAILABLE
    if web is WebSignal.UNAVAILABLE:
        return SignalRelationship.WEB_UNAVAILABLE
    if web is WebSignal.INSUFFICIENT:
        return SignalRelationship.WEB_INSUFFICIENT
    # Treat partial support like support for agreement (no contradictions).
    web_ok = web in {WebSignal.SUPPORTED, WebSignal.PARTIALLY_SUPPORTED}
    if metaqa is MetaqaSignal.CONSISTENT and web_ok:
        return SignalRelationship.AGREE
    if metaqa is MetaqaSignal.CONSISTENT and web is WebSignal.CONTRADICTED:
        return SignalRelationship.DISAGREE
    if metaqa is MetaqaSignal.INCONSISTENT and web_ok:
        return SignalRelationship.DISAGREE
    if metaqa is MetaqaSignal.INCONSISTENT and web is WebSignal.CONTRADICTED:
        return SignalRelationship.BOTH_CONCERNING
    return SignalRelationship.PENDING


def metaqa_interpretation(signal: MetaqaSignal, *, score: float | None, threshold: float) -> str:
    if signal is MetaqaSignal.CONSISTENT:
        score_txt = f"{score:.2f}" if score is not None else "n/a"
        return (
            f"MetaQA score {score_txt} is below the threshold ({threshold:.2f}), "
            "indicating mutation-consistency behavior classified as Reliable."
        )
    if signal is MetaqaSignal.INCONSISTENT:
        score_txt = f"{score:.2f}" if score is not None else "n/a"
        return (
            f"MetaQA score {score_txt} is at or above the threshold ({threshold:.2f}), "
            "indicating inconsistent behavior under synonym/antonym mutations."
        )
    if signal is MetaqaSignal.UNAVAILABLE:
        return (
            "MetaQA analysis is unavailable — no MetaQA score was assigned. "
            "This is not the same as a score of 0.00."
        )
    return "MetaQA analysis is still running."


def web_interpretation(signal: WebSignal, web: WebEvidenceOut | None) -> str:
    if signal is WebSignal.SUPPORTED:
        total = int(web.total_claims) if web else 0
        supported = int(web.supported_claims) if web else 0
        return (
            f"Retrieved evidence supported {supported} of {total} checked claim"
            f"{'' if total == 1 else 's'}; no contradicted claims."
        )
    if signal is WebSignal.PARTIALLY_SUPPORTED:
        supported = int(web.supported_claims) if web else 0
        insufficient = int(web.insufficient_claims) if web else 0
        return (
            f"External sources support some checked claims ({supported} supported), "
            f"while {insufficient} claim{'s' if insufficient != 1 else ''} could not be "
            "sufficiently verified. No contradiction was found. "
            "Insufficient evidence is not treated as hallucination."
        )
    if signal is WebSignal.CONTRADICTED:
        n = int(web.contradicted_claims) if web else 0
        return (
            f"Potential factual contradiction detected: {n} claim"
            f"{'s' if n != 1 else ''} conflict with retrieved evidence. "
            "Inspect the contradicted claim(s) and sources below."
        )
    if signal is WebSignal.INSUFFICIENT:
        return (
            "Retrieved sources were not sufficient to verify the claims. "
            "Insufficient evidence is not treated as hallucination."
        )
    if signal is WebSignal.UNAVAILABLE:
        return "Web Evidence could not be completed for this run."
    return "Web Evidence analysis is still running."


def relationship_detail(relationship: SignalRelationship) -> str:
    details = {
        SignalRelationship.AGREE: (
            "MetaQA found consistent mutation behavior, and Web Evidence found supporting sources "
            "for checked claims (or partial support without contradictions). "
            "The methods still measure different things."
        ),
        SignalRelationship.DISAGREE: (
            "MetaQA and Web Evidence point in different directions. Review both panels — "
            "do not collapse this into a single percentage."
        ),
        SignalRelationship.BOTH_CONCERNING: (
            "MetaQA found inconsistent mutation behavior and Web Evidence found contradicted claims. "
            "Treat the answer with caution and inspect the claim-level evidence."
        ),
        SignalRelationship.WEB_INSUFFICIENT: (
            "External evidence was insufficient to verify claims. "
            "Do not interpret this as a hallucination verdict."
        ),
        SignalRelationship.METAQA_UNAVAILABLE: (
            "Only the Web Evidence signal is available for this run. "
            "MetaQA has no score (not 0.00)."
        ),
        SignalRelationship.WEB_UNAVAILABLE: (
            "Only the MetaQA signal is available for this run."
        ),
        SignalRelationship.BOTH_UNAVAILABLE: (
            "Neither MetaQA nor Web Evidence completed successfully. "
            "The generated answer remains available above."
        ),
        SignalRelationship.PENDING: "Waiting for verification signals to finish.",
    }
    return details[relationship]


def attention_claims_from_web(web: WebEvidenceOut | None) -> list[WebClaimOut]:
    """Only contradicted claims require attention for hallucination warnings."""
    if web is None or not web.claims:
        return []
    return [c for c in web.claims if c.verdict is EvidenceVerdict.CONTRADICTED]


def compute_overall_assessment(
    *,
    metaqa_signal: MetaqaSignal,
    metaqa_score: float | None,
    web_signal: WebSignal,
    web_evidence: WebEvidenceOut | None,
) -> tuple[OverallVerdict, str, str, str, float | None, float | None]:
    """Deterministic fusion layer combining MetaQA and Web Evidence.

    Returns:
        (overall_verdict, overall_explanation, metaqa_summary_text, web_summary_text, combined_risk, web_risk)
    """
    web_score = web_evidence.consistency_score if web_evidence else None
    web_risk = round(1.0 - web_score, 4) if web_score is not None else None
    combined_risk: float | None = None
    if metaqa_score is not None and web_risk is not None:
        combined_risk = round(0.5 * metaqa_score + 0.5 * web_risk, 4)

    # 1. Check pending
    if metaqa_signal is MetaqaSignal.PENDING or web_signal is WebSignal.PENDING:
        return (
            OverallVerdict.PENDING,
            "Verification is still in progress.",
            "MetaQA analysis in progress.",
            "Web Evidence analysis in progress.",
            None,
            web_risk,
        )

    # 2. Both unavailable
    if metaqa_signal is MetaqaSignal.UNAVAILABLE and web_signal is WebSignal.UNAVAILABLE:
        return (
            OverallVerdict.UNAVAILABLE,
            "Both MetaQA consistency checking and Web Evidence analysis were unavailable for this run. An overall assessment cannot be determined.",
            "MetaQA analysis unavailable.",
            "Web Evidence analysis unavailable.",
            None,
            None,
        )

    # 3. Web Evidence unavailable, only MetaQA available
    if web_signal is WebSignal.UNAVAILABLE:
        if metaqa_signal is MetaqaSignal.CONSISTENT:
            return (
                OverallVerdict.LIKELY_RELIABLE,
                "MetaQA detected no consistency violations under test mutations. External web evidence was unavailable for this run.",
                "No consistency violations detected.",
                "External evidence unavailable.",
                None,
                None,
            )
        else:
            return (
                OverallVerdict.POTENTIALLY_HALLUCINATED,
                "MetaQA detected consistency violations across test mutations. External web evidence was unavailable to corroborate claims.",
                "Consistency violations detected under test mutations.",
                "External evidence unavailable.",
                None,
                None,
            )

    # 4. MetaQA unavailable, only Web Evidence available
    if metaqa_signal is MetaqaSignal.UNAVAILABLE:
        contradicted = int(web_evidence.contradicted_claims) if web_evidence else 0
        supported = int(web_evidence.supported_claims) if web_evidence else 0
        insufficient = int(web_evidence.insufficient_claims) if web_evidence else 0

        if contradicted > 0:
            return (
                OverallVerdict.POTENTIALLY_HALLUCINATED,
                f"External evidence contradicts {contradicted} checked claim{'s' if contradicted > 1 else ''}. MetaQA consistency checking was unavailable.",
                "MetaQA analysis unavailable.",
                f"External evidence contradicts {contradicted} checked claim{'s' if contradicted > 1 else ''}.",
                None,
                web_risk,
            )
        elif supported > 0 and insufficient == 0:
            return (
                OverallVerdict.LIKELY_RELIABLE,
                "Available web evidence supports all checked claims. MetaQA consistency checking was unavailable.",
                "MetaQA analysis unavailable.",
                "All checked claims were supported by available evidence.",
                None,
                web_risk,
            )
        elif supported > 0:
            return (
                OverallVerdict.NEEDS_VERIFICATION,
                "Web evidence supports some claims, but some could not be verified. MetaQA consistency checking was unavailable.",
                "MetaQA analysis unavailable.",
                "Some checked claims were supported, while others were insufficient.",
                None,
                web_risk,
            )
        else:
            return (
                OverallVerdict.NEEDS_VERIFICATION,
                "External evidence was insufficient to verify the claims, and MetaQA was unavailable.",
                "MetaQA analysis unavailable.",
                "Available web evidence was insufficient to verify claims.",
                None,
                web_risk,
            )

    # 5. BOTH signals are available!
    contradicted = int(web_evidence.contradicted_claims) if web_evidence else 0
    supported = int(web_evidence.supported_claims) if web_evidence else 0
    insufficient = int(web_evidence.insufficient_claims) if web_evidence else 0
    total = int(web_evidence.total_claims) if web_evidence else 0

    # Case 1 & Case 5: Contradictions in Web Evidence
    if contradicted > 0:
        if metaqa_signal is MetaqaSignal.INCONSISTENT:
            # Case 1: MetaQA indicates hallucination AND Web Evidence contains contradictions
            return (
                OverallVerdict.POTENTIALLY_HALLUCINATED,
                "Both consistency checking and external evidence indicate problems with the answer.",
                "Consistency violations detected under test mutations.",
                f"External evidence contradicts {contradicted} checked claim{'s' if contradicted > 1 else ''}.",
                combined_risk,
                web_risk,
            )
        else:
            # Case 5: Web Evidence contains contradictions even if MetaQA is reliable
            return (
                OverallVerdict.POTENTIALLY_HALLUCINATED,
                "External evidence contradicts one or more claims even though MetaQA did not detect consistency violations.",
                "No consistency violations detected.",
                f"External evidence contradicts {contradicted} checked claim{'s' if contradicted > 1 else ''}.",
                combined_risk,
                web_risk,
            )

    # When contradicted == 0:
    if metaqa_signal is MetaqaSignal.INCONSISTENT:
        # Case 2: MetaQA indicates hallucination BUT Web Evidence mostly/partially supports the claims
        if supported > 0:
            return (
                OverallVerdict.NEEDS_VERIFICATION,
                "Web evidence supports the checked claims, but MetaQA detected consistency violations.",
                "Consistency violations detected under test mutations.",
                "Available web evidence supports checked claims without contradictions.",
                combined_risk,
                web_risk,
            )
        else:
            # MetaQA inconsistent and Web Evidence is insufficient
            return (
                OverallVerdict.POTENTIALLY_HALLUCINATED,
                "MetaQA detected consistency violations, and external web evidence was insufficient to verify claims.",
                "Consistency violations detected under test mutations.",
                "Available web evidence was insufficient to verify claims.",
                combined_risk,
                web_risk,
            )

    # When metaqa_signal is MetaqaSignal.CONSISTENT (and contradicted == 0):
    if supported > 0 and insufficient == 0:
        # Case 3: MetaQA is reliable AND Web Evidence supports all checked claims
        return (
            OverallVerdict.LIKELY_RELIABLE,
            "MetaQA found no consistency violations and the available web evidence supports all checked claims.",
            "No consistency violations detected.",
            "All checked claims were supported by available evidence.",
            combined_risk,
            web_risk,
        )
    elif supported > 0 and insufficient > 0:
        # Example 7: MetaQA consistent, partial/mostly supported claims without contradictions
        if supported >= insufficient:
            return (
                OverallVerdict.LIKELY_RELIABLE,
                "MetaQA detected no consistency violations, while web evidence supported most checked claims.",
                "No consistency violations detected.",
                "Most checked claims were supported, while some could not be verified.",
                combined_risk,
                web_risk,
            )
        else:
            # Case 4: substantial insufficient evidence
            return (
                OverallVerdict.NEEDS_VERIFICATION,
                "MetaQA found no consistency violations, but available web evidence was insufficient to verify some claims.",
                "No consistency violations detected.",
                f"Evidence was insufficient for {insufficient} of {total} checked claims.",
                combined_risk,
                web_risk,
            )
    else:
        # Case 4: No claims supported, all insufficient
        return (
            OverallVerdict.NEEDS_VERIFICATION,
            "MetaQA found no consistency violations, but available web evidence was insufficient to verify claims.",
            "No consistency violations detected.",
            "Available web evidence was insufficient to verify claims.",
            combined_risk,
            web_risk,
        )


def build_verification_summary(
    *,
    status: RunStatus | str,
    classification: Classification | str | None,
    score: float | None,
    threshold: float,
    web_evidence: WebEvidenceOut | None,
) -> dict:
    """Pure function returning a JSON-serializable verification summary dict."""
    metaqa = metaqa_signal_from_run(status=status, classification=classification, score=score)
    web = web_signal_from_evidence(web_evidence)
    relationship = relationship_for(metaqa, web)
    attention = attention_claims_from_web(web_evidence)

    ready = relationship is not SignalRelationship.PENDING

    class_raw = None
    if classification is not None:
        class_raw = classification.value if isinstance(classification, Classification) else str(classification)

    (
        overall_verdict,
        overall_explanation,
        metaqa_summary_text,
        web_summary_text,
        combined_risk,
        web_risk,
    ) = compute_overall_assessment(
        metaqa_signal=metaqa,
        metaqa_score=score,
        web_signal=web,
        web_evidence=web_evidence,
    )

    return {
        "ready": ready,
        "metaqa_signal": metaqa.value,
        "metaqa_label": _METAQA_LABELS[metaqa],
        "metaqa_score": score,
        "metaqa_classification": class_raw,
        "metaqa_interpretation": metaqa_interpretation(metaqa, score=score, threshold=threshold),
        "web_signal": web.value,
        "web_label": _WEB_LABELS[web],
        "web_interpretation": web_interpretation(web, web_evidence),
        "web_total_claims": int(web_evidence.total_claims) if web_evidence else 0,
        "web_supported": int(web_evidence.supported_claims) if web_evidence else 0,
        "web_contradicted": int(web_evidence.contradicted_claims) if web_evidence else 0,
        "web_insufficient": int(web_evidence.insufficient_claims) if web_evidence else 0,
        "web_consistency_score": web_evidence.consistency_score if web_evidence else None,
        "web_consistency_verdict": web_evidence.consistency_verdict if web_evidence else None,
        "web_consistency_verdict_label": (
            web_evidence.consistency_verdict_label if web_evidence else None
        ),
        "relationship": relationship.value,
        "relationship_label": _RELATIONSHIP_LABELS[relationship],
        "relationship_detail": relationship_detail(relationship),
        "attention_claims": [claim.model_dump(mode="json") for claim in attention],
        # Overall VeriFact Assessment
        "overall_verdict": overall_verdict.value,
        "overall_label": _OVERALL_LABELS[overall_verdict],
        "overall_explanation": overall_explanation,
        "metaqa_summary_text": metaqa_summary_text,
        "web_summary_text": web_summary_text,
        "combined_risk_score": combined_risk,
        "web_risk_score": web_risk,
        "overall_note": OVERALL_RESEARCH_NOTE,
    }
