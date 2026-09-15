from app.metaqa.detector import score_mutation
from app.metaqa.mutation import GeneratedMutation
from app.metaqa.scoring import (
    Classification,
    MutationType,
    Verdict,
    aggregate_score,
    classify,
    contribution_score,
    expected_verdict,
    not_sure_rate,
)
from app.metaqa.verifier import VerifierResult


def test_synonym_scoring_table() -> None:
    assert contribution_score(MutationType.SYNONYM, Verdict.YES) == 0.0
    assert contribution_score(MutationType.SYNONYM, Verdict.NO) == 1.0
    assert contribution_score(MutationType.SYNONYM, Verdict.NOT_SURE) == 0.5


def test_antonym_scoring_table() -> None:
    assert contribution_score(MutationType.ANTONYM, Verdict.YES) == 1.0
    assert contribution_score(MutationType.ANTONYM, Verdict.NO) == 0.0
    assert contribution_score(MutationType.ANTONYM, Verdict.NOT_SURE) == 0.5


def test_expected_verdict_is_derived_from_type() -> None:
    assert expected_verdict(MutationType.SYNONYM) is Verdict.YES
    assert expected_verdict(MutationType.ANTONYM) is Verdict.NO


def test_final_score_aggregation() -> None:
    score = aggregate_score([0.0, 1.0, 0.5, 0.0, 1.0, 1.0, 0.0, 0.5, 1.0, 0.0])
    assert score == 0.5
    assert 0.0 <= score <= 1.0


def test_aggregate_score_stays_in_unit_interval() -> None:
    assert aggregate_score([0.0] * 10) == 0.0
    assert aggregate_score([1.0] * 10) == 1.0
    assert aggregate_score([2.0, 2.0]) == 1.0
    assert aggregate_score([-1.0, 0.0]) == 0.0


def test_case_d_mixed_average() -> None:
    # Synonym: YES, YES, NO, NOT SURE, YES → 0 + 0 + 1 + 0.5 + 0 = 1.5
    # Antonym: NO, YES, NO, NOT SURE, NO → 0 + 1 + 0 + 0.5 + 0 = 1.5
    synonym = [
        contribution_score(MutationType.SYNONYM, Verdict.YES),
        contribution_score(MutationType.SYNONYM, Verdict.YES),
        contribution_score(MutationType.SYNONYM, Verdict.NO),
        contribution_score(MutationType.SYNONYM, Verdict.NOT_SURE),
        contribution_score(MutationType.SYNONYM, Verdict.YES),
    ]
    antonym = [
        contribution_score(MutationType.ANTONYM, Verdict.NO),
        contribution_score(MutationType.ANTONYM, Verdict.YES),
        contribution_score(MutationType.ANTONYM, Verdict.NO),
        contribution_score(MutationType.ANTONYM, Verdict.NOT_SURE),
        contribution_score(MutationType.ANTONYM, Verdict.NO),
    ]
    assert synonym == [0.0, 0.0, 1.0, 0.5, 0.0]
    assert antonym == [0.0, 1.0, 0.0, 0.5, 0.0]
    score = aggregate_score(synonym + antonym)
    assert score == 0.3
    assert classify(score, 0.5) is Classification.RELIABLE


def test_threshold_classification_boundary() -> None:
    assert classify(0.5, 0.5) is Classification.HALLUCINATED
    assert classify(0.72, 0.5) is Classification.HALLUCINATED
    assert classify(0.4999, 0.5) is Classification.RELIABLE
    assert classify(0.0, 0.5) is Classification.RELIABLE
    assert classify(0.0, 0.0) is Classification.HALLUCINATED
    assert classify(0.99, 1.0) is Classification.RELIABLE
    assert classify(1.0, 1.0) is Classification.HALLUCINATED


def test_not_sure_rate() -> None:
    rate = not_sure_rate(
        [
            Verdict.YES,
            Verdict.NO,
            Verdict.NOT_SURE,
            Verdict.YES,
            Verdict.NO,
            Verdict.YES,
            Verdict.NO,
            Verdict.YES,
            Verdict.NO,
            Verdict.NOT_SURE,
        ]
    )
    assert rate == 0.2


def test_not_sure_rate_all_uncertain() -> None:
    assert not_sure_rate([Verdict.NOT_SURE] * 10) == 1.0


def test_rationale_does_not_change_score() -> None:
    mutation = GeneratedMutation(
        type=MutationType.SYNONYM,
        original_text="Sydney is the capital of Australia.",
        mutated_text="Australia's capital city is Sydney.",
    )
    first = score_mutation(mutation, VerifierResult(verdict=Verdict.NO, rationale="First explanation."))
    second = score_mutation(
        mutation,
        VerifierResult(verdict=Verdict.NO, rationale="A completely different explanation."),
    )
    assert first.contribution == second.contribution == 1.0
    assert first.verdict is second.verdict is Verdict.NO


def test_ten_mutations_all_consistent_yields_zero_score() -> None:
    """10 mutations with all expected verifier behavior (synonym YES, antonym NO) must score 0.0."""
    synonym_contributions = [contribution_score(MutationType.SYNONYM, Verdict.YES)] * 5
    antonym_contributions = [contribution_score(MutationType.ANTONYM, Verdict.NO)] * 5
    score = aggregate_score(synonym_contributions + antonym_contributions)
    assert score == 0.0
    assert classify(score, 0.5) is Classification.RELIABLE


def test_ten_mutations_all_inconsistent_yields_one_score() -> None:
    """10 mutations with all inconsistent verifier behavior (synonym NO, antonym YES) must score 1.0."""
    synonym_contributions = [contribution_score(MutationType.SYNONYM, Verdict.NO)] * 5
    antonym_contributions = [contribution_score(MutationType.ANTONYM, Verdict.YES)] * 5
    score = aggregate_score(synonym_contributions + antonym_contributions)
    assert score == 1.0
    assert classify(score, 0.5) is Classification.HALLUCINATED


def test_direct_score_engine_without_llm() -> None:
    """Direct verification of score engine with 5 synonym YES and 5 antonym NO."""
    mutations = [
        {"type": MutationType.SYNONYM, "verdict": Verdict.YES},
        {"type": MutationType.SYNONYM, "verdict": Verdict.YES},
        {"type": MutationType.SYNONYM, "verdict": Verdict.YES},
        {"type": MutationType.SYNONYM, "verdict": Verdict.YES},
        {"type": MutationType.SYNONYM, "verdict": Verdict.YES},
        {"type": MutationType.ANTONYM, "verdict": Verdict.NO},
        {"type": MutationType.ANTONYM, "verdict": Verdict.NO},
        {"type": MutationType.ANTONYM, "verdict": Verdict.NO},
        {"type": MutationType.ANTONYM, "verdict": Verdict.NO},
        {"type": MutationType.ANTONYM, "verdict": Verdict.NO},
    ]
    contributions = [contribution_score(m["type"], m["verdict"]) for m in mutations]
    assert contributions == [0.0] * 10
    score = aggregate_score(contributions)
    assert score == 0.0
    assert classify(score, 0.5) is Classification.RELIABLE
