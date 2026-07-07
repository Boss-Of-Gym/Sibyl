import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.pr_analysis.adapters.db_models import (
    LocalFlakySignalProjection,
    PrRiskAssessment,
    PullRequest,
)
from sibyl.pr_analysis.domain.models import RiskAssessment


class PrAnalysisRepository:
    async def upsert_pull_request(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        pr_number: int,
        head_sha: str,
        base_sha: str,
        author_login: str,
        files_changed: int,
        additions: int,
        deletions: int,
        opened_at: datetime,
    ) -> PullRequest:
        stmt = select(PullRequest).where(
            PullRequest.repository == repository, PullRequest.pr_number == pr_number
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.head_sha = head_sha
            existing.files_changed = files_changed
            existing.additions = additions
            existing.deletions = deletions
            return existing

        pull_request = PullRequest(
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            base_sha=base_sha,
            author_login=author_login,
            files_changed=files_changed,
            additions=additions,
            deletions=deletions,
            opened_at=opened_at,
        )
        session.add(pull_request)
        await session.flush()
        return pull_request

    async def add_risk_assessment(
        self,
        session: AsyncSession,
        pull_request: PullRequest,
        assessment: RiskAssessment,
        computed_at: datetime,
    ) -> PrRiskAssessment:
        record = PrRiskAssessment(
            pull_request_id=pull_request.id,
            score=assessment.score,
            rationale=assessment.rationale,
            contributing_factors=[f.model_dump() for f in assessment.contributing_factors],
            llm_model=assessment.llm_model,
            llm_tokens_used=assessment.llm_tokens_used,
            llm_latency_ms=assessment.llm_latency_ms,
            computed_at=computed_at,
        )
        session.add(record)
        return record

    async def get_latest_assessment(
        self, session: AsyncSession, repository: str, pr_number: int
    ) -> tuple[PullRequest, PrRiskAssessment] | None:
        stmt = (
            select(PullRequest, PrRiskAssessment)
            .join(PrRiskAssessment, PrRiskAssessment.pull_request_id == PullRequest.id)
            .where(PullRequest.repository == repository, PullRequest.pr_number == pr_number)
            .order_by(PrRiskAssessment.computed_at.desc())
            .limit(1)
        )
        result = (await session.execute(stmt)).first()
        return (result[0], result[1]) if result is not None else None

    async def get_flaky_signals(
        self, session: AsyncSession, repository: str
    ) -> list[LocalFlakySignalProjection]:
        stmt = select(LocalFlakySignalProjection).where(
            LocalFlakySignalProjection.repository == repository
        )
        return list((await session.execute(stmt)).scalars().all())

    async def upsert_local_flaky_signal(
        self,
        session: AsyncSession,
        *,
        repository: str,
        test_identifier: str,
        flakiness_score: float,
        updated_at: datetime,
    ) -> LocalFlakySignalProjection:
        existing = await session.get(
            LocalFlakySignalProjection, (test_identifier, repository)
        )
        if existing is not None:
            existing.flakiness_score = flakiness_score
            existing.updated_at = updated_at
            return existing

        projection = LocalFlakySignalProjection(
            test_identifier=test_identifier,
            repository=repository,
            flakiness_score=flakiness_score,
            updated_at=updated_at,
        )
        session.add(projection)
        return projection
