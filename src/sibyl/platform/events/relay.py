from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.platform.events.kafka import KafkaProducerClient
from sibyl.platform.events.outbox import OutboxEventMixin, OutboxRepository


async def relay_once[OutboxModelT: OutboxEventMixin](
    session: AsyncSession,
    repository: OutboxRepository[OutboxModelT],
    producer: KafkaProducerClient,
    limit: int = 100,
) -> int:
    events = await repository.fetch_unpublished(session, limit=limit)
    for event in events:
        envelope = {
            "schema_version": 1,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat(),
            "installation_id": str(event.installation_id),
            "payload": event.payload,
        }
        await producer.publish(
            topic=event.event_type,
            key=str(event.installation_id),
            value=envelope,
        )
    if events:
        await repository.mark_published(session, events, datetime.now(UTC))
        await session.commit()
    return len(events)
