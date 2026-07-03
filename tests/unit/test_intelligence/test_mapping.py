from sibyl.test_intelligence.domain.mapping import map_changed_files_to_affected_tests


def test_exact_test_file_change_is_affected():
    result = map_changed_files_to_affected_tests(
        changed_file_paths=["tests/unit/test_foo.py"],
        known_test_identifiers=["tests/unit/test_foo.py::test_a"],
    )
    assert result == ["tests/unit/test_foo.py::test_a"]


def test_source_file_maps_to_matching_test_by_stem():
    result = map_changed_files_to_affected_tests(
        changed_file_paths=["src/sibyl/pr_analysis/api.py"],
        known_test_identifiers=[
            "tests/unit/pr_analysis/test_api.py::test_ok",
            "tests/unit/ingestion/test_signature.py::test_valid",
        ],
    )
    assert result == ["tests/unit/pr_analysis/test_api.py::test_ok"]


def test_unrelated_file_matches_nothing():
    result = map_changed_files_to_affected_tests(
        changed_file_paths=["docs/README.md"],
        known_test_identifiers=["tests/unit/test_foo.py::test_a"],
    )
    assert result == []


def test_result_is_deduplicated_and_sorted():
    result = map_changed_files_to_affected_tests(
        changed_file_paths=["src/sibyl/foo.py", "src/sibyl/foo.py"],
        known_test_identifiers=[
            "tests/test_foo.py::test_b",
            "tests/test_foo.py::test_a",
        ],
    )
    assert result == ["tests/test_foo.py::test_a", "tests/test_foo.py::test_b"]


def test_no_known_tests_returns_empty():
    result = map_changed_files_to_affected_tests(
        changed_file_paths=["src/sibyl/foo.py"], known_test_identifiers=[]
    )
    assert result == []
