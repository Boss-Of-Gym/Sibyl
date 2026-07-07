import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.engineering_metrics.adapters.db_models import (
    CiRunProjection,
    PrLifecycleProjection,
)


class EngineeringMetricsRepository:
    async def upsert_pr_lifecycle(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        pr_number: int,
        opened_at: datetime,
        merged_at: datetime | None,
        closed_at: datetime | None,
        merged: bool,
    ) -> PrLifecycleProjection:
        stmt = select(PrLifecycleProjection).where(
            PrLifecycleProjection.repository == repository,
            PrLifecycleProjection.pr_number == pr_number,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.opened_at = opened_at
            existing.merged_at = merged_at
            existing.closed_at = closed_at
            existing.merged = merged
            return existing

        projection = PrLifecycleProjection(
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            opened_at=opened_at,
            merged_at=merged_at,
            closed_at=closed_at,
            merged=merged,
        )
        session.add(projection)
        return projection

    async def upsert_ci_run(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        ci_run_id: int,
        commit_sha: str,
        started_at: datetime,
        completed_at: datetime,
        passed_count: int,
        failed_count: int,
        skipped_count: int,
    ) -> CiRunProjection:
        stmt = select(CiRunProjection).where(
            CiRunProjection.repository == repository,
            CiRunProjection.ci_run_id == ci_run_id,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.commit_sha = commit_sha
            existing.started_at = started_at
            existing.completed_at = completed_at
            existing.passed_count = passed_count
            existing.failed_count = failed_count
            existing.skipped_count = skipped_count
            return existing

        projection = CiRunProjection(
            installation_id=installation_id,
            repository=repository,
            ci_run_id=ci_run_id,
            commit_sha=commit_sha,
            started_at=started_at,
            completed_at=completed_at,
            passed_count=passed_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        )
        session.add(projection)
        return projection

    async def get_pr_lifecycle_in_window(
        self, session: AsyncSession, repository: str, since: datetime
    ) -> list[PrLifecycleProjection]:
        stmt = select(PrLifecycleProjection).where(
            PrLifecycleProjection.repository == repository,
            PrLifecycleProjection.opened_at >= since,
        )
        return list((await session.execute(stmt)).scalars().all())

    async def get_ci_runs_in_window(
        self, session: AsyncSession, repository: str, since: datetime
    ) -> list[CiRunProjection]:
        stmt = select(CiRunProjection).where(
            CiRunProjection.repository == repository,
            CiRunProjection.started_at >= since,
        )
        return list((await session.execute(stmt)).scalars().all())
