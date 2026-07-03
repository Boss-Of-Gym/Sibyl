from pathlib import PurePosixPath

KNOWN_FLAKY_THRESHOLD = 0.2


def _stem(path: str) -> str:
    name = PurePosixPath(path).stem
    return name.removeprefix("test_")


def match_known_flaky_areas(
    changed_file_paths: list[str], flaky_signals: list[tuple[str, float]]
) -> list[str]:
    changed_stems = {_stem(path) for path in changed_file_paths}
    matched = set()

    for test_identifier, flakiness_score in flaky_signals:
        if flakiness_score <= KNOWN_FLAKY_THRESHOLD:
            continue
        test_file_path = test_identifier.split("::", 1)[0]
        if test_file_path in changed_file_paths or _stem(test_file_path) in changed_stems:
            matched.add(test_identifier)

    return sorted(matched)
