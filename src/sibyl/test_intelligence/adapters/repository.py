import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sibyl.test_intelligence.adapters.db_models import (
    FileCoverageSignal,
    PrChangedFilesProjection,
    TestCaseResult,
    TestDurationSignal,
    TestImpact,
    TestImpactAffectedTest,
    TestRun,
    TestStabilitySignal,
)
from sibyl.test_intelligence.domain.models import TestResultItem


class TestIntelligenceRepository:
    async def upsert_pr_changed_files(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        commit_sha: str,
        pr_number: int,
        changed_file_paths: list[str],
        received_at: datetime,
    ) -> PrChangedFilesProjection:
        existing = await self.get_pr_changed_files(session, repository, commit_sha)
        if existing is not None:
            existing.changed_file_paths = changed_file_paths
            return existing

        projection = PrChangedFilesProjection(
            installation_id=installation_id,
            repository=repository,
            commit_sha=commit_sha,
            pr_number=pr_number,
            changed_file_paths=changed_file_paths,
            received_at=received_at,
        )
        session.add(projection)
        await session.flush()
        return projection

    async def get_pr_changed_files(
        self, session: AsyncSession, repository: str, commit_sha: str
    ) -> PrChangedFilesProjection | None:
        stmt = select(PrChangedFilesProjection).where(
            PrChangedFilesProjection.repository == repository,
            PrChangedFilesProjection.commit_sha == commit_sha,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def upsert_test_run(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        commit_sha: str,
        ci_run_id: int,
        started_at: datetime,
        completed_at: datetime,
        tests: list[TestResultItem],
    ) -> TestRun:
        existing = await self.get_test_run(session, repository, commit_sha)
        if existing is not None:
            return existing

        test_run = TestRun(
            installation_id=installation_id,
            repository=repository,
            commit_sha=commit_sha,
            ci_run_id=ci_run_id,
            started_at=started_at,
            completed_at=completed_at,
        )
        session.add(test_run)
        await session.flush()

        for test in tests:
            session.add(
                TestCaseResult(
                    test_run_id=test_run.id,
                    test_identifier=test.test_identifier,
                    status=test.status,
                    duration_ms=test.duration_ms,
                    failure_message=test.failure_message,
                )
            )
        return test_run

    async def get_test_run(
        self, session: AsyncSession, repository: str, commit_sha: str
    ) -> TestRun | None:
        stmt = select(TestRun).where(
            TestRun.repository == repository, TestRun.commit_sha == commit_sha
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_observed_test_identifiers(
        self, session: AsyncSession, repository: str
    ) -> list[str]:
        stmt = (
            select(TestCaseResult.test_identifier)
            .join(TestRun, TestRun.id == TestCaseResult.test_run_id)
            .where(TestRun.repository == repository)
            .distinct()
        )
        return list((await session.execute(stmt)).scalars().all())

    async def save_test_impact(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        pr_number: int,
        commit_sha: str,
        affected_tests: list[str],
        computed_at: datetime,
    ) -> TestImpact:
        impact = TestImpact(
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            commit_sha=commit_sha,
            computed_at=computed_at,
        )
        session.add(impact)
        await session.flush()

        for test_identifier in affected_tests:
            session.add(
                TestImpactAffectedTest(test_impact_id=impact.id, test_identifier=test_identifier)
            )
        return impact

    async def get_latest_test_impact(
        self, session: AsyncSession, repository: str, pr_number: int
    ) -> TestImpact | None:
        stmt = (
            select(TestImpact)
            .where(TestImpact.repository == repository, TestImpact.pr_number == pr_number)
            .options(selectinload(TestImpact.affected_tests))
            .order_by(TestImpact.computed_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_recent_statuses(
        self, session: AsyncSession, repository: str, test_identifier: str, limit: int = 20
    ) -> list[str]:
        stmt = (
            select(TestCaseResult.status)
            .join(TestRun, TestRun.id == TestCaseResult.test_run_id)
            .where(
                TestRun.repository == repository,
                TestCaseResult.test_identifier == test_identifier,
            )
            .order_by(TestRun.completed_at.desc())
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def get_stability_signal(
        self, session: AsyncSession, repository: str, test_identifier: str
    ) -> TestStabilitySignal | None:
        return await session.get(TestStabilitySignal, (test_identifier, repository))

    async def get_recent_durations(
        self, session: AsyncSession, repository: str, test_identifier: str, limit: int = 20
    ) -> list[int]:
        stmt = (
            select(TestCaseResult.duration_ms)
            .join(TestRun, TestRun.id == TestCaseResult.test_run_id)
            .where(
                TestRun.repository == repository,
                TestCaseResult.test_identifier == test_identifier,
            )
            .order_by(TestRun.completed_at.desc())
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def get_duration_signal(
        self, session: AsyncSession, repository: str, test_identifier: str
    ) -> TestDurationSignal | None:
        return await session.get(TestDurationSignal, (test_identifier, repository))

    async def upsert_duration_signal(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        test_identifier: str,
        median_duration_ms: float,
        sample_size: int,
        computed_at: datetime,
    ) -> TestDurationSignal:
        existing = await self.get_duration_signal(session, repository, test_identifier)
        if existing is not None:
            existing.median_duration_ms = median_duration_ms
            existing.sample_size = sample_size
            existing.last_computed_at = computed_at
            return existing

        signal = TestDurationSignal(
            test_identifier=test_identifier,
            repository=repository,
            installation_id=installation_id,
            median_duration_ms=median_duration_ms,
            sample_size=sample_size,
            last_computed_at=computed_at,
        )
        session.add(signal)
        return signal

    async def list_slow_tests(
        self,
        session: AsyncSession,
        repository: str,
        *,
        flaky_threshold: float = 0.2,
        limit: int = 20,
    ) -> list[tuple[TestDurationSignal, float | None]]:
        stmt = (
            select(TestDurationSignal, TestStabilitySignal.flakiness_score)
            .outerjoin(
                TestStabilitySignal,
                (TestStabilitySignal.repository == TestDurationSignal.repository)
                & (TestStabilitySignal.test_identifier == TestDurationSignal.test_identifier),
            )
            .where(
                TestDurationSignal.repository == repository,
                (TestStabilitySignal.flakiness_score.is_(None))
                | (TestStabilitySignal.flakiness_score <= flaky_threshold),
            )
            .order_by(TestDurationSignal.median_duration_ms.desc())
            .limit(limit)
        )
        return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]

    async def upsert_stability_signal(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        test_identifier: str,
        flakiness_score: float,
        sample_size: int,
        computed_at: datetime,
    ) -> TestStabilitySignal:
        existing = await self.get_stability_signal(session, repository, test_identifier)
        if existing is not None:
            existing.flakiness_score = flakiness_score
            existing.sample_size = sample_size
            existing.last_computed_at = computed_at
            return existing

        signal = TestStabilitySignal(
            test_identifier=test_identifier,
            repository=repository,
            installation_id=installation_id,
            flakiness_score=flakiness_score,
            sample_size=sample_size,
            last_computed_at=computed_at,
        )
        session.add(signal)
        return signal

    async def get_file_coverage_signal(
        self, session: AsyncSession, repository: str, file_path: str
    ) -> FileCoverageSignal | None:
        return await session.get(FileCoverageSignal, (file_path, repository))

    async def upsert_file_coverage_signal(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        file_path: str,
        commit_sha: str,
        lines_covered: int,
        lines_total: int,
        coverage_pct: float,
        computed_at: datetime,
    ) -> FileCoverageSignal:
        existing = await self.get_file_coverage_signal(session, repository, file_path)
        if existing is not None:
            existing.commit_sha = commit_sha
            existing.lines_covered = lines_covered
            existing.lines_total = lines_total
            existing.coverage_pct = coverage_pct
            existing.computed_at = computed_at
            return existing

        signal = FileCoverageSignal(
            file_path=file_path,
            repository=repository,
            installation_id=installation_id,
            commit_sha=commit_sha,
            lines_covered=lines_covered,
            lines_total=lines_total,
            coverage_pct=coverage_pct,
            computed_at=computed_at,
        )
        session.add(signal)
        return signal

    async def get_recently_changed_files(
        self, session: AsyncSession, repository: str, pr_window: int = 20
    ) -> list[str]:
        stmt = (
            select(PrChangedFilesProjection.changed_file_paths)
            .where(PrChangedFilesProjection.repository == repository)
            .order_by(PrChangedFilesProjection.received_at.desc())
            .limit(pr_window)
        )
        rows = (await session.execute(stmt)).scalars().all()
        seen: dict[str, None] = {}
        for changed_file_paths in rows:
            for file_path in changed_file_paths:
                seen.setdefault(file_path, None)
        return list(seen)

    async def list_coverage_gaps(
        self,
        session: AsyncSession,
        repository: str,
        *,
        pr_window: int = 20,
        limit: int = 20,
    ) -> list[tuple[str, FileCoverageSignal | None]]:
        recently_changed = await self.get_recently_changed_files(session, repository, pr_window)
        if not recently_changed:
            return []

        stmt = select(FileCoverageSignal).where(
            FileCoverageSignal.repository == repository,
            FileCoverageSignal.file_path.in_(recently_changed),
        )
        signals_by_path = {
            signal.file_path: signal for signal in (await session.execute(stmt)).scalars().all()
        }

        entries = [(file_path, signals_by_path.get(file_path)) for file_path in recently_changed]
        entries.sort(
            key=lambda entry: (
                entry[1] is not None,
                entry[1].coverage_pct if entry[1] is not None else 0.0,
            )
        )
        return entries[:limit]
