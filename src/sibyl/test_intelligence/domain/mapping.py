from pathlib import PurePosixPath


def _stem(path: str) -> str:
    name = PurePosixPath(path).stem
    return name.removeprefix("test_")


def map_changed_files_to_affected_tests(
    changed_file_paths: list[str], known_test_identifiers: list[str]
) -> list[str]:
    changed_stems = {_stem(path) for path in changed_file_paths}
    affected = set()

    for changed_path in changed_file_paths:
        for test_identifier in known_test_identifiers:
            test_file_path = test_identifier.split("::", 1)[0]
            if test_file_path == changed_path:
                affected.add(test_identifier)

    for test_identifier in known_test_identifiers:
        test_file_path = test_identifier.split("::", 1)[0]
        if _stem(test_file_path) in changed_stems:
            affected.add(test_identifier)

    return sorted(affected)
