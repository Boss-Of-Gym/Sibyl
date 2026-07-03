import uuid
from datetime import UTC, datetime

from aiokafka import AIOKafkaConsumer

from sibyl.ingestion.adapters.db_models import IngestionOutboxEvent
from sibyl.platform.events.kafka import KafkaProducerClient
from sibyl.platform.events.outbox import OutboxRepository
from sibyl.platform.events.relay import relay_once

repository = OutboxRepository(IngestionOutboxEvent)


async def test_relay_publishes_unpublished_events_and_marks_them_published(
    db_session, kafka_container
):
    installation_id = uuid.uuid4()
    await repository.add(
        db_session,
        event_type="ingestion.pr-changed",
        installation_id=installation_id,
        payload={"pr_number": 99},
        occurred_at=datetime.now(UTC),
    )
    await db_session.commit()

    bootstrap_servers = kafka_container.get_bootstrap_server()
    producer = KafkaProducerClient(bootstrap_servers)
    await producer.start()

    consumer = AIOKafkaConsumer(
        "ingestion.pr-changed",
        bootstrap_servers=bootstrap_servers,
        auto_offset_reset="earliest",
        group_id=f"test-{uuid.uuid4()}",
    )
    await consumer.start()

    try:
        published_count = await relay_once(db_session, repository, producer)
        assert published_count >= 1

        record = await anext(aiter(consumer))
        received = record.value.decode("utf-8")
        assert "\"pr_number\": 99" in received
        assert str(installation_id) in received

        remaining = await repository.fetch_unpublished(db_session)
        assert all(e.installation_id != installation_id for e in remaining)
    finally:
        await consumer.stop()
        await producer.stop()
