from sibyl.release_risk_analysis.domain.scoring import (
    compute_average_coverage_pct,
    compute_ci_success_rate,
    compute_release_risk_score,
)


def test_compute_ci_success_rate_returns_none_for_empty_list():
    assert compute_ci_success_rate([]) is None


def test_compute_ci_success_rate_all_passing_runs_is_full_rate():
    assert compute_ci_success_rate([0, 0, 0]) == 1.0


def test_compute_ci_success_rate_mixed_runs_is_fractional():
    assert compute_ci_success_rate([0, 1, 0, 2]) == 0.5


def test_compute_average_coverage_pct_returns_none_for_empty_list():
    assert compute_average_coverage_pct([]) is None


def test_compute_average_coverage_pct_averages_fractions():
    result = compute_average_coverage_pct([0.8, 0.4])
    assert result is not None
    assert round(result, 10) == 0.6


def test_compute_release_risk_score_with_no_signals_is_zero_and_empty():
    score, considered = compute_release_risk_score(None, None, None)
    assert score == 0.0
    assert considered == []


def test_compute_release_risk_score_uses_only_available_signals():
    score, considered = compute_release_risk_score(0.8, None, None)
    assert score == 0.8
    assert considered == ["regression_probability"]


def test_compute_release_risk_score_averages_all_three_risk_contributions():
    score, considered = compute_release_risk_score(
        regression_probability=0.6, ci_success_rate=0.8, coverage_pct=0.5
    )
    assert considered == ["regression_probability", "ci_success_rate", "coverage_pct"]
    assert round(score, 4) == round((0.6 + 0.2 + 0.5) / 3, 4)


def test_compute_release_risk_score_poor_ci_and_coverage_raise_score_despite_low_regression():
    score, _ = compute_release_risk_score(
        regression_probability=0.1, ci_success_rate=0.2, coverage_pct=0.1
    )
    assert score > 0.1
