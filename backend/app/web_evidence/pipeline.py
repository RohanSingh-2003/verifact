from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from app.config import Settings
from app.llm.base import LLMClient, LLMError
from app.web_evidence.claims import extract_web_claims
from app.web_evidence.classifier import QuestionClassification, classify_question
from app.web_evidence.dedupe import dedupe_sources
from app.web_evidence.question_types import QUESTION_TYPE_LABELS
from app.web_evidence.search_query import claim_to_search_query
from app.web_evidence.source_quality import classify_source_type, normalize_source_type_value
from app.web_evidence.strategies import SourceStrategy, get_source_strategy
from app.web_evidence.types import (
    EvidenceVerdict,
    ExtractedClaim,
    VerifiedClaim,
    WebEvidenceResult,
    WebEvidenceStatus,
)
from app.web_evidence.evidence_extractor import extract_source_evidence
from app.web_evidence.verifier import verify_claims_batch
from app.web_search.base import WebSearchAuthError, WebSearchClient, WebSearchError, WebSource

logger = logging.getLogger("verifact.web_evidence.pipeline")

StageCallback = Callable[[str], None]


def build_web_search_client(settings: Settings) -> WebSearchClient | None:
    """Return a search client, or None when Web Evidence cannot run."""
    if not settings.web_evidence_enabled:
        return None
    if not settings.tavily_configured:
        return None
    from app.web_search.tavily_client import TavilyClient

    return TavilyClient(settings)


def _annotate_sources(
    sources: list[WebSource],
    *,
    question_type: str,
) -> list[WebSource]:
    enriched: list[WebSource] = []
    for source in sources:
        source_type = normalize_source_type_value(
            source.source_type or classify_source_type(source.domain, source.url).value
        )
        enriched.append(
            WebSource(
                title=source.title,
                url=source.url,
                domain=source.domain,
                snippet=source.snippet,
                published_at=source.published_at,
                relevance_score=source.relevance_score,
                source_type=source_type,
                question_type=question_type,
            )
        )
    return enriched


def _annotate_and_sort_sources(
    sources: list[WebSource],
    *,
    question_type: str,
) -> list[WebSource]:
    """Annotate sources and sort them so authoritative and primary sources appear first."""
    from app.web_evidence.source_quality import source_tier_rank

    annotated = _annotate_sources(dedupe_sources(sources), question_type=question_type)
    # Lower tier rank = higher priority (Tier 1 Primary < Tier 2 Academic < ... < Tier 6 Low Priority)
    annotated.sort(key=lambda s: (source_tier_rank(s.source_type), -(s.relevance_score or 0.0)))
    return annotated


def _routing_fields(classification: QuestionClassification, strategy: SourceStrategy) -> dict:
    return {
        "question_type": classification.type.value,
        "question_type_label": QUESTION_TYPE_LABELS[classification.type],
        "question_type_confidence": classification.confidence,
        "source_strategy_labels": list(strategy.labels),
        "freshness_required": classification.freshness_required,
    }


async def _search_once(
    search: WebSearchClient,
    query: str,
    *,
    max_results: int,
    include_domains: list[str] | None,
    days: int | None,
    topic: str | None,
    question_type: str | None = None,
) -> list[WebSource]:
    return await search.search(
        query,
        max_results=max_results,
        include_domains=include_domains,
        days=days,
        topic=topic,
        question_type=question_type,
    )


