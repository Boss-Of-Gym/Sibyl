from typing import Any

from aiokafka.structs import ConsumerRecord

from sibyl.platform.events.errors import MalformedEventError
from sibyl.platform.events.kafka import EventPublisher, KafkaConsumerClient


class _RecordingDlqProducer:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, dict[str, Any]]] = []

    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        self.published.append((topic, key, value))


def _make_client(
    dlq_producer: EventPublisher, max_retries: int = 5, initial_backoff_seconds: float = 0.001
) -> KafkaConsumerClient:
    return KafkaConsumerClient(
        topics=["some-topic"],
        bootstrap_servers="localhost:9092",
        group_id="test-group",
        dlq_producer=dlq_producer,
        max_retries=max_retries,
        initial_backoff_seconds=initial_backoff_seconds,
    )


def _make_record(
    topic: str = "some-topic",
    key: bytes | None = b"install-1",
    value: dict[str, Any] | None = None,
) -> ConsumerRecord:
    return ConsumerRecord(
        topic=topic,
        partition=0,
        offset=0,
        timestamp=0,
        timestamp_type=0,
        key=key,
        value=value or {"foo": "bar"},
        checksum=None,
        serialized_key_size=-1,
        serialized_value_size=-1,
        headers=[],
    )


async def test_successful_handler_does_not_retry_or_dead_letter():
    dlq = _RecordingDlqProducer()
    client = _make_client(dlq)
    calls = []

    async def handler(payload):
        calls.append(payload)

    await client._process_with_retry(_make_record(), handler)

    assert calls == [{"foo": "bar"}]
    assert dlq.published == []


async def test_transient_failure_then_success_retries_without_dead_lettering():
    dlq = _RecordingDlqProducer()
    client = _make_client(dlq)
    attempts = []

    async def handler(payload):
        attempts.append(payload)
        if len(attempts) < 3:
            raise RuntimeError("transient db timeout")

    await client._process_with_retry(_make_record(), handler)

    assert len(attempts) == 3
    assert dlq.published == []


async def test_exhausted_retries_dead_letters_with_original_payload():
    dlq = _RecordingDlqProducer()
    client = _make_client(dlq, max_retries=2)

    async def handler(payload):
        raise RuntimeError("db is down")

    record = _make_record(topic="ingestion.pr-changed", key=b"install-1", value={"pr": 1})
    await client._process_with_retry(record, handler)

    assert len(dlq.published) == 1
    topic, key, value = dlq.published[0]
    assert topic == "ingestion.pr-changed.dlq"
    assert key == "install-1"
    assert value["original_payload"] == {"pr": 1}
    assert "db is down" in value["failure_reason"]


async def test_malformed_event_dead_letters_immediately_without_retrying():
    dlq = _RecordingDlqProducer()
    client = _make_client(dlq, max_retries=5)
    attempts = []

    async def handler(payload):
        attempts.append(payload)
        raise MalformedEventError("missing required field")

    await client._process_with_retry(_make_record(), handler)

    assert len(attempts) == 1
    assert len(dlq.published) == 1
    assert "missing required field" in dlq.published[0][2]["failure_reason"]


async def test_dead_letter_uses_empty_key_when_record_key_is_none():
    dlq = _RecordingDlqProducer()
    client = _make_client(dlq, max_retries=0)

    async def handler(payload):
        raise RuntimeError("boom")

    await client._process_with_retry(_make_record(key=None), handler)

    assert dlq.published[0][1] == ""
