import pytest

from sibyl.pr_analysis.application import MalformedPrChangedPayload, _extract_context

VALID_PAYLOAD = {
    "number": 42,
    "repository": {"full_name": "acme/widgets"},
    "pull_request": {
        "head": {"sha": "abc123"},
        "base": {"sha": "def456"},
        "user": {"login": "octocat"},
        "changed_files": 3,
        "additions": 50,
        "deletions": 10,
    },
    "files": [{"filename": "src/widgets/core.py"}, {"filename": "tests/test_core.py"}],
}


def test_extracts_all_fields_from_a_well_formed_payload():
    context = _extract_context(VALID_PAYLOAD)

    assert context.repository == "acme/widgets"
    assert context.pr_number == 42
    assert context.head_sha == "abc123"
    assert context.base_sha == "def456"
    assert context.author_login == "octocat"
    assert context.files_changed == 3
    assert context.additions == 50
    assert context.deletions == 10
    assert context.changed_file_paths == ["src/widgets/core.py", "tests/test_core.py"]


def test_missing_pull_request_key_raises_malformed():
    payload = {"number": 1, "repository": {"full_name": "acme/widgets"}}

    with pytest.raises(MalformedPrChangedPayload):
        _extract_context(payload)


def test_missing_files_key_defaults_to_empty_list():
    payload = {**VALID_PAYLOAD, "files": None}
    del payload["files"]

    context = _extract_context(payload)

    assert context.changed_file_paths == []
