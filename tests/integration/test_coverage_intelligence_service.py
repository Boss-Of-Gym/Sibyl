import uuid

from sqlalchemy import select

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.test_intelligence.adapters.db_models import TestIntelligenceOutboxEvent
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository
from sibyl.test_intelligence.application import TestIntelligenceService


def _service() -> TestIntelligenceService:
    return TestIntelligenceService(
        TestIntelligenceRepository(), OutboxRepository(TestIntelligenceOutboxEvent)
    )


async def _get_coverage_computed_events(
    db_session, installation_id: uuid.UUID
) -> list[TestIntelligenceOutboxEvent]:
    stmt = select(TestIntelligenceOutboxEvent).where(
        TestIntelligenceOutboxEvent.event_type == "test-intelligence.coverage-computed",
        TestIntelligenceOutboxEvent.installation_id == installation_id,
    )
    return list((await db_session.execute(stmt)).scalars().all())


async def test_handle_coverage_report_received_upserts_all_files(db_session):
    repository = "acme/coverage-service-a"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_coverage_report_received(
        db_session,
        installation_id,
        {
            "repository": repository,
            "commit_sha": "sha-1",
            "files": [
                {"file_path": "src/a.py", "lines_covered": 8, "lines_total": 10},
                {"file_path": "src/b.py", "lines_covered": 2, "lines_total": 10},
            ],
        },
    )

    signal_a = await TestIntelligenceRepository().get_file_coverage_signal(
        db_session, repository, "src/a.py"
    )
    signal_b = await TestIntelligenceRepository().get_file_coverage_signal(
        db_session, repository, "src/b.py"
    )
    assert signal_a is not None
    assert signal_a.coverage_pct == 0.8
    assert signal_b is not None
    assert signal_b.coverage_pct == 0.2

    events = await _get_coverage_computed_events(db_session, installation_id)
    assert {e.payload["file_path"] for e in events} == {"src/a.py", "src/b.py"}
    assert {e.payload["coverage_pct"] for e in events} == {0.8, 0.2}


async def test_handle_coverage_report_received_overwrites_previous_snapshot(db_session):
    repository = "acme/coverage-service-b"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_coverage_report_received(
        db_session,
        installation_id,
        {
            "repository": repository,
            "commit_sha": "sha-1",
            "files": [{"file_path": "src/a.py", "lines_covered": 2, "lines_total": 10}],
        },
    )
    await service.handle_coverage_report_received(
        db_session,
        installation_id,
        {
            "repository": repository,
            "commit_sha": "sha-2",
            "files": [{"file_path": "src/a.py", "lines_covered": 9, "lines_total": 10}],
        },
    )

    signal = await TestIntelligenceRepository().get_file_coverage_signal(
        db_session, repository, "src/a.py"
    )
    assert signal is not None
    assert signal.commit_sha == "sha-2"
    assert signal.coverage_pct == 0.9
