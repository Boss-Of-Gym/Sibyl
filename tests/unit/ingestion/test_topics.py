from sibyl.ingestion.topics import resolve_topic


def test_pull_request_maps_to_pr_changed():
    assert resolve_topic("pull_request") == "ingestion.pr-changed"


def test_check_suite_has_no_topic_mapping():
    assert resolve_topic("check_suite") is None


def test_workflow_run_has_no_topic_mapping():
    assert resolve_topic("workflow_run") is None


def test_unknown_event_type_resolves_to_none():
    assert resolve_topic("star") is None
