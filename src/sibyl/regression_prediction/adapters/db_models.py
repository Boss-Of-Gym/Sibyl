import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sibyl.platform.db import Base
from sibyl.platform.events.outbox import OutboxEventMixin


class RegressionPredictionResult(Base):
    __tablename__ = "regression_prediction"
    __table_args__ = {"schema": "regression_prediction"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    head_sha: Mapped[str] = mapped_column(String, nullable=False)
    regression_probability: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    contributing_signals: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    llm_model: Mapped[str] = mapped_column(String, nullable=False)
    llm_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HistoricalRegressionProjection(Base):
    __tablename__ = "historical_regression_projection"
    __table_args__ = {"schema": "regression_prediction"}

    failure_event_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    hypothesis_text: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RegressionPredictionOutboxEvent(Base, OutboxEventMixin):
    __tablename__ = "outbox_event"
    __table_args__ = {"schema": "regression_prediction"}
