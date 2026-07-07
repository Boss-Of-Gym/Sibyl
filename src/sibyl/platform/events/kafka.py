import asyncio
import json
from collections.abc import Callable
from typing import Any, Protocol

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import ConsumerRecord

from sibyl.platform.events.errors import MalformedEventError
from sibyl.platform.observability import get_logger, get_meter

logger = get_logger(__name__)
meter = get_meter(__name__)

_retry_total = meter.create_counter("consumer.retry_total")
_dead_lettered_total = meter.create_counter("consumer.dead_lettered_total")
_malformed_event_total = meter.create_counter("consumer.malformed_event_total")

MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 1.0


class EventPublisher(Protocol):
    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None: ...


class KafkaProducerClient:
    def __init__(self, bootstrap_servers: str):
        self._bootstrap_servers = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8"),
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()

    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        if self._producer is None:
            raise RuntimeError("KafkaProducerClient.start() must be called before publish()")
        await self._producer.send_and_wait(topic, value=value, key=key)


class KafkaConsumerClient:
    def __init__(
        self,
        topics: list[str],
        bootstrap_servers: str,
        group_id: str,
        dlq_producer: EventPublisher,
        max_retries: int = MAX_RETRIES,
        initial_backoff_seconds: float = INITIAL_BACKOFF_SECONDS,
    ):
        self._consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=False,
        )
        self._dlq_producer = dlq_producer
        self._max_retries = max_retries
        self._initial_backoff_seconds = initial_backoff_seconds

    async def start(self) -> None:
        await self._consumer.start()

    async def stop(self) -> None:
        await self._consumer.stop()

    async def consume_forever(self, handler: Callable[[dict[str, Any]], Any]) -> None:
        async for record in self._consumer:
            await self._process_with_retry(record, handler)
            await self._consumer.commit()

    async def _process_with_retry(
        self, record: ConsumerRecord, handler: Callable[[dict[str, Any]], Any]
    ) -> None:
        attempt = 0
        while True:
            try:
                await handler(record.value)
                return
            except MalformedEventError as exc:
                logger.error("consumer.malformed_event", topic=record.topic, reason=str(exc))
                _malformed_event_total.add(1, {"topic": record.topic})
                await self._dead_letter(record, reason=str(exc))
                return
            except Exception as exc:
                attempt += 1
                if attempt > self._max_retries:
                    logger.error(
                        "consumer.dead_lettered",
                        topic=record.topic,
                        attempts=attempt,
                        exc_info=True,
                    )
                    _dead_lettered_total.add(1, {"topic": record.topic})
                    await self._dead_letter(record, reason=str(exc))
                    return
                logger.warning(
                    "consumer.retry", topic=record.topic, attempt=attempt, reason=str(exc)
                )
                _retry_total.add(1, {"topic": record.topic})
                await asyncio.sleep(self._initial_backoff_seconds * (2 ** (attempt - 1)))

    async def _dead_letter(self, record: ConsumerRecord, reason: str) -> None:
        await self._dlq_producer.publish(
            topic=f"{record.topic}.dlq",
            key=record.key.decode("utf-8") if record.key else "",
            value={"original_payload": record.value, "failure_reason": reason},
        )
