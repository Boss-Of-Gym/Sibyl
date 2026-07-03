import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sibyl.platform.db import Base


class Installation(Base):
    __tablename__ = "installation"
    __table_args__ = {"schema": "identity"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    github_installation_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    organization_login: Mapped[str] = mapped_column(String, nullable=False)
    repository_selection: Mapped[str] = mapped_column(String, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    repositories: Mapped[list["InstallationRepository"]] = relationship(
        back_populates="installation", cascade="all, delete-orphan"
    )


class InstallationRepository(Base):
    __tablename__ = "installation_repository"
    __table_args__ = {"schema": "identity"}

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("identity.installation.id"), nullable=False
    )
    repository_full_name: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    installation: Mapped[Installation] = relationship(back_populates="repositories")
