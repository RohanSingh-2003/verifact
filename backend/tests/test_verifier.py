from app.metaqa.scoring import Verdict
from app.metaqa.verifier import result_from_payload


def test_result_from_payload_parses_valid_verdict() -> None:
    result = result_from_payload({"verdict": "YES", "rationale": "Supported."})
    assert result.verdict is Verdict.YES
    assert result.rationale == "Supported."
    assert result.parse_failed is False


def test_result_from_payload_malformed_becomes_not_sure() -> None:
    result = result_from_payload({"verdict": "???", "rationale": "unclear"})
    assert result.verdict is Verdict.NOT_SURE
    assert result.parse_failed is True
    assert result.rationale == "unclear"


def test_result_from_payload_missing_verdict() -> None:
    result = result_from_payload({"rationale": "no label"})
    assert result.verdict is Verdict.NOT_SURE
    assert result.parse_failed is True
