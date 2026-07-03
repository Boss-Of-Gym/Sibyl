import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sibyl.platform.db import Base


class DependencyManifestSnapshot(Base):
    __tablename__ = "dependency_manifest_snapshot"
    __table_args__ = (
        UniqueConstraint("repository", "commit_sha", "ecosystem"),
        {"schema": "dependency_analysis"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String, nullable=False)
    ecosystem: Mapped[str] = mapped_column(String, nullable=False)
    packages: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
