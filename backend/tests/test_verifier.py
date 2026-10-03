from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from app.llm.base import (
    LLMClient,
    LLMError,
    LLMMalformedResponseError,
    LLMTimeoutError,
)
from app.metaqa.detector import (
    GeneratedMutation,
    score_mutation,
)
from app.metaqa.scoring import MutationType, Verdict
from app.metaqa.verifier import VerifierResult, result_from_payload, verify_mutation


# ── Payload Parsing Tests ──────────────────────────────────────────────────


def test_result_from_payload_parses_valid_verdict_yes() -> None:
    result = result_from_payload({"verdict": "YES", "rationale": "Supported."})
    assert result.verdict is Verdict.YES
    assert result.rationale == "Supported."
    assert result.parse_failed is False
    assert result.error is None


def test_result_from_payload_parses_valid_verdict_no() -> None:
    result = result_from_payload({"verdict": "NO", "rationale": "Contradicted."})
    assert result.verdict is Verdict.NO
    assert result.rationale == "Contradicted."
    assert result.parse_failed is False
    assert result.error is None


def test_result_from_payload_parses_valid_verdict_not_sure() -> None:
    result = result_from_payload({"verdict": "NOT SURE", "rationale": "Uncertain relationship."})
    assert result.verdict is Verdict.NOT_SURE
    assert result.rationale == "Uncertain relationship."
    assert result.parse_failed is False
    assert result.error is None


def test_result_from_payload_malformed_becomes_failure() -> None:
    """Malformed or unsupported verdict must NOT be treated as genuine NOT SURE."""
    result = result_from_payload({"verdict": "???", "rationale": "unclear"})
    assert result.verdict is None
    assert result.parse_failed is True
    assert "Unsupported verdict" in (result.error or "")


def test_result_from_payload_missing_verdict_becomes_failure() -> None:
    """Missing verdict field must result in parse failure with verdict=None."""
    result = result_from_payload({"rationale": "no label"})
    assert result.verdict is None
    assert result.parse_failed is True
    assert "Payload validation error" in (result.error or "")


# ── Regression Test for Rahul Gandhi Failure Case ──────────────────────────


@pytest.mark.asyncio
async def test_rahul_gandhi_synonym_mutation_preserves_yes() -> None:
    """Regression test for the inspection report bug:

    Rahul Gandhi synonym mutation was truncated and converted into NOT SURE.
    With proper token allocation and JSON parsing, a valid Gemini YES remains YES,
    does NOT become NOT SURE, and parse_failed is False.
    """
    question = "who is rahul gandhi ?"
    answer = (
        "Rahul Gandhi is a prominent Indian politician and a senior leader of the Indian "
        "National Congress (INC), one of the country's major political parties."
    )
    statement = "Rahul Gandhi holds a high-ranking leadership position within the Indian National Congress."

    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.complete_json.return_value = {
        "verdict": "YES",
        "rationale": "Candidate answer states he is a senior leader of the party.",
    }

    result = await verify_mutation(
        mock_llm,
        model="gemini-3.8-flash",
        question=question,
        answer=answer,
        statement=statement,
        max_tokens=256,
    )

    assert result.verdict is Verdict.YES
    assert result.parse_failed is False
    assert result.error is None
    assert "senior leader" in result.rationale

    mutation = GeneratedMutation(
        type=MutationType.SYNONYM,
        original_text="Rahul Gandhi is a senior leader of the Indian National Congress.",
        mutated_text=statement,
    )
    scored = score_mutation(mutation, result)
    assert scored.verdict is Verdict.YES
    assert scored.contribution == 0.0  # Synonym with observed YES -> consistent (0.0)
    assert scored.unavailable is False
    assert scored.parse_failed is False


# ── Requirement 16: Failure Separation Tests (A - J) ───────────────────────


@pytest.mark.asyncio
async def test_requirement_16_a_gemini_returns_yes() -> None:
    """A. Gemini returns valid YES -> valid YES."""
    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.complete_json.return_value = {"verdict": "YES", "rationale": "Preserves meaning."}

    result = await verify_mutation(
        mock_llm,
        model="gemini-3.8-flash",
        question="Q",
        answer="A",
        statement="S",
        max_tokens=256,
    )
    assert result.verdict is Verdict.YES
    assert result.parse_failed is False


@pytest.mark.asyncio
async def test_requirement_16_b_gemini_returns_no() -> None:
    """B. Gemini returns valid NO -> valid NO."""
    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.complete_json.return_value = {"verdict": "NO", "rationale": "Contradicts answer."}

    result = await verify_mutation(
        mock_llm,
        model="gemini-3.8-flash",
        question="Q",
        answer="A",
        statement="S",
        max_tokens=256,
    )
    assert result.verdict is Verdict.NO
    assert result.parse_failed is False


