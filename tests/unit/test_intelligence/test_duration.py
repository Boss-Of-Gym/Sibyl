from sibyl.test_intelligence.domain.duration import compute_median_duration


def test_empty_history_has_zero_sample_size():
    median, sample_size = compute_median_duration([])
    assert median == 0.0
    assert sample_size == 0


def test_single_value_is_its_own_median():
    median, sample_size = compute_median_duration([500])
    assert median == 500.0
    assert sample_size == 1


def test_odd_count_takes_the_middle_value():
    median, sample_size = compute_median_duration([300, 100, 200])
    assert median == 200.0
    assert sample_size == 3


def test_even_count_averages_the_two_middle_values():
    median, sample_size = compute_median_duration([100, 200, 300, 400])
    assert median == 250.0
    assert sample_size == 4


def test_outlier_does_not_skew_the_median_like_it_would_an_average():
    durations = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100000]
    median, sample_size = compute_median_duration(durations)
    assert median == 100.0
    assert sample_size == 10
