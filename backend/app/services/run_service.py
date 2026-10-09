from __future__ import annotations

import json

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import Mutation, Run, new_id
from app.metaqa.detector import DetectionResult, ScoredMutation
from app.metaqa.mutation import GeneratedMutation
from app.metaqa.scoring import Classification, expected_verdict
from app.schemas.detect import (
    BaseAnswerOut,
    DetectResponse,
    DetectTiming,
    MutationOut,
    OverallStatus,
    RunListResponse,
    RunStatus,
    RunSummary,
)
from app.schemas.verification_summary import VerificationSummaryOut
from app.schemas.web_evidence import WebClaimOut, WebEvidenceOut, WebSourceOut
from app.services.overall_status import derive_overall_status
from app.services.verification_summary import build_verification_summary
from app.web_evidence.types import EvidenceVerdict, WebEvidenceResult, WebEvidenceStatus


INCOMPLETE_CLASSIFICATION = "Incomplete"
PENDING_VERDICT = ""

MUTATION_GENERATION_ERROR = (
    "Hallucination analysis could not be completed because the mutation generator "
    "did not return the required mutation set. The generated answer is still available above."
)
CLAIM_EXTRACTION_ERROR = (
    "Hallucination analysis could not be completed because core claim extraction failed. "
    "The generated answer is still available above."
)
VERIFICATION_ERROR = (
    "MetaQA analysis is unavailable because mutation verification did not complete. "
    "The generated answer remains available. Web Evidence may still finish independently."
)
PARTIAL_VERIFICATION_NOTE = (
    "MetaQA partially completed: {verified} of {expected} mutations verified. "
    "Score uses only completed verification results."
)
SCORING_ERROR = (
    "Hallucination analysis could not be completed while calculating the score. "
    "The generated answer and any mutations above are still available."
)
GENERIC_ANALYSIS_ERROR = (
    "Hallucination analysis could not be completed. The generated answer is still available above."
)


def classify_analysis_failure(
    exc: BaseException,
    *,
    stage: str | None = None,
) -> tuple[RunStatus, str]:
    """Map a MetaQA-stage exception to a failure status and user-facing message.

    Never treats mutation/verification failures as answer-generation failures.
    """
    message = str(exc) or ""
    lower = message.casefold()
    stage_value = (stage or "").casefold()

    if "gemini" in lower or "verif" in lower or stage_value == RunStatus.VERIFYING_MUTATIONS.value:
        if "429" in lower or "rate" in lower or "quota" in lower:
            return RunStatus.VERIFICATION_FAILED, "FAILED\nReason: Verifier API returned HTTP 429 (rate limit)"
        if "503" in lower or "unavailable" in lower or "high demand" in lower:
            return RunStatus.VERIFICATION_FAILED, "FAILED\nReason: Verifier API returned HTTP 503 (service unavailable)"
        if "401" in lower or "403" in lower or "unauthorized" in lower:
            return RunStatus.VERIFICATION_FAILED, "FAILED\nReason: Verifier API returned HTTP 401/403 (unauthorized). Check provider credentials."
        if "400" in lower or "bad request" in lower or "invalid" in lower:
            return RunStatus.VERIFICATION_FAILED, "FAILED\nReason: Verifier API returned HTTP 400 (invalid request)."
        if "timeout" in lower:
            return RunStatus.VERIFICATION_FAILED, "FAILED\nReason: Verifier API request timed out."
        if message and not message.startswith("FAILED"):
            return RunStatus.VERIFICATION_FAILED, f"FAILED\nReason: {message}"
        return RunStatus.VERIFICATION_FAILED, VERIFICATION_ERROR
    if "score" in lower or stage_value == RunStatus.CALCULATING_SCORE.value:
        return RunStatus.SCORING_FAILED, SCORING_ERROR
    if stage_value in {
        RunStatus.GENERATING_MUTATIONS.value,
        RunStatus.ANSWER_READY.value,
        RunStatus.MUTATIONS_READY.value,
        "",
    }:
        return RunStatus.MUTATION_GENERATION_FAILED, MUTATION_GENERATION_ERROR
    return RunStatus.FAILED, GENERIC_ANALYSIS_ERROR



