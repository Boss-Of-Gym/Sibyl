import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sibyl.platform.db import Base
from sibyl.platform.events.outbox import OutboxEventMixin


class FailureEvent(Base):
    __tablename__ = "failure_event"
    __table_args__ = (
        UniqueConstraint("repository", "test_identifier", "commit_sha", "ci_run_id"),
        {"schema": "root_cause_analysis"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    test_identifier: Mapped[str] = mapped_column(String, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String, nullable=False)
    ci_run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    hypotheses: Mapped[list["RootCauseHypothesis"]] = relationship(
        back_populates="failure_event", cascade="all, delete-orphan"
    )


class RootCauseHypothesis(Base):
    __tablename__ = "root_cause_hypothesis"
    __table_args__ = {"schema": "root_cause_analysis"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    failure_event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("root_cause_analysis.failure_event.id"),
        nullable=False,
    )
    hypothesis_text: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    suspected_commit_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    suspected_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_model: Mapped[str] = mapped_column(String, nullable=False)
    llm_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    failure_event: Mapped[FailureEvent] = relationship(back_populates="hypotheses")


class PrContextProjection(Base):
    __tablename__ = "pr_context_projection"
    __table_args__ = (
        UniqueConstraint("repository", "pr_number"),
        {"schema": "root_cause_analysis"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    head_sha: Mapped[str] = mapped_column(String, nullable=False)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation_unavailable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TestImpactProjection(Base):
    __tablename__ = "test_impact_projection"
    __table_args__ = (
        UniqueConstraint("repository", "pr_number"),
        {"schema": "root_cause_analysis"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    affected_tests: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FlakySignalProjection(Base):
    __tablename__ = "flaky_signal_projection"
    __table_args__ = {"schema": "root_cause_analysis"}

    test_identifier: Mapped[str] = mapped_column(String, primary_key=True)
    repository: Mapped[str] = mapped_column(String, primary_key=True)
    flakiness_score: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RootCauseAnalysisOutboxEvent(Base, OutboxEventMixin):
    __tablename__ = "outbox_event"
    __table_args__ = {"schema": "root_cause_analysis"}
