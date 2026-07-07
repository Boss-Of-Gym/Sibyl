from sibyl.engineering_metrics.domain.metrics import (
    compute_ci_success_rate,
    compute_median,
)


def test_compute_median_returns_none_for_empty_list():
    assert compute_median([]) is None


def test_compute_median_single_value_is_its_own_median():
    assert compute_median([5.0]) == 5.0


def test_compute_median_odd_count_takes_the_middle_value():
    assert compute_median([3.0, 1.0, 2.0]) == 2.0


def test_compute_median_even_count_averages_the_two_middle_values():
    assert compute_median([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_compute_ci_success_rate_returns_none_for_empty_list():
    assert compute_ci_success_rate([]) is None


def test_compute_ci_success_rate_all_passing_runs_is_full_rate():
    assert compute_ci_success_rate([0, 0, 0]) == 1.0


def test_compute_ci_success_rate_mixed_runs_is_fractional():
    assert compute_ci_success_rate([0, 1, 0, 2]) == 0.5