@pytest.mark.asyncio
async def test_requirement_16_c_gemini_returns_not_sure() -> None:
    """C. Gemini returns genuine NOT SURE -> valid NOT SURE."""
    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.complete_json.return_value = {"verdict": "NOT SURE", "rationale": "Cannot determine."}

    result = await verify_mutation(
        mock_llm,
        model="gemini-3.8-flash",
        question="Q",
        answer="A",
        statement="S",
        max_tokens=256,
    )
    assert result.verdict is Verdict.NOT_SURE
    assert result.parse_failed is False


@pytest.mark.asyncio
async def test_requirement_16_d_gemini_returns_malformed_json() -> None:
    """D. Gemini returns malformed JSON -> verification error, NOT NOT SURE."""
    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.complete_json.side_effect = LLMMalformedResponseError("Malformed JSON.")

    result = await verify_mutation(
        mock_llm,
        model="gemini-3.8-flash",
        question="Q",
        answer="A",
        statement="S",
        max_tokens=256,
    )
    assert result.verdict is None
    assert result.parse_failed is True
    assert result.error == "Malformed JSON"


@pytest.mark.asyncio
async def test_requirement_16_e_gemini_response_is_truncated() -> None:
    """E. Gemini response is truncated -> verification error, NOT NOT SURE."""
    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.complete_json.side_effect = LLMMalformedResponseError("Truncated JSON '{\"verdict'.")

    result = await verify_mutation(
        mock_llm,
        model="gemini-3.8-flash",
        question="Q",
        answer="A",
        statement="S",
        max_tokens=256,
    )
    assert result.verdict is None
    assert result.parse_failed is True
    assert result.error == "Malformed JSON"


@pytest.mark.asyncio
async def test_requirement_16_f_gemini_times_out() -> None:
    """F. Gemini times out -> verification error."""
    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.complete_json.side_effect = LLMTimeoutError("Request timed out.")

    result = await verify_mutation(
        mock_llm,
        model="gemini-3.8-flash",
        question="Q",
        answer="A",
        statement="S",
        max_tokens=256,
    )
    assert result.verdict is None
    assert result.parse_failed is True
    assert result.error == "Timeout"


@pytest.mark.asyncio
async def test_requirement_16_g_gemini_api_auth_error() -> None:
    """G. Gemini returns authentication error -> verification error."""
    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.complete_json.side_effect = LLMError("Gemini API key is invalid or unauthorized.")

    result = await verify_mutation(
        mock_llm,
        model="gemini-3.8-flash",
        question="Q",
        answer="A",
        statement="S",
        max_tokens=256,
    )
    assert result.verdict is None
    assert result.parse_failed is True
    assert "unauthorized" in (result.error or "")


def test_requirement_16_h_gemini_returns_json_in_markdown_fences() -> None:
    """H. Gemini returns JSON inside markdown fences -> parse successfully."""
    from app.llm.client import parse_json_object

    fenced = "```json\n{\n  \"verdict\": \"YES\",\n  \"rationale\": \"Equivalent claim.\"\n}\n```"
    parsed = parse_json_object(fenced)
    assert parsed is not None
    assert parsed["verdict"] == "YES"
    result = result_from_payload(parsed)
    assert result.verdict is Verdict.YES
    assert result.parse_failed is False


def test_requirement_16_i_gemini_returns_unsupported_verdict() -> None:
    """I. Gemini returns an unsupported verdict (e.g. 'MAYBE') -> verification error, not NOT SURE."""
    result = result_from_payload({"verdict": "MAYBE", "rationale": "Could be true."})
    assert result.verdict is None
    assert result.parse_failed is True
    assert "Unsupported verdict" in (result.error or "")


def test_requirement_16_j_technical_failures_never_contribute_half_to_score() -> None:
    """J. Technical failures never contribute 0.5 to the MetaQA score."""
    mutation = GeneratedMutation(
        type=MutationType.SYNONYM,
        original_text="Core claim.",
        mutated_text="Mutated claim.",
    )

    # 1. Technical failure with verdict=None
    fail_result = VerifierResult(
        verdict=None,
        rationale="Gemini returned an incomplete response.",
        parse_failed=True,
        error="Malformed JSON",
    )
    scored = score_mutation(mutation, fail_result, unavailable=True)
    assert scored.unavailable is True
    assert scored.parse_failed is True
    # Crucial assertion: contribution must be 0.0 (excluded), NEVER 0.5
    assert scored.contribution == 0.0

    # 2. Genuine NOT SURE contributes 0.5
    genuine_not_sure = VerifierResult(
        verdict=Verdict.NOT_SURE,
        rationale="Uncertain relationship.",
        parse_failed=False,
    )
    scored_not_sure = score_mutation(mutation, genuine_not_sure, unavailable=False)
    assert scored_not_sure.unavailable is False
    assert scored_not_sure.parse_failed is False
    assert scored_not_sure.contribution == 0.5
