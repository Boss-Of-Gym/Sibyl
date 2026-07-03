from sibyl.test_intelligence.domain.coverage import compute_coverage_pct


def test_partial_coverage():
    assert compute_coverage_pct(8, 10) == 0.8


def test_full_coverage():
    assert compute_coverage_pct(10, 10) == 1.0


def test_zero_coverage():
    assert compute_coverage_pct(0, 10) == 0.0


def test_zero_total_lines_does_not_divide_by_zero():
    assert compute_coverage_pct(0, 0) == 0.0
