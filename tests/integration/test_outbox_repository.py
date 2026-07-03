import uuid
from datetime import UTC, datetime

from sibyl.ingestion.adapters.db_models import IngestionOutboxEvent
from sibyl.platform.events.outbox import OutboxRepository

repository = OutboxRepository(IngestionOutboxEvent)


async def test_added_event_is_unpublished_by_default(db_session):
    installation_id = uuid.uuid4()

    await repository.add(
        db_session,
        event_type="ingestion.pr-changed",
        installation_id=installation_id,
        payload={"pr_number": 42},
        occurred_at=datetime.now(UTC),
    )
    await db_session.flush()

    unpublished = await repository.fetch_unpublished(db_session)

    assert any(e.installation_id == installation_id for e in unpublished)


async def test_marking_published_excludes_it_from_unpublished(db_session):
    installation_id = uuid.uuid4()
    event = await repository.add(
        db_session,
        event_type="ingestion.pr-changed",
        installation_id=installation_id,
        payload={"pr_number": 7},
        occurred_at=datetime.now(UTC),
    )
    await db_session.flush()

    await repository.mark_published(db_session, [event], datetime.now(UTC))
    await db_session.flush()

    unpublished = await repository.fetch_unpublished(db_session)

    assert event.id not in [e.id for e in unpublished]
