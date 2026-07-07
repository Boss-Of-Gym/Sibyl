import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.root_cause_analysis.adapters.db_models import (
    FailureEvent,
    FlakySignalProjection,
    PrContextProjection,
    RootCauseHypothesis,
    TestImpactProjection,
)


class RootCauseAnalysisRepository:
    async def upsert_failure_event(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        test_identifier: str,
        commit_sha: str,
        ci_run_id: int,
        detected_at: datetime,
    ) -> FailureEvent:
        stmt = select(FailureEvent).where(
            FailureEvent.repository == repository,
            FailureEvent.test_identifier == test_identifier,
            FailureEvent.commit_sha == commit_sha,
            FailureEvent.ci_run_id == ci_run_id,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        failure_event = FailureEvent(
            installation_id=installation_id,
            repository=repository,
            test_identifier=test_identifier,
            commit_sha=commit_sha,
            ci_run_id=ci_run_id,
            detected_at=detected_at,
        )
        session.add(failure_event)
        await session.flush()
        return failure_event

    async def get_failure_event(
        self, session: AsyncSession, failure_event_id: uuid.UUID
    ) -> FailureEvent | None:
        return await session.get(FailureEvent, failure_event_id)

    async def get_failure_events_by_commit(
        self, session: AsyncSession, repository: str, commit_sha: str
    ) -> list[FailureEvent]:
        stmt = select(FailureEvent).where(
            FailureEvent.repository == repository, FailureEvent.commit_sha == commit_sha
        )
        return list((await session.execute(stmt)).scalars().all())

    async def get_latest_hypothesis(
        self, session: AsyncSession, failure_event_id: uuid.UUID
    ) -> RootCauseHypothesis | None:
        stmt = (
            select(RootCauseHypothesis)
            .where(RootCauseHypothesis.failure_event_id == failure_event_id)
            .order_by(RootCauseHypothesis.computed_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def save_hypothesis(
        self,
        session: AsyncSession,
        *,
        failure_event_id: uuid.UUID,
        hypothesis_text: str,
        confidence: float,
        suspected_commit_sha: str | None,
        suspected_file_path: str | None,
        llm_model: str,
        llm_tokens_used: int,
        llm_latency_ms: int,
        computed_at: datetime,
    ) -> RootCauseHypothesis:
        hypothesis = RootCauseHypothesis(
            failure_event_id=failure_event_id,
            hypothesis_text=hypothesis_text,
            confidence=confidence,
            suspected_commit_sha=suspected_commit_sha,
            suspected_file_path=suspected_file_path,
            llm_model=llm_model,
            llm_tokens_used=llm_tokens_used,
            llm_latency_ms=llm_latency_ms,
            computed_at=computed_at,
        )
        session.add(hypothesis)
        await session.flush()
        return hypothesis

    async def upsert_pr_context_projection(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        pr_number: int,
        head_sha: str,
        risk_score: float | None,
        explanation_unavailable: bool,
        received_at: datetime,
    ) -> PrContextProjection:
        existing = await self.get_pr_context(session, repository, pr_number)
        if existing is not None:
            existing.head_sha = head_sha
            existing.risk_score = risk_score
            existing.explanation_unavailable = explanation_unavailable
            existing.received_at = received_at
            return existing

        projection = PrContextProjection(
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            risk_score=risk_score,
            explanation_unavailable=explanation_unavailable,
            received_at=received_at,
        )
        session.add(projection)
        await session.flush()
        return projection

    async def get_pr_context(
        self, session: AsyncSession, repository: str, pr_number: int
    ) -> PrContextProjection | None:
        stmt = select(PrContextProjection).where(
            PrContextProjection.repository == repository,
            PrContextProjection.pr_number == pr_number,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_pr_context_by_head_sha(
        self, session: AsyncSession, repository: str, head_sha: str
    ) -> PrContextProjection | None:
        stmt = select(PrContextProjection).where(
            PrContextProjection.repository == repository,
            PrContextProjection.head_sha == head_sha,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def upsert_test_impact_projection(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        pr_number: int,
        affected_tests: list[str],
        received_at: datetime,
    ) -> TestImpactProjection:
        existing = await self.get_test_impact(session, repository, pr_number)
        if existing is not None:
            existing.affected_tests = affected_tests
            existing.received_at = received_at
            return existing

        projection = TestImpactProjection(
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            affected_tests=affected_tests,
            received_at=received_at,
        )
        session.add(projection)
        await session.flush()
        return projection

    async def get_test_impact(
        self, session: AsyncSession, repository: str, pr_number: int
    ) -> TestImpactProjection | None:
        stmt = select(TestImpactProjection).where(
            TestImpactProjection.repository == repository,
            TestImpactProjection.pr_number == pr_number,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def upsert_flaky_signal(
        self,
        session: AsyncSession,
        *,
        repository: str,
        test_identifier: str,
        flakiness_score: float,
        updated_at: datetime,
    ) -> FlakySignalProjection:
        existing = await session.get(FlakySignalProjection, (test_identifier, repository))
        if existing is not None:
            existing.flakiness_score = flakiness_score
            existing.updated_at = updated_at
            return existing

        projection = FlakySignalProjection(
            test_identifier=test_identifier,
            repository=repository,
            flakiness_score=flakiness_score,
            updated_at=updated_at,
        )
        session.add(projection)
        return projection

    async def get_flaky_signal(
        self, session: AsyncSession, repository: str, test_identifier: str
    ) -> FlakySignalProjection | None:
        return await session.get(FlakySignalProjection, (test_identifier, repository))
