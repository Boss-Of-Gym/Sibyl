import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column


class OutboxEventMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OutboxRepository[OutboxModelT: OutboxEventMixin]:
    def __init__(self, model: type[OutboxModelT]):
        self._model = model

    async def add(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        installation_id: uuid.UUID,
        payload: dict[str, Any],
        occurred_at: datetime,
    ) -> OutboxModelT:
        event = self._model()
        event.event_type = event_type
        event.installation_id = installation_id
        event.payload = payload
        event.occurred_at = occurred_at
        session.add(event)
        return event

    async def fetch_unpublished(
        self, session: AsyncSession, limit: int = 100
    ) -> list[OutboxModelT]:
        stmt = (
            select(self._model)
            .where(self._model.published_at.is_(None))
            .order_by(self._model.occurred_at)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def mark_published(
        self, session: AsyncSession, events: list[OutboxModelT], published_at: datetime
    ) -> None:
        for event in events:
            event.published_at = published_at
