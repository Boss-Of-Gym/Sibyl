from typing import Any

from sibyl.platform.events.relay import _publish_with_retry


class _AlwaysFailingProducer:
    def __init__(self) -> None:
        self.attempts = 0

    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        self.attempts += 1
        raise RuntimeError("kafka is unreachable")


class _FailsTwiceThenSucceedsProducer:
    def __init__(self) -> None:
        self.attempts = 0

    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        self.attempts += 1
        if self.attempts <= 2:
            raise RuntimeError("transient broker error")


async def test_publish_with_retry_succeeds_after_transient_failures():
    producer = _FailsTwiceThenSucceedsProducer()

    succeeded = await _publish_with_retry(
        producer, topic="t", key="k", value={}, initial_backoff_seconds=0.001
    )

    assert succeeded is True
    assert producer.attempts == 3


async def test_publish_with_retry_gives_up_after_max_retries():
    producer = _AlwaysFailingProducer()

    succeeded = await _publish_with_retry(
        producer, topic="t", key="k", value={}, max_retries=2, initial_backoff_seconds=0.001
    )

    assert succeeded is False
    assert producer.attempts == 3
