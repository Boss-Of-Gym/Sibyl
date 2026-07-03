import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sibyl.platform.db import Base
from sibyl.platform.events.outbox import OutboxEventMixin


class WebhookDelivery(Base):
    __tablename__ = "webhook_delivery"
    __table_args__ = {"schema": "ingestion"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    github_delivery_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)


class IngestionOutboxEvent(Base, OutboxEventMixin):
    __tablename__ = "outbox_event"
    __table_args__ = {"schema": "ingestion"}
