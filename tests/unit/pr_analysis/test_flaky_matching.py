from sibyl.pr_analysis.domain.flaky_matching import match_known_flaky_areas


def test_matches_flaky_test_for_exactly_changed_file():
    result = match_known_flaky_areas(
        changed_file_paths=["tests/test_checkout.py"],
        flaky_signals=[("tests/test_checkout.py::test_applies_discount", 0.5)],
    )

    assert result == ["tests/test_checkout.py::test_applies_discount"]


def test_matches_via_stem_when_source_file_changed_not_the_test_file():
    result = match_known_flaky_areas(
        changed_file_paths=["src/checkout.py"],
        flaky_signals=[("tests/test_checkout.py::test_applies_discount", 0.5)],
    )

    assert result == ["tests/test_checkout.py::test_applies_discount"]


def test_excludes_signals_at_or_below_the_threshold():
    result = match_known_flaky_areas(
        changed_file_paths=["src/checkout.py"],
        flaky_signals=[("tests/test_checkout.py::test_applies_discount", 0.2)],
    )

    assert result == []


def test_excludes_flaky_tests_unrelated_to_any_changed_file():
    result = match_known_flaky_areas(
        changed_file_paths=["src/unrelated.py"],
        flaky_signals=[("tests/test_checkout.py::test_applies_discount", 0.9)],
    )

    assert result == []


def test_result_is_sorted_and_deduplicated():
    result = match_known_flaky_areas(
        changed_file_paths=["src/checkout.py"],
        flaky_signals=[
            ("tests/test_checkout.py::test_b", 0.9),
            ("tests/test_checkout.py::test_a", 0.9),
            ("tests/test_checkout.py::test_a", 0.9),
        ],
    )

    assert result == ["tests/test_checkout.py::test_a", "tests/test_checkout.py::test_b"]