def persist_detection(db: Session, result: DetectionResult) -> DetectResponse:
    """Persist a fully completed detection (used by experiments / sync paths)."""
    run = Run(
        id=new_id(),
        question=result.question,
        generator_model=result.generator_model,
        mutation_generator_model=result.generator_model,
        mutation_verifier_model=result.verifier_model,
        base_answer=result.base_answer.text,
        hallucination_score=result.hallucination_score,
        threshold=result.threshold,
        classification=result.classification.value,
        not_sure_rate=result.not_sure_rate,
        llm_mode=result.llm_mode,
        status=RunStatus.COMPLETED.value,
        analysis_error="",
    )
    if result.timing is not None:
        run.answer_ms = result.timing.answer_ms
        run.mutation_ms = result.timing.mutation_ms
        run.verify_ms = result.timing.verify_ms
        run.total_ms = result.timing.total_ms
    for index, item in enumerate(result.mutations):
        run.mutations.append(
            Mutation(
                id=new_id(),
                type=item.mutation.type.value,
                original_text=item.mutation.original_text,
                mutated_text=item.mutation.mutated_text,
                verifier_model=result.verifier_model,
                verdict=item.verdict.value,
                expected_verdict=item.expected.value,
                contribution=item.contribution,
                rationale=item.rationale,
                parse_failed=item.parse_failed,
                verified=True,
                position=index,
            )
        )
    db.add(run)
    db.flush()
    db.refresh(run)
    return to_detect_response(run)


def create_answer_ready_run(
    db: Session,
    *,
    question: str,
    base_answer: str,
    generator_model: str,
    threshold: float,
    llm_mode: str = "live",
    answer_ms: float | None = None,
    ai_verdicts_json: str = "",
) -> Run:
    run = Run(
        id=new_id(),
        question=question,
        generator_model=generator_model,
        base_answer=base_answer,
        hallucination_score=0.0,
        threshold=threshold,
        classification=INCOMPLETE_CLASSIFICATION,
        not_sure_rate=0.0,
        llm_mode=llm_mode,
        status=RunStatus.ANSWER_READY.value,
        analysis_error="",
        web_evidence_status=WebEvidenceStatus.PENDING.value,
        web_evidence_error="",
        web_evidence_json="",
        ai_verdicts_json=ai_verdicts_json,
        answer_ms=answer_ms,
    )
    db.add(run)
    db.flush()
    db.refresh(run)
    return run


def update_web_evidence_status(db: Session, run_id: str, status: WebEvidenceStatus) -> None:
    run = db.get(Run, run_id)
    if run is None:
        return
    run.web_evidence_status = status.value
    db.flush()


def persist_web_evidence_result(db: Session, run_id: str, result: WebEvidenceResult) -> None:
    """Store Web Evidence payload without touching MetaQA fields or base_answer."""
    run = db.get(Run, run_id)
    if run is None:
        return
    run.web_evidence_status = result.status.value
    run.web_evidence_error = (result.error or "").strip()
    run.web_evidence_json = json.dumps(result.to_dict(), ensure_ascii=False)
    db.flush()


