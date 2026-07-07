import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sibyl.platform.events.kafka import EventPublisher
from sibyl.platform.events.outbox import OutboxEventMixin, OutboxRepository
from sibyl.platform.observability import get_logger, get_meter

logger = get_logger(__name__)
meter = get_meter(__name__)

_publish_retry_total = meter.create_counter("outbox.publish_retry_total")

MAX_PUBLISH_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 1.0


async def _publish_with_retry(
    producer: EventPublisher,
    topic: str,
    key: str,
    value: dict[str, object],
    max_retries: int = MAX_PUBLISH_RETRIES,
    initial_backoff_seconds: float = INITIAL_BACKOFF_SECONDS,
) -> bool:
    attempt = 0
    while True:
        try:
            await producer.publish(topic=topic, key=key, value=value)
            return True
        except Exception:
            attempt += 1
            if attempt > max_retries:
                logger.error("outbox.publish_failed", topic=topic, key=key, exc_info=True)
                return False
            logger.warning("outbox.publish_retry", topic=topic, key=key, attempt=attempt)
            _publish_retry_total.add(1, {"topic": topic})
            await asyncio.sleep(initial_backoff_seconds * (2 ** (attempt - 1)))


async def relay_once[OutboxModelT: OutboxEventMixin](
    session: AsyncSession,
    repository: OutboxRepository[OutboxModelT],
    producer: EventPublisher,
    limit: int = 100,
    max_retries: int = MAX_PUBLISH_RETRIES,
    initial_backoff_seconds: float = INITIAL_BACKOFF_SECONDS,
) -> int:
    events = await repository.fetch_unpublished(session, limit=limit)
    published = []
    for event in events:
        envelope = {
            "schema_version": 1,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat(),
            "installation_id": str(event.installation_id),
            "payload": event.payload,
        }
        succeeded = await _publish_with_retry(
            producer,
            topic=event.event_type,
            key=str(event.installation_id),
            value=envelope,
            max_retries=max_retries,
            initial_backoff_seconds=initial_backoff_seconds,
        )
        if succeeded:
            published.append(event)

    if published:
        await repository.mark_published(session, published, datetime.now(UTC))
        await session.commit()
    return len(published)


async def run_relay_forever[OutboxModelT: OutboxEventMixin](
    session_factory: async_sessionmaker[AsyncSession],
    repository: OutboxRepository[OutboxModelT],
    producer: EventPublisher,
    poll_interval_seconds: float = 2.0,
) -> None:
    while True:
        async with session_factory() as session:
            await relay_once(session, repository, producer)
        await asyncio.sleep(poll_interval_seconds)
