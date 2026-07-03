from sibyl.dependency_analysis.domain.diffing import classify_version_change, diff_packages


def test_major_version_bump_is_breaking():
    assert classify_version_change("1.2.3", "2.0.0") == "breaking"


def test_minor_version_bump_is_non_breaking():
    assert classify_version_change("1.2.3", "1.3.0") == "non_breaking"


def test_patch_version_bump_is_non_breaking():
    assert classify_version_change("1.2.3", "1.2.4") == "non_breaking"


def test_unparseable_version_is_unknown():
    assert classify_version_change("main", "2.0.0") == "unknown"
    assert classify_version_change("1.2.3", "latest") == "unknown"


def test_v_prefixed_versions_are_parsed():
    assert classify_version_change("v1.0.0", "v2.0.0") == "breaking"


def test_diff_detects_added_package():
    changes = diff_packages(
        old_packages=[],
        new_packages=[{"name": "left-pad", "version": "1.0.0", "direct": True}],
    )

    assert len(changes) == 1
    assert changes[0].name == "left-pad"
    assert changes[0].change_type == "added"
    assert changes[0].severity == "non_breaking"


def test_diff_detects_removed_package_as_breaking():
    changes = diff_packages(
        old_packages=[{"name": "left-pad", "version": "1.0.0", "direct": True}],
        new_packages=[],
    )

    assert len(changes) == 1
    assert changes[0].change_type == "removed"
    assert changes[0].severity == "breaking"


def test_diff_detects_version_change():
    changes = diff_packages(
        old_packages=[{"name": "left-pad", "version": "1.0.0", "direct": True}],
        new_packages=[{"name": "left-pad", "version": "2.0.0", "direct": True}],
    )

    assert len(changes) == 1
    assert changes[0].change_type == "version_changed"
    assert changes[0].old_version == "1.0.0"
    assert changes[0].new_version == "2.0.0"
    assert changes[0].severity == "breaking"


def test_diff_ignores_unchanged_packages():
    changes = diff_packages(
        old_packages=[{"name": "left-pad", "version": "1.0.0", "direct": True}],
        new_packages=[{"name": "left-pad", "version": "1.0.0", "direct": True}],
    )

    assert changes == []


def test_diff_results_are_sorted_by_name():
    changes = diff_packages(
        old_packages=[],
        new_packages=[
            {"name": "z-package", "version": "1.0.0", "direct": True},
            {"name": "a-package", "version": "1.0.0", "direct": True},
        ],
    )

    assert [change.name for change in changes] == ["a-package", "z-package"]
