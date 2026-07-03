import json
from collections.abc import Callable
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer


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
    def __init__(self, topics: list[str], bootstrap_servers: str, group_id: str):
        self._consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=False,
        )

    async def start(self) -> None:
        await self._consumer.start()

    async def stop(self) -> None:
        await self._consumer.stop()

    async def consume_forever(self, handler: Callable[[dict[str, Any]], Any]) -> None:
        async for record in self._consumer:
            await handler(record.value)
            await self._consumer.commit()