def web_evidence_from_run(run: Run) -> WebEvidenceOut | None:
    status_raw = getattr(run, "web_evidence_status", None) or WebEvidenceStatus.PENDING.value
    try:
        status = WebEvidenceStatus(status_raw)
    except ValueError:
        status = WebEvidenceStatus.PENDING

    payload: dict | None = None
    raw_json = getattr(run, "web_evidence_json", "") or ""
    if raw_json.strip():
        try:
            loaded = json.loads(raw_json)
            if isinstance(loaded, dict):
                payload = loaded
        except json.JSONDecodeError:
            payload = None

    if payload is None:
        error = getattr(run, "web_evidence_error", "") or None
        return WebEvidenceOut(
            status=status,
            error=error or None,
            claims=[],
        )

    claims_out: list[WebClaimOut] = []
    for item in payload.get("claims") or []:
        if not isinstance(item, dict):
            continue
        verdict_raw = str(item.get("verdict") or EvidenceVerdict.INSUFFICIENT_EVIDENCE.value)
        try:
            verdict = EvidenceVerdict(verdict_raw)
        except ValueError:
            verdict = EvidenceVerdict.INSUFFICIENT_EVIDENCE
        sources = []
        for source in item.get("sources") or []:
            if not isinstance(source, dict):
                continue
            url = str(source.get("url") or "").strip()
            if not url:
                continue
            sources.append(
                WebSourceOut(
                    title=str(source.get("title") or url),
                    url=url,
                    domain=str(source.get("domain") or ""),
                    snippet=str(source.get("snippet") or ""),
                    published_at=source.get("published_at"),
                    relevance_score=source.get("relevance_score"),
                    source_type=str(source.get("source_type") or "GENERAL"),
                    question_type=source.get("question_type"),
                )
            )
        claims_out.append(
            WebClaimOut(
                id=str(item.get("id") or f"claim_{len(claims_out) + 1}"),
                text=str(item.get("text") or ""),
                search_query=str(item.get("search_query") or ""),
                verdict=verdict,
                reason=str(item.get("reason") or ""),
                used_fallback=bool(item.get("used_fallback")),
                sources=sources,
            )
        )

    return WebEvidenceOut(
        status=status,
        error=payload.get("error") or (getattr(run, "web_evidence_error", "") or None),
        searches_used=int(payload.get("searches_used") or 0),
        sources_found=int(payload.get("sources_found") or 0),
        question_type=payload.get("question_type"),
        question_type_label=payload.get("question_type_label"),
        question_type_confidence=payload.get("question_type_confidence"),
        source_strategy_labels=list(payload.get("source_strategy_labels") or []),
        freshness_required=bool(payload.get("freshness_required")),
        used_fallback_search=bool(payload.get("used_fallback_search")),
        total_claims=int(payload.get("total_claims") or len(claims_out)),
        supported_claims=int(payload.get("supported_claims") or 0),
        contradicted_claims=int(payload.get("contradicted_claims") or 0),
        insufficient_claims=int(payload.get("insufficient_claims") or 0),
        consistency_score=(
            float(payload["consistency_score"])
            if payload.get("consistency_score") is not None
            else None
        ),
        consistency_verdict=payload.get("consistency_verdict"),
        consistency_verdict_label=payload.get("consistency_verdict_label"),
        claims=claims_out,
    )


def update_run_status(db: Session, run_id: str, status: RunStatus) -> None:
    run = db.get(Run, run_id)
    if run is None:
        return
    run.status = status.value
    db.flush()


def persist_pending_mutations(
    db: Session,
    run_id: str,
    *,
    mutations: list[GeneratedMutation],
    verifier_model: str,
    verifier_models: list[str] | None = None,
    mutation_ms: float | None = None,
) -> None:
    """Persist generated mutations before verification so the API can show them."""
    run = db.execute(
        select(Run).options(selectinload(Run.mutations)).where(Run.id == run_id)
    ).scalar_one_or_none()
    if run is None:
        return

    initial_verdicts_json = ""
    if verifier_models:
        from app.llm.registry import MODEL_REGISTRY
        pending_list = [
            {
                "model_id": mid,
                "model_name": MODEL_REGISTRY[mid].display_name if mid in MODEL_REGISTRY else mid,
                "model": MODEL_REGISTRY[mid].display_name if mid in MODEL_REGISTRY else mid,
                "provider": MODEL_REGISTRY[mid].provider_display if mid in MODEL_REGISTRY else "",
                "verdict": "PENDING",
                "rationale": "",
                "error": None,
                "contribution": None,
                "status": "pending",
            }
            for mid in verifier_models
        ]
        initial_verdicts_json = json.dumps(pending_list, ensure_ascii=False)

    run.mutations.clear()
    for index, item in enumerate(mutations):
        run.mutations.append(
            Mutation(
                id=new_id(),
                type=item.type.value,
                original_text=item.original_text,
                mutated_text=item.mutated_text,
                verifier_model=verifier_model,
                verdict=PENDING_VERDICT,
                expected_verdict=expected_verdict(item.type).value,
                contribution=0.0,
                rationale="",
                parse_failed=False,
                verified=False,
                position=index,
                verdicts_json=initial_verdicts_json,
            )
        )
    run.status = RunStatus.MUTATIONS_READY.value
    if mutation_ms is not None:
        run.mutation_ms = mutation_ms
    db.flush()


