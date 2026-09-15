from app.experiment.stats import paired_t_test, summarize_scores, wilcoxon_signed_rank


def test_summarize_scores_and_ci() -> None:
    summary = summarize_scores([0.0, 0.5, 1.0])
    assert summary.n == 3
    assert summary.mean == 0.5
    assert summary.median == 0.5
    assert summary.ci95_low is not None
    assert summary.ci95_high is not None
    assert summary.ci95_low < summary.mean < summary.ci95_high


def test_wilcoxon_all_negative_differences() -> None:
    result = wilcoxon_signed_rank([-0.3] * 12)
    assert result.n == 12
    assert result.statistic == 0
    assert result.p_value is not None
    assert result.p_value < 0.05


def test_wilcoxon_drops_zeros() -> None:
    result = wilcoxon_signed_rank([0.0, 0.0, 0.2, -0.1])
    assert result.n == 2


def test_wilcoxon_empty() -> None:
    result = wilcoxon_signed_rank([0.0, 0.0])
    assert result.n == 0
    assert result.p_value is None


def test_paired_t_test() -> None:
    result = paired_t_test([-1.0] * 10)
    assert result.n == 10
    assert result.p_value is not None
    assert result.p_value < 0.05
