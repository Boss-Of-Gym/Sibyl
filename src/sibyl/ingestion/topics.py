GITHUB_EVENT_TO_TOPIC = {
    "pull_request": "ingestion.pr-changed",
}


def resolve_topic(github_event_type: str) -> str | None:
    return GITHUB_EVENT_TO_TOPIC.get(github_event_type)
