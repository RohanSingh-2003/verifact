from app.experiment.analysis import (
    category_analysis,
    key_finding_text,
    paired_rows,
    research_summary,
    self_verification_block,
    summarize_condition,
)
from app.metaqa.scoring import Classification


def test_self_verification_difference() -> None:
    same = [
        {"question_id": "q1", "question": "Q1", "generator_model": "model-a", "hallucination_score": 0.2, "classification": "Reliable"},
        {"question_id": "q2", "question": "Q2", "generator_model": "model-a", "hallucination_score": 0.1, "classification": "Reliable"},
    ]
    cross = [
        {"question_id": "q1", "question": "Q1", "generator_model": "model-a", "hallucination_score": 0.8, "classification": "Hallucinated"},
        {"question_id": "q2", "question": "Q2", "generator_model": "model-a", "hallucination_score": 0.9, "classification": "Hallucinated"},
    ]
    paired = paired_rows(same, cross)
    assert [item["difference"] for item in paired] == [-0.6, -0.8]
    block = self_verification_block(paired, "model-a")
    assert block["self_verification_score_difference"] == -0.7
    assert block["mean_paired_difference"] == -0.7
    assert block["median_paired_difference"] == -0.7
    assert block["classification_flip_rate"] == 1.0
    assert block["flip_count"] == 2


def test_four_condition_aggregation() -> None:
    summary = summarize_condition(
        generator_model="model-a",
        verifier_model="model-b",
        scores=[1.0, 1.0],
        classifications=["Hallucinated", "Hallucinated"],
        not_sure_rates=[0.0, 0.0],
        actuals=[Classification.HALLUCINATED, Classification.RELIABLE],
        labeled_classifications=["Hallucinated", "Hallucinated"],
    )
    assert summary.pair_type == "cross"
    assert summary.mean_score == 1.0
    assert summary.hallucinated_count == 2
    assert summary.precision == 0.5


def test_key_finding_is_dynamic() -> None:
    significant = {
        "generator_model": "model-a",
        "self_verification_score_difference": -0.4,
        "significant": True,
        "exploratory": False,
        "wilcoxon": {"p_value": 0.001},
    }
    none = {
        "generator_model": "model-b",
        "self_verification_score_difference": 0.01,
        "significant": False,
        "exploratory": False,
        "wilcoxon": {"p_value": 0.8},
    }
    text = key_finding_text([significant, none], demo=True, dataset="pilot")
    assert text.startswith("DEMO / MOCK DATA")
    assert "lower hallucination scores" in text
    assert "no statistically significant difference" in text
    assert "hardcoded" not in text.lower()


def test_key_finding_does_not_claim_significance_when_exploratory() -> None:
    block = {
        "generator_model": "model-a",
        "self_verification_score_difference": -0.4,
        "significant": False,
        "exploratory": True,
        "wilcoxon": {"p_value": 0.001},
    }
    text = key_finding_text([block], demo=False, dataset="mini")
    assert "statistically significant" not in text
    assert "exploratory" in text
    assert "lower hallucination scores" in text


def test_paired_rows_match_on_question_and_trial() -> None:
    same = [
        {"question_id": "q1", "question": "Q1", "generator_model": "model-a", "trial_num": 1, "hallucination_score": 0.2, "classification": "Reliable"},
        {"question_id": "q1", "question": "Q1", "generator_model": "model-a", "trial_num": 2, "hallucination_score": 0.3, "classification": "Reliable"},
    ]
    cross = [
        {"question_id": "q1", "question": "Q1", "generator_model": "model-a", "trial_num": 2, "hallucination_score": 0.9, "classification": "Hallucinated"},
        {"question_id": "q1", "question": "Q1", "generator_model": "model-a", "trial_num": 1, "hallucination_score": 0.8, "classification": "Hallucinated"},
    ]
    paired = paired_rows(same, cross)
    by_trial = {item["trial_num"]: item for item in paired}
    assert by_trial[1]["difference"] == -0.6
    assert by_trial[2]["difference"] == -0.6


def test_research_summary_uses_computed_numbers() -> None:
    paired = paired_rows(
        [{"question_id": "q1", "question": "Q1", "generator_model": "model-a", "hallucination_score": 0.2, "classification": "Reliable"}],
        [{"question_id": "q1", "question": "Q1", "generator_model": "model-a", "hallucination_score": 0.8, "classification": "Hallucinated"}],
    )
    block = self_verification_block(paired, "model-a")
    summary = research_summary(
        blocks=[block],
        condition_summaries=[
            {
                "label": "A → A",
                "generator_model": "model-a",
                "verifier_model": "model-a",
                "pair_type": "same",
                "n": 1,
                "mean_score": 0.2,
            }
        ],
        question_count=1,
        classification_flip_rate=1.0,
        demo=True,
        dataset="mini",
    )
    assert summary["sample_size"] == 1
    assert summary["generators"][0]["score_difference"] == -0.6
    assert summary["demo_data"] is True
    assert "DEMO" in summary["narrative"]


def test_category_analysis_flags_insufficient_samples() -> None:
    paired = [
        {
            "question_id": "q1",
            "generator_model": "model-a",
            "same_model_score": 0.2,
            "cross_model_score": 0.8,
            "classification_flip": True,
        }
    ]
    rows = [{"question_id": "q1", "category": "location"}]
    result = category_analysis(paired, rows)
    assert result[0]["n"] == 1
    assert result[0]["insufficient_data"] is True
    assert "insufficient" in result[0]["note"]
