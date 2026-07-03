import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sibyl.platform.db import Base
from sibyl.platform.events.outbox import OutboxEventMixin


class PrChangedFilesProjection(Base):
    __tablename__ = "pr_changed_files_projection"
    __table_args__ = (
        UniqueConstraint("repository", "commit_sha"),
        {"schema": "test_intelligence"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_file_paths: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TestRun(Base):
    __tablename__ = "test_run"
    __table_args__ = (
        UniqueConstraint("repository", "commit_sha"),
        {"schema": "test_intelligence"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String, nullable=False)
    ci_run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    results: Mapped[list["TestCaseResult"]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )


class TestCaseResult(Base):
    __tablename__ = "test_case_result"
    __table_args__ = {"schema": "test_intelligence"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    test_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("test_intelligence.test_run.id"), nullable=False
    )
    test_identifier: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_message: Mapped[str | None] = mapped_column(String, nullable=True)

    test_run: Mapped[TestRun] = relationship(back_populates="results")


class TestImpact(Base):
    __tablename__ = "test_impact"
    __table_args__ = {"schema": "test_intelligence"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    affected_tests: Mapped[list["TestImpactAffectedTest"]] = relationship(
        back_populates="test_impact", cascade="all, delete-orphan"
    )


class TestImpactAffectedTest(Base):
    __tablename__ = "test_impact_affected_test"
    __table_args__ = {"schema": "test_intelligence"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    test_impact_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("test_intelligence.test_impact.id"), nullable=False
    )
    test_identifier: Mapped[str] = mapped_column(String, nullable=False)

    test_impact: Mapped[TestImpact] = relationship(back_populates="affected_tests")


class TestStabilitySignal(Base):
    __tablename__ = "test_stability_signal"
    __table_args__ = {"schema": "test_intelligence"}

    test_identifier: Mapped[str] = mapped_column(String, primary_key=True)
    repository: Mapped[str] = mapped_column(String, primary_key=True)
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    flakiness_score: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    last_computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TestDurationSignal(Base):
    __tablename__ = "test_duration_signal"
    __table_args__ = {"schema": "test_intelligence"}

    test_identifier: Mapped[str] = mapped_column(String, primary_key=True)
    repository: Mapped[str] = mapped_column(String, primary_key=True)
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    median_duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    last_computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FileCoverageSignal(Base):
    __tablename__ = "file_coverage_signal"
    __table_args__ = {"schema": "test_intelligence"}

    file_path: Mapped[str] = mapped_column(String, primary_key=True)
    repository: Mapped[str] = mapped_column(String, primary_key=True)
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String, nullable=False)
    lines_covered: Mapped[int] = mapped_column(Integer, nullable=False)
    lines_total: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_pct: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TestIntelligenceOutboxEvent(Base, OutboxEventMixin):
    __tablename__ = "outbox_event"
    __table_args__ = {"schema": "test_intelligence"}
