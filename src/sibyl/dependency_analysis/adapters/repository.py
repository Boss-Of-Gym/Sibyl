import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.dependency_analysis.adapters.db_models import DependencyManifestSnapshot


class DependencyAnalysisRepository:
    async def upsert_manifest_snapshot(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        commit_sha: str,
        ecosystem: str,
        packages: list[dict[str, object]],
        received_at: datetime,
    ) -> DependencyManifestSnapshot:
        stmt = select(DependencyManifestSnapshot).where(
            DependencyManifestSnapshot.repository == repository,
            DependencyManifestSnapshot.commit_sha == commit_sha,
            DependencyManifestSnapshot.ecosystem == ecosystem,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.packages = packages
            existing.received_at = received_at
            return existing

        snapshot = DependencyManifestSnapshot(
            installation_id=installation_id,
            repository=repository,
            commit_sha=commit_sha,
            ecosystem=ecosystem,
            packages=packages,
            received_at=received_at,
        )
        session.add(snapshot)
        await session.flush()
        return snapshot

    async def get_latest_snapshots_by_repository(
        self, session: AsyncSession, repository: str
    ) -> list[DependencyManifestSnapshot]:
        stmt = (
            select(DependencyManifestSnapshot)
            .where(DependencyManifestSnapshot.repository == repository)
            .order_by(DependencyManifestSnapshot.received_at.desc())
        )
        snapshots = (await session.execute(stmt)).scalars().all()

        latest_by_ecosystem: dict[str, DependencyManifestSnapshot] = {}
        for snapshot in snapshots:
            latest_by_ecosystem.setdefault(snapshot.ecosystem, snapshot)
        return list(latest_by_ecosystem.values())

    async def get_recent_snapshots(
        self, session: AsyncSession, repository: str, ecosystem: str, limit: int = 2
    ) -> list[DependencyManifestSnapshot]:
        stmt = (
            select(DependencyManifestSnapshot)
            .where(
                DependencyManifestSnapshot.repository == repository,
                DependencyManifestSnapshot.ecosystem == ecosystem,
            )
            .order_by(DependencyManifestSnapshot.received_at.desc())
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())
