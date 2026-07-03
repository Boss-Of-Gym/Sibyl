import uuid
from typing import Any

from sqlalchemy import select

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.test_intelligence.adapters.db_models import TestIntelligenceOutboxEvent
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository
from sibyl.test_intelligence.application import TestIntelligenceService

TEST_IDENTIFIER = "tests/test_flaky.py::test_flaky"


def _service() -> TestIntelligenceService:
    return TestIntelligenceService(
        TestIntelligenceRepository(), OutboxRepository(TestIntelligenceOutboxEvent)
    )


def _ci_payload(
    repository: str, commit_sha: str, ci_run_id: int, status: str
) -> dict[str, Any]:
    return {
        "repository": repository,
        "commit_sha": commit_sha,
        "ci_run_id": ci_run_id,
        "started_at": "2026-07-02T00:00:00Z",
        "completed_at": f"2026-07-02T00:{ci_run_id:02d}:00Z",
        "tests": [{"test_identifier": TEST_IDENTIFIER, "status": status}],
    }


async def _get_flaky_signal_events(
    db_session, installation_id
) -> list[TestIntelligenceOutboxEvent]:
    stmt = select(TestIntelligenceOutboxEvent).where(
        TestIntelligenceOutboxEvent.event_type == "test-intelligence.flaky-signal-updated",
        TestIntelligenceOutboxEvent.installation_id == installation_id,
    )
    return list((await db_session.execute(stmt)).scalars().all())


async def test_first_ci_run_always_publishes_material_change_event(db_session):
    repository = "acme/flaky-service-first-run"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-1", 1, "passed")
    )

    signal = await TestIntelligenceRepository().get_stability_signal(
        db_session, repository, TEST_IDENTIFIER
    )
    assert signal is not None
    assert signal.flakiness_score == 0.0
    assert signal.sample_size == 1

    events = await _get_flaky_signal_events(db_session, installation_id)
    assert len(events) == 1
    assert events[0].payload["flakiness_score"] == 0.0


async def test_repeated_stable_result_does_not_publish_a_second_event(db_session):
    repository = "acme/flaky-service-stable"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-2", 1, "passed")
    )
    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-3", 2, "passed")
    )

    signal = await TestIntelligenceRepository().get_stability_signal(
        db_session, repository, TEST_IDENTIFIER
    )
    assert signal is not None
    assert signal.flakiness_score == 0.0
    assert signal.sample_size == 2

    events = await _get_flaky_signal_events(db_session, installation_id)
    assert len(events) == 1


async def test_alternating_results_raise_flakiness_score_and_republish(db_session):
    repository = "acme/flaky-service-alternating"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-4", 1, "passed")
    )
    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-5", 2, "passed")
    )
    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-6", 3, "failed")
    )

    signal = await TestIntelligenceRepository().get_stability_signal(
        db_session, repository, TEST_IDENTIFIER
    )
    assert signal is not None
    assert signal.sample_size == 3
    assert round(signal.flakiness_score, 6) == round(2 / 3, 6)

    events = await _get_flaky_signal_events(db_session, installation_id)
    assert len(events) == 2
    assert events[0].payload["flakiness_score"] == 0.0
    assert round(events[1].payload["flakiness_score"], 6) == round(2 / 3, 6)


async def test_skipped_only_history_does_not_create_a_stability_signal(db_session):
    repository = "acme/flaky-service-skipped"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-7", 1, "skipped")
    )

    signal = await TestIntelligenceRepository().get_stability_signal(
        db_session, repository, TEST_IDENTIFIER
    )
    assert signal is None

    events = await _get_flaky_signal_events(db_session, installation_id)
    assert events == []