def update_mutation_verification(
    db: Session,
    run_id: str,
    position: int,
    scored: ScoredMutation,
) -> None:
    run = db.execute(
        select(Run).options(selectinload(Run.mutations)).where(Run.id == run_id)
    ).scalar_one_or_none()
    if run is None:
        return
    for item in run.mutations:
        if item.position == position:
            item.verdict = scored.verdict.value if scored.verdict is not None else ""
            item.expected_verdict = scored.expected.value
            item.contribution = scored.contribution if not scored.unavailable else 0.0
            item.rationale = scored.rationale
            item.parse_failed = scored.parse_failed or scored.unavailable
            item.verified = not scored.unavailable and not scored.parse_failed and scored.verdict is not None
            if getattr(scored, "verdicts", None):
                item.verdicts_json = json.dumps(
                    [v.model_dump() if hasattr(v, "model_dump") else dict(v) for v in scored.verdicts],
                    ensure_ascii=False,
                )
            break
    db.flush()


def complete_run_analysis(
    db: Session,
    run_id: str,
    result: DetectionResult,
) -> Run | None:
    run = db.execute(
        select(Run).options(selectinload(Run.mutations)).where(Run.id == run_id)
    ).scalar_one_or_none()
    if run is None:
        return None

    run.hallucination_score = result.hallucination_score
    run.threshold = result.threshold
    run.classification = result.classification.value
    run.not_sure_rate = result.not_sure_rate
    run.mutation_generator_model = result.generator_model
    run.mutation_verifier_model = result.verifier_model
    run.status = RunStatus.COMPLETED.value
    if result.metaqa_completion == "partial" and result.expected_count:
        run.analysis_error = PARTIAL_VERIFICATION_NOTE.format(
            verified=result.verified_count,
            expected=result.expected_count,
        )
    else:
        run.analysis_error = ""
    if result.timing is not None:
        run.answer_ms = result.timing.answer_ms
        run.mutation_ms = result.timing.mutation_ms
        run.verify_ms = result.timing.verify_ms
        run.total_ms = result.timing.total_ms

    # Ensure mutation rows match final scored results (stable positions).
    by_position = {item.position: item for item in run.mutations}
    for index, scored in enumerate(result.mutations):
        existing = by_position.get(index)
        is_verified = not scored.unavailable and not scored.parse_failed and scored.verdict is not None
        verdict_str = scored.verdict.value if scored.verdict is not None else ""
        verdicts_json = ""
        if getattr(scored, "verdicts", None):
            verdicts_json = json.dumps(
                [v.model_dump() if hasattr(v, "model_dump") else dict(v) for v in scored.verdicts],
                ensure_ascii=False,
            )
        if existing is None:
            run.mutations.append(
                Mutation(
                    id=new_id(),
                    type=scored.mutation.type.value,
                    original_text=scored.mutation.original_text,
                    mutated_text=scored.mutation.mutated_text,
                    verifier_model=result.verifier_model,
                    verdict=verdict_str,
                    expected_verdict=scored.expected.value,
                    contribution=scored.contribution if is_verified else 0.0,
                    rationale=scored.rationale,
                    parse_failed=scored.parse_failed or scored.unavailable,
                    verified=is_verified,
                    position=index,
                    verdicts_json=verdicts_json,
                )
            )
        else:
            existing.type = scored.mutation.type.value
            existing.original_text = scored.mutation.original_text
            existing.mutated_text = scored.mutation.mutated_text
            existing.verifier_model = result.verifier_model
            existing.verdict = verdict_str
            existing.expected_verdict = scored.expected.value
            existing.contribution = scored.contribution if is_verified else 0.0
            existing.rationale = scored.rationale
            existing.parse_failed = scored.parse_failed or scored.unavailable
            existing.verified = is_verified
            if verdicts_json:
                existing.verdicts_json = verdicts_json
    db.flush()
    db.refresh(run)
    return run


def fail_run_analysis(
    db: Session,
    run_id: str,
    message: str,
    *,
    status: RunStatus = RunStatus.FAILED,
) -> None:
    """Record a MetaQA-stage failure without clearing the persisted answer.

    Earlier-stage data (base_answer, mutations, partial verifier results) is kept.
    Score/classification are not finalized — callers must not invent results.
    """
    run = db.get(Run, run_id)
    if run is None:
        return
    # Preserve base_answer and any mutations already stored on the run.
    run.status = status.value if RunStatus.is_failure(status) else RunStatus.FAILED.value
    run.analysis_error = message.strip() or GENERIC_ANALYSIS_ERROR
    # Do not publish a fake completed score/classification.
    run.classification = INCOMPLETE_CLASSIFICATION
    db.flush()