async def _search_claims_concurrent(
    search: WebSearchClient,
    claims: list[ExtractedClaim],
    *,
    preferred_domains: list[str] | None = None,
    secondary_domains: list[str] | None = None,
    question_text: str = "",
    results_per_claim: int,
    max_searches: int,
    days: int | None,
    topic: str,
    question_type: str,
) -> tuple[list[tuple[str, str, str, list[WebSource], bool]], int, int, bool, str | None, float]:
    """Search claims using a multi-pass strategy within max_searches budget.

    Pass 1: Preferred authoritative domains for the question type.
    Pass 2: Broader reputable secondary domains (if preferred returned no results).
    Pass 3: General web search fallback (if still no results, sorted by tier rank).
    """
    from app.web_evidence.verifier import sources_have_usable_snippets

    prepared: list[tuple[ExtractedClaim, str]] = []
    empty_query: list[tuple[str, str, str, list[WebSource], bool]] = []
    for claim in claims:
        query = claim_to_search_query(
            claim.text,
            question_type=question_type,
            question_text=question_text,
        )
        if not query:
            empty_query.append((claim.id, claim.text, "", [], False))
        else:
            prepared.append((claim, query))

    budget = min(len(prepared), max_searches)
    batch = prepared[:budget]
    deferred = prepared[budget:]

    pref_list = [d for d in (preferred_domains or []) if d and d.strip()]
    sec_list = [d for d in (secondary_domains or []) if d and d.strip()]

    async def pass1(
        claim: ExtractedClaim, query: str
    ) -> tuple[str, ExtractedClaim, str, list[WebSource], Exception | None]:
        try:
            hits = await _search_once(
                search,
                query,
                max_results=results_per_claim,
                include_domains=pref_list or None,
                days=days,
                topic=topic,
                question_type=question_type,
            )
            return ("ok", claim, query, hits, None)
        except WebSearchAuthError as exc:
            return ("auth", claim, query, [], exc)
        except WebSearchError as exc:
            return ("err", claim, query, [], exc)

    search_started = time.perf_counter()
    pass1_results = await asyncio.gather(*[pass1(c, q) for c, q in batch]) if batch else []
    searches_used = len(batch)

    auth_failed = False
    search_error: str | None = None
    resolved_claims: list[tuple[str, str, str, list[WebSource], bool]] = []
    needs_fallback: list[tuple[ExtractedClaim, str]] = []

    for kind, claim, query, hits, exc in pass1_results:
        if kind == "auth":
            auth_failed = True
            search_error = str(exc) if exc else "Web search authentication failed."
            resolved_claims.append((claim.id, claim.text, query, [], False))
        elif kind == "err":
            search_error = str(exc) if exc else "Web search failed."
            # On network error on preferred pass, queue for fallback if budget permits
            if pref_list:
                needs_fallback.append((claim, query))
            else:
                resolved_claims.append((claim.id, claim.text, query, [], False))
        else:
            usable = [h for h in hits if sources_have_usable_snippets([h])]
            if usable:
                unique = _annotate_and_sort_sources(usable, question_type=question_type)
                resolved_claims.append((claim.id, claim.text, query, unique, False))
            elif pref_list:
                # Preferred domains returned 0 usable hits — try fallback!
                needs_fallback.append((claim, query))
            else:
                unique = _annotate_and_sort_sources(hits, question_type=question_type)
                resolved_claims.append((claim.id, claim.text, query, unique, False))

    # PASS 2 & PASS 3: Fallback for claims with 0 preferred hits
    remaining_budget = max(0, max_searches - searches_used)
    if needs_fallback and remaining_budget > 0 and not auth_failed:
        fallback_batch = needs_fallback[:remaining_budget]
        fallback_deferred = needs_fallback[remaining_budget:]

        async def run_fallback(
            claim: ExtractedClaim, query: str
        ) -> tuple[str, ExtractedClaim, str, list[WebSource], Exception | None]:
            # Try secondary domains first if available
            if sec_list:
                try:
                    hits2 = await _search_once(
                        search,
                        query,
                        max_results=results_per_claim,
                        include_domains=sec_list,
                        days=days,
                        topic=topic,
                        question_type=question_type,
                    )
                    usable2 = [h for h in hits2 if sources_have_usable_snippets([h])]
                    if usable2:
                        return ("ok", claim, query, usable2, None)
                except WebSearchError:
                    pass

            # Fall back to general web search
            try:
                hits_gen = await _search_once(
                    search,
                    query,
                    max_results=results_per_claim,
                    include_domains=None,
                    days=days,
                    topic=topic,
                    question_type=question_type,
                )
                return ("ok", claim, query, hits_gen, None)
            except WebSearchAuthError as exc:
                return ("auth", claim, query, [], exc)
            except WebSearchError as exc:
                return ("err", claim, query, [], exc)

        fb_results = await asyncio.gather(*[run_fallback(c, q) for c, q in fallback_batch])
        searches_used += len(fallback_batch)

        for kind, claim, query, hits, exc in fb_results:
            if kind == "auth":
                auth_failed = True
                search_error = str(exc) if exc else "Web search authentication failed."
                resolved_claims.append((claim.id, claim.text, query, [], True))
            elif kind == "err":
                search_error = str(exc) if exc else "Web search fallback failed."
                resolved_claims.append((claim.id, claim.text, query, [], True))
            else:
                usable = [h for h in hits if sources_have_usable_snippets([h])]
                unique = _annotate_and_sort_sources(usable or hits, question_type=question_type)
                resolved_claims.append((claim.id, claim.text, query, unique, True))

        for claim, query in fallback_deferred:
            resolved_claims.append((claim.id, claim.text, query, [], True))
    else:
        for claim, query in needs_fallback:
            resolved_claims.append((claim.id, claim.text, query, [], True))

    for claim, query in deferred:
        resolved_claims.append((claim.id, claim.text, query, [], False))

    search_ms = (time.perf_counter() - search_started) * 1000

    # Preserve original claim order
    claim_order = {claim.id: idx for idx, claim in enumerate(claims)}
    all_results = empty_query + resolved_claims
    all_results.sort(key=lambda item: claim_order.get(item[0], 10_000))

    sources_found = sum(len(sources) for _, _, _, sources, _ in all_results)

    logger.info(
        "web_search_ms=%.0f searches=%s sources=%s concurrent=%s fallback_needed=%s",
        search_ms,
        searches_used,
        sources_found,
        len(batch),
        len(needs_fallback),
    )
    return all_results, searches_used, sources_found, auth_failed, search_error, search_ms


