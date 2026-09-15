from app.metaqa.scoring import Verdict, parse_verdict


def test_parse_exact_labels() -> None:
    assert parse_verdict("YES") == (Verdict.YES, False)
    assert parse_verdict("NO") == (Verdict.NO, False)
    assert parse_verdict("NOT SURE") == (Verdict.NOT_SURE, False)


def test_parse_harmless_formatting_variants() -> None:
    assert parse_verdict("yes") == (Verdict.YES, False)
    assert parse_verdict("YES.") == (Verdict.YES, False)
    assert parse_verdict(" Verdict: YES ") == (Verdict.YES, False)
    assert parse_verdict("\"NO\"") == (Verdict.NO, False)
    assert parse_verdict("Answer: NOT SURE") == (Verdict.NOT_SURE, False)


def test_parse_embedded_text_prefers_not_sure() -> None:
    verdict, fallback = parse_verdict("I am NOT SURE about this claim.")
    assert verdict is Verdict.NOT_SURE
    assert fallback is False


def test_parse_json_style_yes() -> None:
    verdict, fallback = parse_verdict("The verdict is YES.")
    assert verdict is Verdict.YES
    assert fallback is False


def test_invalid_verdict_becomes_not_sure() -> None:
    verdict, fallback = parse_verdict("maybe tomorrow")
    assert verdict is Verdict.NOT_SURE
    assert fallback is True


def test_empty_verdict_becomes_not_sure() -> None:
    verdict, fallback = parse_verdict("   ")
    assert verdict is Verdict.NOT_SURE
    assert fallback is True


def test_ambiguous_yes_and_no_is_not_guessed() -> None:
    verdict, fallback = parse_verdict("YES or NO depending on context")
    assert verdict is Verdict.NOT_SURE
    assert fallback is True
