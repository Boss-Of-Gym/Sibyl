import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.identity.adapters.db_models import Installation


class InstallationRepository:
    async def get_by_id(
        self, session: AsyncSession, installation_id: uuid.UUID
    ) -> Installation | None:
        return await session.get(Installation, installation_id)

    async def get_by_github_id(
        self, session: AsyncSession, github_installation_id: int
    ) -> Installation | None:
        stmt = select(Installation).where(
            Installation.github_installation_id == github_installation_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_organization_login(
        self, session: AsyncSession, organization_login: str
    ) -> Installation | None:
        stmt = (
            select(Installation)
            .where(Installation.organization_login == organization_login)
            .order_by(Installation.installed_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_by_github_id(
        self,
        session: AsyncSession,
        github_installation_id: int,
        organization_login: str = "",
    ) -> Installation:
        existing = await self.get_by_github_id(session, github_installation_id)
        if existing is not None:
            return existing
        installation = Installation(
            github_installation_id=github_installation_id,
            organization_login=organization_login,
            repository_selection="selected",
            installed_at=datetime.now(UTC),
        )
        session.add(installation)
        await session.flush()
        return installation
