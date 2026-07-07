import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sibyl.platform.db import Base
from sibyl.platform.events.outbox import OutboxEventMixin


class PullRequest(Base):
    __tablename__ = "pull_request"
    __table_args__ = {"schema": "pr_analysis"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    head_sha: Mapped[str] = mapped_column(String, nullable=False)
    base_sha: Mapped[str] = mapped_column(String, nullable=False)
    author_login: Mapped[str] = mapped_column(String, nullable=False)
    files_changed: Mapped[int] = mapped_column(Integer, nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    risk_assessments: Mapped[list["PrRiskAssessment"]] = relationship(
        back_populates="pull_request", cascade="all, delete-orphan"
    )


class PrRiskAssessment(Base):
    __tablename__ = "pr_risk_assessment"
    __table_args__ = {"schema": "pr_analysis"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pr_analysis.pull_request.id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    contributing_factors: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    llm_model: Mapped[str] = mapped_column(String, nullable=False)
    llm_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    pull_request: Mapped[PullRequest] = relationship(back_populates="risk_assessments")


class LocalFlakySignalProjection(Base):
    __tablename__ = "local_flaky_signal_projection"
    __table_args__ = {"schema": "pr_analysis"}

    test_identifier: Mapped[str] = mapped_column(String, primary_key=True)
    repository: Mapped[str] = mapped_column(String, primary_key=True)
    flakiness_score: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PrAnalysisOutboxEvent(Base, OutboxEventMixin):
    __tablename__ = "outbox_event"
    __table_args__ = {"schema": "pr_analysis"}
