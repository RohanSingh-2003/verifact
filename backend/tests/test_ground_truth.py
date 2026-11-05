from app.evaluation.ground_truth import answers_equivalent, match_reference, resolve_ground_truth

from app.evaluation.schemas import DatasetExample

from app.evaluation.schemas import GroundTruthSource

from app.metaqa.scoring import Classification





def _example(**overrides: object) -> DatasetExample:

    payload = {

        "id": "q001",

        "question": "What is the capital of Australia?",

        "reference_answer": "Canberra",

        "category": "location",

        "source": "curated",

    }

    payload.update(overrides)

    return DatasetExample.model_validate(payload)





def test_paraphrase_matches_reference() -> None:

    assert answers_equivalent("The capital of Australia is Canberra.", "Canberra")

    assert match_reference("The capital of Australia is Canberra.", _example()) is True





def test_wrong_answer_is_hallucinated() -> None:

    decision = resolve_ground_truth("Sydney is the capital.", _example(), mode="legacy")

    assert decision.label is Classification.HALLUCINATED

    assert decision.source is GroundTruthSource.REFERENCE_MATCH





def test_correct_answer_is_reliable() -> None:

    decision = resolve_ground_truth("Canberra", _example(), mode="legacy")

    assert decision.label is Classification.RELIABLE





def test_alias_match() -> None:

    example = _example(aliases=["Canberra, Australia"])

    assert match_reference("Canberra, Australia is the capital.", example) is True





def test_numeric_token_does_not_match_inside_larger_number() -> None:

    example = _example(reference_answer="6", question="atomic number?", category="numeric")

    assert match_reference("The atomic number is 12.", example) is False

    assert match_reference("The atomic number is 6.", example) is True





def test_uncertain_generated_answer_needs_review() -> None:

    decision = resolve_ground_truth("I don't know", _example(), mode="legacy")

    assert decision.is_review

    assert decision.source is GroundTruthSource.NEEDS_REVIEW





def test_needs_review_flag_excluded() -> None:

    decision = resolve_ground_truth("Canberra", _example(needs_review=True))

    assert decision.is_review





def test_manual_label_overrides_matching() -> None:

    example = _example(ground_truth_label="Hallucinated")

    decision = resolve_ground_truth("Canberra", example)

    assert decision.label is Classification.HALLUCINATED

    assert decision.source is GroundTruthSource.MANUAL





def test_adjudicated_label_takes_precedence_over_dataset_label_and_matching() -> None:

    example = _example(ground_truth_label="Hallucinated")

    decision = resolve_ground_truth("Canberra", example, adjudicated_label="Reliable", mode="formal")

    assert decision.label is Classification.RELIABLE

    assert decision.source is GroundTruthSource.ADJUDICATED





def test_missing_ground_truth_in_formal_mode_remains_unvalidated_without_guessing() -> None:

    example = _example(ground_truth_label=None)

    decision = resolve_ground_truth("Canberra", example, mode="formal")

    assert decision.label is None

    assert decision.source is GroundTruthSource.UNVALIDATED

    assert decision.is_review is True





def test_definitive_adjudicated_label_overrides_stale_needs_review_flag() -> None:

    example = _example(needs_review=True, ground_truth_label="Hallucinated")

    decision = resolve_ground_truth("Canberra", example, adjudicated_label="Reliable")

    assert decision.is_review is False

    assert decision.label is Classification.RELIABLE

    assert decision.source is GroundTruthSource.ADJUDICATED





def test_ambiguous_adjudication_or_unadjudicated_retains_needs_review() -> None:

    example = _example(needs_review=True)

    d1 = resolve_ground_truth("Canberra", example)

    assert d1.is_review is True

    assert d1.label is None

    assert d1.source is GroundTruthSource.NEEDS_REVIEW



    d2 = resolve_ground_truth("Canberra", example, adjudicated_label="Needs Review")

    assert d2.is_review is True

    assert d2.label is None

    assert d2.source is GroundTruthSource.NEEDS_REVIEW



def test_definitive_adjudicated_example_provenance_preserved_and_overrides_needs_review() -> None:
    """An example marked ADJUDICATED in dataset overrides stale needs_review=True and keeps ADJUDICATED provenance."""
    example = _example(
        needs_review=True,
        ground_truth_label="Reliable",
        ground_truth_source="Adjudicated",
    )
    decision = resolve_ground_truth("Canberra", example, mode="formal")
    assert decision.is_review is False
    assert decision.label is Classification.RELIABLE
    assert decision.source is GroundTruthSource.ADJUDICATED
    assert decision.source != GroundTruthSource.MANUAL


def test_ambiguous_adjudication_labels_remain_excluded() -> None:
    """Ambiguous or non-binary adjudication values ('Ambiguous', 'Uncertain') remain excluded as NEEDS_REVIEW."""
    for ambig in ("Ambiguous", "Uncertain", "Needs Review", "Unresolvable"):
        example = _example(needs_review=False)
        decision = resolve_ground_truth("Canberra", example, adjudicated_label=ambig)
        assert decision.is_review is True
        assert decision.label is None
        assert decision.source is GroundTruthSource.NEEDS_REVIEW

    # Unadjudicated unvalidated example in formal mode remains UNVALIDATED
    decision_none = resolve_ground_truth("Canberra", _example(needs_review=False), adjudicated_label=None, mode="formal")
    assert decision_none.is_review is True
    assert decision_none.label is None
    assert decision_none.source is GroundTruthSource.UNVALIDATED


def test_unvalidated_records_cannot_receive_inferred_labels_in_formal_mode() -> None:
    """In formal mode, even an exact string match cannot grant a label to an unvalidated record."""
    example = _example(ground_truth_label=None, reference_answer="Canberra")
    # Even when generated answer is an exact match to reference
    decision = resolve_ground_truth("Canberra", example, mode="formal")
    assert decision.label is None
    assert decision.source is GroundTruthSource.UNVALIDATED
    assert decision.is_review is True


def test_gemini_outputs_cannot_override_human_labels() -> None:
    """Ground truth resolution strictly consults human adjudication and explicit gold labels, ignoring AI judges."""
    example = _example(
        ground_truth_label="Reliable",
        ground_truth_source="Adjudicated",
    )
    # Even if an external AI judge hallucination output was produced
    decision = resolve_ground_truth("Canberra", example, mode="formal")
    assert decision.label is Classification.RELIABLE
    assert decision.source is GroundTruthSource.ADJUDICATED