async def run_web_evidence(
    llm: LLMClient,
    search: WebSearchClient,
    *,
    question: str,
    answer: str,
    settings: Settings,
    model: str | None = None,
    on_stage: StageCallback | None = None,
) -> WebEvidenceResult:
    """Classify → claims → one search/claim (concurrent) → batch evidence verify.

    Isolated from MetaQA. Failures return structured results; never invent SUPPORTED.
    """
    verifier_model = settings.require_model(model or settings.verifier_model)
    max_claims = settings.web_max_claims
    max_searches = settings.web_max_searches
    results_per_claim = settings.web_results_per_claim
    pipeline_started = time.perf_counter()

    def set_stage(stage: WebEvidenceStatus) -> None:
        if on_stage is not None:
            on_stage(stage.value)

    set_stage(WebEvidenceStatus.CLASSIFYING_QUESTION)
    classification = classify_question(question)
    strategy = get_source_strategy(classification.type)
    routing = _routing_fields(classification, strategy)
    logger.info(
        "Web Evidence routing type=%s confidence=%.2f freshness=%s domains=%s",
        classification.type.value,
        classification.confidence,
        classification.freshness_required,
        len(strategy.preferred_include_domains),
    )

    set_stage(WebEvidenceStatus.EXTRACTING_CLAIMS)
    claim_started = time.perf_counter()
    try:
        claims = await extract_web_claims(
            llm,
            model=verifier_model,
            question=question,
            answer=answer,
            max_claims=max_claims,
            max_tokens=settings.llm_web_claim_max_tokens,
        )
    except LLMError as exc:
        logger.warning("web evidence claim extraction failed: %s", exc)
        return _finalize(
            WebEvidenceResult(
                status=WebEvidenceStatus.FAILED,
                error="Web Evidence could not extract factual claims from the answer.",
                **routing,
            )
        )
    claim_ms = (time.perf_counter() - claim_started) * 1000
    logger.info("web_claim_extraction_ms=%.0f claims=%s", claim_ms, len(claims))

    if not claims:
        return _finalize(
            WebEvidenceResult(
                status=WebEvidenceStatus.COMPLETED,
                error="No independently verifiable factual claims were found in the answer.",
                claims=[],
                searches_used=0,
                sources_found=0,
                **routing,
            )
        )

    claims = claims[: min(len(claims), max_claims, max_searches)]
    set_stage(WebEvidenceStatus.SEARCHING_WEB)

    preferred_domains = list(strategy.preferred_include_domains)
    secondary_domains = list(strategy.secondary_include_domains)
    days = strategy.default_days if classification.freshness_required else None
    topic = strategy.topic if strategy.topic else "general"

    (
        claim_sources,
        searches_used,
        sources_found,
        auth_failed,
        search_error,
        search_ms,
    ) = await _search_claims_concurrent(
        search,
        claims,
        preferred_domains=preferred_domains,
        secondary_domains=secondary_domains,
        question_text=question,
        results_per_claim=results_per_claim,
        max_searches=max_searches,
        days=days,
        topic=topic,
        question_type=classification.type.value,
    )

    used_fallback_search = any(used_fb for _, _, _, _, used_fb in claim_sources)

    if auth_failed and not any(sources for _, _, _, sources, _ in claim_sources):
        return _finalize(
            WebEvidenceResult(
                status=WebEvidenceStatus.FAILED,
                error=f"Web evidence unavailable: {search_error}",
                searches_used=searches_used,
                sources_found=0,
                used_fallback_search=used_fallback_search,
                timing_ms={
                    "web_total_ms": round((time.perf_counter() - pipeline_started) * 1000, 1),
                    "web_claim_extraction_ms": round(claim_ms, 1),
                    "web_search_ms": round(search_ms, 1),
                    "web_verification_ms": 0.0,
                    "total_analysis_ms": round((time.perf_counter() - pipeline_started) * 1000, 1),
                },
                **routing,
            )
        )

    set_stage(WebEvidenceStatus.VERIFYING_EVIDENCE)
    verify_started = time.perf_counter()
    batch_input = [
        (claim_id, claim_text, sources) for claim_id, claim_text, _query, sources, _fb in claim_sources
    ]
    # Slightly larger token budget for batch JSON (still compact reasons).
    batch_tokens = max(settings.llm_web_verify_max_tokens, min(480, 120 * max(1, len(batch_input))))
    verdict_map = await verify_claims_batch(
        llm,
        model=verifier_model,
        claims=batch_input,
        max_tokens=batch_tokens,
    )
    verify_ms = (time.perf_counter() - verify_started) * 1000
    logger.info("web_verification_ms=%.0f claims=%s", verify_ms, len(batch_input))

    verified: list[VerifiedClaim] = []
    for claim_id, claim_text, query, sources, used_fallback in claim_sources:
        verdict_reason = verdict_map.get(claim_id)
        if verdict_reason is None:
            verdict = EvidenceVerdict.INSUFFICIENT_EVIDENCE
            reason = "Evidence verification could not be completed for this claim."
        else:
            verdict, reason = verdict_reason

        if verdict is EvidenceVerdict.SUPPORTED and not sources:
            verdict = EvidenceVerdict.INSUFFICIENT_EVIDENCE
            reason = "No web sources were retrieved for this claim."
        if not sources and verdict is EvidenceVerdict.CONTRADICTED:
            verdict = EvidenceVerdict.INSUFFICIENT_EVIDENCE
            reason = "No web sources were retrieved for this claim."

        enriched_sources: list[WebSource] = []
        for src in sources:
            summary = src.evidence_summary
            if not summary:
                summary = extract_source_evidence(claim_text, src, verdict)
            enriched_sources.append(
                WebSource(
                    title=src.title,
                    url=src.url,
                    domain=src.domain,
                    snippet=src.snippet,
                    published_at=src.published_at,
                    relevance_score=src.relevance_score,
                    source_type=src.source_type,
                    question_type=src.question_type,
                    evidence_summary=summary,
                )
            )

        verified.append(
            VerifiedClaim(
                id=claim_id,
                text=claim_text,
                search_query=query or claim_to_search_query(claim_text),
                verdict=verdict,
                reason=reason,
                sources=enriched_sources,
                used_fallback=used_fallback,
            )
        )

    total_ms = (time.perf_counter() - pipeline_started) * 1000
    timing_dict = {
        "web_total_ms": round(total_ms, 1),
        "web_claim_extraction_ms": round(claim_ms, 1),
        "web_search_ms": round(search_ms, 1),
        "web_verification_ms": round(verify_ms, 1),
        "total_analysis_ms": round(total_ms, 1),
    }
    logger.info(
        "Web Evidence: type=%s claims=%s searches=%s sources=%s "
        "web_claim_extraction_ms=%.0f web_search_ms=%.0f web_verification_ms=%.0f total_analysis_ms=%.0f",
        classification.type.value,
        len(verified),
        searches_used,
        sources_found,
        claim_ms,
        search_ms,
        verify_ms,
        total_ms,
    )
    set_stage(WebEvidenceStatus.COMPLETED)
    return _finalize(
        WebEvidenceResult(
            status=WebEvidenceStatus.COMPLETED,
            claims=verified,
            error=None,
            searches_used=searches_used,
            sources_found=sources_found,
            used_fallback_search=used_fallback_search,
            timing_ms=timing_dict,
            **routing,
        )
    )


def _finalize(result: WebEvidenceResult) -> WebEvidenceResult:
    """Attach consistency score without touching MetaQA."""
    result.finalize_score()
    return result


def unavailable_result(message: str) -> WebEvidenceResult:
    return _finalize(
        WebEvidenceResult(
            status=WebEvidenceStatus.UNAVAILABLE,
            error=message,
        )
    )

