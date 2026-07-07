import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sibyl.platform.db import Base
from sibyl.platform.events.outbox import OutboxEventMixin


class RegressionSignalProjection(Base):
    __tablename__ = "regression_signal_projection"
    __table_args__ = (
        UniqueConstraint("repository", "pr_number"),
        {"schema": "release_risk_analysis"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    head_sha: Mapped[str] = mapped_column(String, nullable=False)
    regression_probability: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CiHealthProjection(Base):
    __tablename__ = "ci_health_projection"
    __table_args__ = (
        UniqueConstraint("repository", "ci_run_id"),
        {"schema": "release_risk_analysis"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    ci_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CoverageSignalProjection(Base):
    __tablename__ = "coverage_signal_projection"
    __table_args__ = (
        UniqueConstraint("repository", "file_path"),
        {"schema": "release_risk_analysis"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    coverage_pct: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReleaseRiskAssessment(Base):
    __tablename__ = "release_risk_assessment"
    __table_args__ = {"schema": "release_risk_analysis"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    head_sha: Mapped[str] = mapped_column(String, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    considered_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    regression_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReleaseRiskOutboxEvent(Base, OutboxEventMixin):
    __tablename__ = "outbox_event"
    __table_args__ = {"schema": "release_risk_analysis"}
