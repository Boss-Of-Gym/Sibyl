import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.release_risk_analysis.adapters.db_models import (
    CiHealthProjection,
    CoverageSignalProjection,
    RegressionSignalProjection,
    ReleaseRiskAssessment,
)


class ReleaseRiskAnalysisRepository:
    async def upsert_regression_signal(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        pr_number: int,
        head_sha: str,
        regression_probability: float,
        computed_at: datetime,
    ) -> RegressionSignalProjection:
        stmt = select(RegressionSignalProjection).where(
            RegressionSignalProjection.repository == repository,
            RegressionSignalProjection.pr_number == pr_number,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.head_sha = head_sha
            existing.regression_probability = regression_probability
            existing.computed_at = computed_at
            return existing

        projection = RegressionSignalProjection(
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            regression_probability=regression_probability,
            computed_at=computed_at,
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
        passed_count: int,
        failed_count: int,
        completed_at: datetime,
    ) -> CiHealthProjection:
        stmt = select(CiHealthProjection).where(
            CiHealthProjection.repository == repository,
            CiHealthProjection.ci_run_id == ci_run_id,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.passed_count = passed_count
            existing.failed_count = failed_count
            existing.completed_at = completed_at
            return existing

        projection = CiHealthProjection(
            installation_id=installation_id,
            repository=repository,
            ci_run_id=ci_run_id,
            passed_count=passed_count,
            failed_count=failed_count,
            completed_at=completed_at,
        )
        session.add(projection)
        return projection

    async def upsert_coverage_signal(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        file_path: str,
        coverage_pct: float,
        computed_at: datetime,
    ) -> CoverageSignalProjection:
        stmt = select(CoverageSignalProjection).where(
            CoverageSignalProjection.repository == repository,
            CoverageSignalProjection.file_path == file_path,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.coverage_pct = coverage_pct
            existing.computed_at = computed_at
            return existing

        projection = CoverageSignalProjection(
            installation_id=installation_id,
            repository=repository,
            file_path=file_path,
            coverage_pct=coverage_pct,
            computed_at=computed_at,
        )
        session.add(projection)
        return projection

    async def get_recent_ci_runs(
        self, session: AsyncSession, repository: str, limit: int = 20
    ) -> list[CiHealthProjection]:
        stmt = (
            select(CiHealthProjection)
            .where(CiHealthProjection.repository == repository)
            .order_by(CiHealthProjection.completed_at.desc())
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def get_coverage_signals(
        self, session: AsyncSession, repository: str
    ) -> list[CoverageSignalProjection]:
        stmt = select(CoverageSignalProjection).where(
            CoverageSignalProjection.repository == repository
        )
        return list((await session.execute(stmt)).scalars().all())

    async def save_assessment(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        pr_number: int,
        head_sha: str,
        risk_score: float,
        considered_signals: list[str],
        regression_probability: float | None,
        ci_success_rate: float | None,
        coverage_pct: float | None,
        computed_at: datetime,
    ) -> ReleaseRiskAssessment:
        record = ReleaseRiskAssessment(
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            risk_score=risk_score,
            considered_signals=considered_signals,
            regression_probability=regression_probability,
            ci_success_rate=ci_success_rate,
            coverage_pct=coverage_pct,
            computed_at=computed_at,
        )
        session.add(record)
        return record

    async def get_latest_assessment(
        self, session: AsyncSession, repository: str, pr_number: int
    ) -> ReleaseRiskAssessment | None:
        stmt = (
            select(ReleaseRiskAssessment)
            .where(
                ReleaseRiskAssessment.repository == repository,
                ReleaseRiskAssessment.pr_number == pr_number,
            )
            .order_by(ReleaseRiskAssessment.computed_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()
