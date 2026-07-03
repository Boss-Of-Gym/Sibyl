import pytest

from sibyl.test_intelligence.application import MalformedPrChangedPayload, _extract_changed_files

VALID_PAYLOAD = {
    "number": 12,
    "repository": {"full_name": "acme/widgets"},
    "pull_request": {"head": {"sha": "abc123"}},
    "files": [{"filename": "src/a.py"}, {"filename": "src/b.py"}],
}


def test_extracts_all_fields():
    repository, commit_sha, pr_number, changed_files = _extract_changed_files(VALID_PAYLOAD)

    assert repository == "acme/widgets"
    assert commit_sha == "abc123"
    assert pr_number == 12
    assert changed_files == ["src/a.py", "src/b.py"]


def test_missing_key_raises_malformed():
    with pytest.raises(MalformedPrChangedPayload):
        _extract_changed_files({"number": 1})


def test_missing_files_defaults_to_empty_list():
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "files"}

    _, _, _, changed_files = _extract_changed_files(payload)

    assert changed_files == []
