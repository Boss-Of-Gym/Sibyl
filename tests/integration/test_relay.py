import uuid
from datetime import UTC, datetime
from typing import Any

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


class _SelectivelyFailingProducer:
    def __init__(self, real_producer: KafkaProducerClient, fail_key: str):
        self._real = real_producer
        self._fail_key = fail_key

    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        if key == self._fail_key:
            raise RuntimeError("simulated broker rejection")
        await self._real.publish(topic=topic, key=key, value=value)


async def test_relay_marks_only_successfully_published_events_when_one_fails(
    db_session, kafka_container
):
    ok_installation_id = uuid.uuid4()
    failing_installation_id = uuid.uuid4()
    await repository.add(
        db_session,
        event_type="ingestion.pr-changed",
        installation_id=ok_installation_id,
        payload={"pr_number": 1},
        occurred_at=datetime.now(UTC),
    )
    await repository.add(
        db_session,
        event_type="ingestion.pr-changed",
        installation_id=failing_installation_id,
        payload={"pr_number": 2},
        occurred_at=datetime.now(UTC),
    )
    await db_session.commit()

    bootstrap_servers = kafka_container.get_bootstrap_server()
    real_producer = KafkaProducerClient(bootstrap_servers)
    await real_producer.start()
    producer = _SelectivelyFailingProducer(real_producer, str(failing_installation_id))

    try:
        await relay_once(
            db_session, repository, producer, max_retries=1, initial_backoff_seconds=0.001
        )

        remaining = await repository.fetch_unpublished(db_session)
        remaining_ids = {e.installation_id for e in remaining}
        assert failing_installation_id in remaining_ids
        assert ok_installation_id not in remaining_ids
    finally:
        await real_producer.stop()
