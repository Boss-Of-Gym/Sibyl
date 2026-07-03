from sibyl.test_intelligence.domain.flakiness import compute_flakiness, is_material_change


def test_all_passing_is_not_flaky():
    score, sample_size = compute_flakiness(["passed"] * 10)
    assert score == 0.0
    assert sample_size == 10


def test_all_failing_is_not_flaky_it_is_a_regression():
    score, sample_size = compute_flakiness(["failed"] * 10)
    assert score == 0.0
    assert sample_size == 10


def test_even_split_is_maximally_flaky():
    score, sample_size = compute_flakiness(["passed", "failed"] * 5)
    assert score == 1.0
    assert sample_size == 10


def test_one_failure_in_twenty_is_low_flakiness_not_a_regression():
    statuses = ["passed"] * 19 + ["failed"]
    score, sample_size = compute_flakiness(statuses)
    assert score == 0.1
    assert sample_size == 20


def test_skipped_results_are_excluded_from_sample():
    score, sample_size = compute_flakiness(["passed", "skipped", "skipped", "failed"])
    assert sample_size == 2
    assert score == 1.0


def test_empty_history_has_zero_sample_size():
    score, sample_size = compute_flakiness([])
    assert score == 0.0
    assert sample_size == 0


def test_only_skipped_has_zero_sample_size():
    score, sample_size = compute_flakiness(["skipped", "skipped"])
    assert sample_size == 0


def test_first_computation_is_always_a_material_change():
    assert is_material_change(None, 0.0) is True


def test_small_delta_is_not_material():
    assert is_material_change(0.20, 0.22) is False


def test_large_delta_is_material():
    assert is_material_change(0.20, 0.80) is True
