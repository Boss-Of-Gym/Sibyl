import uuid

from sqlalchemy import select

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.test_intelligence.adapters.db_models import TestIntelligenceOutboxEvent
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository
from sibyl.test_intelligence.application import TestIntelligenceService

PR_CHANGED_PAYLOAD = {
    "number": 1,
    "repository": {"full_name": "acme/order-a"},
    "pull_request": {"head": {"sha": "sha-order-a"}},
    "files": [{"filename": "src/order_a.py"}],
}

CI_RUN_PAYLOAD = {
    "repository": "acme/order-a",
    "commit_sha": "sha-order-a",
    "ci_run_id": 1,
    "started_at": "2026-07-02T00:00:00Z",
    "completed_at": "2026-07-02T00:01:00Z",
    "tests": [{"test_identifier": "tests/test_order_a.py::test_it", "status": "passed"}],
}


def _service() -> TestIntelligenceService:
    return TestIntelligenceService(
        TestIntelligenceRepository(), OutboxRepository(TestIntelligenceOutboxEvent)
    )


async def _get_published_impact_events(
    db_session, installation_id
) -> list[TestIntelligenceOutboxEvent]:
    stmt = select(TestIntelligenceOutboxEvent).where(
        TestIntelligenceOutboxEvent.event_type == "test-intelligence.impact-computed",
        TestIntelligenceOutboxEvent.installation_id == installation_id,
    )
    return list((await db_session.execute(stmt)).scalars().all())


async def test_pr_changed_before_ci_run_still_computes_impact(db_session):
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_pr_changed(db_session, installation_id, PR_CHANGED_PAYLOAD)
    events_before = await _get_published_impact_events(db_session, installation_id)
    assert events_before == []

    await service.handle_ci_run_completed(db_session, installation_id, CI_RUN_PAYLOAD)

    events_after = await _get_published_impact_events(db_session, installation_id)
    assert len(events_after) == 1
    assert events_after[0].payload["affected_tests"] == ["tests/test_order_a.py::test_it"]


async def test_ci_run_before_pr_changed_still_computes_impact(db_session):
    installation_id = uuid.uuid4()
    service = _service()
    payload = {**CI_RUN_PAYLOAD, "commit_sha": "sha-order-b"}
    pr_payload = {
        **PR_CHANGED_PAYLOAD,
        "repository": {"full_name": "acme/order-b"},
        "pull_request": {"head": {"sha": "sha-order-b"}},
    }
    payload["repository"] = "acme/order-b"

    await service.handle_ci_run_completed(db_session, installation_id, payload)
    events_before = await _get_published_impact_events(db_session, installation_id)
    assert events_before == []

    await service.handle_pr_changed(db_session, installation_id, pr_payload)

    events_after = await _get_published_impact_events(db_session, installation_id)
    assert len(events_after) == 1