def get_run(db: Session, run_id: str) -> Run | None:
    statement = select(Run).options(selectinload(Run.mutations)).where(Run.id == run_id)
    return db.execute(statement).scalar_one_or_none()


def list_runs(db: Session, *, limit: int, offset: int) -> RunListResponse:
    total = db.execute(select(func.count()).select_from(Run)).scalar_one()
    statement = (
        select(Run)
        .order_by(desc(Run.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = db.execute(statement).scalars().all()
    return RunListResponse(
        items=[_to_run_summary(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def _is_complete(run: Run) -> bool:
    return run.status == RunStatus.COMPLETED.value


def _parse_run_status(value: str) -> RunStatus:
    if value in RunStatus._value2member_map_:
        return RunStatus(value)
    return RunStatus.COMPLETED


def _to_run_summary(run: Run) -> RunSummary:
    status = _parse_run_status(run.status)
    if not _is_complete(run):
        return RunSummary(
            id=run.id,
            question=run.question,
            generator_model=run.generator_model,
            hallucination_score=None,
            classification=None,
            status=status,
            created_at=run.created_at,
        )
    return RunSummary(
        id=run.id,
        question=run.question,
        generator_model=run.generator_model,
        hallucination_score=run.hallucination_score,
        classification=(
            Classification(run.classification)
            if run.classification in Classification._value2member_map_
            else None
        ),
        status=status,
        created_at=run.created_at,
    )


def _mutation_out(item: Mutation) -> MutationOut:
    from app.metaqa.scoring import Verdict as VerdictEnum
    from app.schemas.detect import ModelVerifierVerdict

    verified = bool(getattr(item, "verified", True)) and bool(item.verdict) and not bool(item.parse_failed)
    verdict = None
    contribution: float | None = None
    if verified:
        try:
            verdict = VerdictEnum(item.verdict)
            contribution = float(item.contribution)
        except ValueError:
            verified = False
    expected = (
        VerdictEnum(item.expected_verdict)
        if item.expected_verdict in VerdictEnum._value2member_map_
        else VerdictEnum.YES
    )
    verdicts_list: list[ModelVerifierVerdict] = []
    if getattr(item, "verdicts_json", None):
        try:
            raw_v = json.loads(item.verdicts_json)
            if isinstance(raw_v, list):
                verdicts_list = [ModelVerifierVerdict.model_validate(v) for v in raw_v]
        except Exception:
            pass

    if not verdicts_list and getattr(item, "verifier_model", None):
        verdicts_list = [
            ModelVerifierVerdict(
                model_id="verifier",
                model_name=item.verifier_model,
                model=item.verifier_model,
                provider="Cloud",
                verdict=item.verdict or "PENDING",
                rationale=item.rationale or "",
                contribution=contribution,
                status="completed" if verified else ("failed" if item.parse_failed else "pending"),
            )
        ]

    return MutationOut(
        id=item.id,
        type=item.type,
        original_text=item.original_text,
        mutated_text=item.mutated_text,
        verifier_model=getattr(item, "verifier_model", None),
        verdict=verdict,
        expected_verdict=expected,
        contribution=contribution,
        rationale=item.rationale or ("Verification failed" if not verified else ""),
        parse_failed=bool(item.parse_failed) or not verified,
        verified=verified,
        verdicts=verdicts_list,
    )


def to_detect_response(run: Run) -> DetectResponse:
    status = _parse_run_status(run.status)
    complete = status == RunStatus.COMPLETED
    # Expose mutations as soon as they exist (pending or verified), including after failures.
    include_mutations = status in {
        RunStatus.MUTATIONS_READY,
        RunStatus.VERIFYING_MUTATIONS,
        RunStatus.CALCULATING_SCORE,
        RunStatus.COMPLETED,
        RunStatus.MUTATION_GENERATION_FAILED,
        RunStatus.VERIFICATION_FAILED,
        RunStatus.SCORING_FAILED,
        RunStatus.FAILED,
    } or bool(run.mutations)
    web_evidence = web_evidence_from_run(run)
    raw_json = getattr(run, "web_evidence_json", "") or ""
    web_timing: dict = {}
    if raw_json.strip():
        try:
            loaded = json.loads(raw_json)
            if isinstance(loaded, dict) and isinstance(loaded.get("timing"), dict):
                web_timing = loaded["timing"]
        except (json.JSONDecodeError, TypeError, KeyError):
            web_timing = {}

    web_total = web_timing.get("web_total_ms")
    metaqa_total = run.total_ms if complete else None
    answer_ms = run.answer_ms
    tot_analysis = None
    if answer_ms is not None:
        branches = [b for b in (metaqa_total, web_total) if b is not None]
        if branches:
            tot_analysis = round(answer_ms + max(branches), 1)

    timing = DetectTiming(
        answer_ms=run.answer_ms,
        mutation_ms=run.mutation_ms,
        verify_ms=run.verify_ms if complete else None,
        total_ms=run.total_ms if complete else None,
        time_to_answer_ms=run.answer_ms,
        answer_generation_ms=run.answer_ms,
        metaqa_total_ms=metaqa_total,
        metaqa_mutation_generation_ms=run.mutation_ms,
        metaqa_verification_ms=run.verify_ms if complete else None,
        web_total_ms=web_timing.get("web_total_ms"),
        web_claim_extraction_ms=web_timing.get("web_claim_extraction_ms"),
        web_search_ms=web_timing.get("web_search_ms"),
        web_verification_ms=web_timing.get("web_verification_ms"),
        total_analysis_ms=tot_analysis or web_timing.get("total_analysis_ms"),
        number_of_tavily_searches=web_evidence.searches_used if web_evidence else 0,
        number_of_web_claims=len(web_evidence.claims) if web_evidence else 0,
        number_of_ollama_calls=None,
    )
    classification = (
        Classification(run.classification)
        if complete and run.classification in Classification._value2member_map_
        else None
    )
    score = run.hallucination_score if complete else None
    summary_payload = build_verification_summary(
        status=status,
        classification=classification,
        score=score,
        threshold=run.threshold,
        web_evidence=web_evidence,
    )
    web_status = web_evidence.status if web_evidence is not None else None
    overall = derive_overall_status(
        status,
        web_status,
        has_answer=bool((run.base_answer or "").strip()),
    )

    from app.config import get_settings
    from app.llm.registry import MODEL_REGISTRY, get_verifier_pool, resolve_model_id
    from app.schemas.detect import AnswerModelOut, VerifierModelOut
    from app.services.independent_verifiers import load_independent_verdicts

    app_settings = get_settings()
    ans_model_id = resolve_model_id(run.generator_model) or "gemma"
    model_def = MODEL_REGISTRY.get(ans_model_id, MODEL_REGISTRY["gemma"])
    answer_model_info = AnswerModelOut(
        id=model_def.id,
        name=model_def.display_name,
        provider=model_def.provider_display,
    )
    verifier_pool_info = [
        VerifierModelOut(
            id=v["id"],
            name=v["name"],
            provider=v["provider"],
            status="pending" if complete or status != RunStatus.FAILED else v["status"],
        )
        for v in get_verifier_pool(ans_model_id, app_settings)
    ]
    ai_verdicts_info = load_independent_verdicts(run, ans_model_id, app_settings)

    return DetectResponse(
        run_id=run.id,
        question=run.question,
        base_answer=BaseAnswerOut(text=run.base_answer, model=run.generator_model),
        mutation_generator_model=getattr(run, "mutation_generator_model", None) or run.generator_model,
        mutation_verifier_model=getattr(run, "mutation_verifier_model", None),
        mutations=[_mutation_out(item) for item in run.mutations] if include_mutations else [],
        # Never invent a score/classification when analysis did not complete.
        hallucination_score=score,
        threshold=run.threshold,
        classification=classification,
        not_sure_rate=run.not_sure_rate if complete else None,
        llm_mode=run.llm_mode or "live",
        status=status,
        overall_status=OverallStatus(overall.value),
        analysis_error=run.analysis_error or None,
        web_evidence=web_evidence,
        verification_summary=VerificationSummaryOut.model_validate(summary_payload),
        answer_model=answer_model_info,
        verifiers=verifier_pool_info,
        ai_verdicts=ai_verdicts_info,
        created_at=run.created_at,
        timing=timing,
    )
