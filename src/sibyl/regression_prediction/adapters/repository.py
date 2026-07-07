import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.regression_prediction.adapters.db_models import (
    HistoricalRegressionProjection,
    RegressionPredictionResult,
)


class RegressionPredictionRepository:
    async def upsert_historical_regression(
        self,
        session: AsyncSession,
        *,
        failure_event_id: uuid.UUID,
        installation_id: uuid.UUID,
        repository: str,
        file_path: str,
        hypothesis_text: str,
        confidence: float,
        occurred_at: datetime,
    ) -> HistoricalRegressionProjection:
        existing = await session.get(HistoricalRegressionProjection, failure_event_id)
        if existing is not None:
            existing.file_path = file_path
            existing.hypothesis_text = hypothesis_text
            existing.confidence = confidence
            existing.occurred_at = occurred_at
            return existing

        projection = HistoricalRegressionProjection(
            failure_event_id=failure_event_id,
            installation_id=installation_id,
            repository=repository,
            file_path=file_path,
            hypothesis_text=hypothesis_text,
            confidence=confidence,
            occurred_at=occurred_at,
        )
        session.add(projection)
        return projection

    async def get_historical_regressions_by_files(
        self, session: AsyncSession, repository: str, file_paths: list[str]
    ) -> list[HistoricalRegressionProjection]:
        if not file_paths:
            return []
        stmt = select(HistoricalRegressionProjection).where(
            HistoricalRegressionProjection.repository == repository,
            HistoricalRegressionProjection.file_path.in_(file_paths),
        )
        return list((await session.execute(stmt)).scalars().all())

    async def save_prediction(
        self,
        session: AsyncSession,
        *,
        installation_id: uuid.UUID,
        repository: str,
        pr_number: int,
        head_sha: str,
        regression_probability: float,
        rationale: str,
        contributing_signals: list[dict[str, object]],
        llm_model: str,
        llm_tokens_used: int,
        llm_latency_ms: int,
        computed_at: datetime,
    ) -> RegressionPredictionResult:
        record = RegressionPredictionResult(
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            regression_probability=regression_probability,
            rationale=rationale,
            contributing_signals=contributing_signals,
            llm_model=llm_model,
            llm_tokens_used=llm_tokens_used,
            llm_latency_ms=llm_latency_ms,
            computed_at=computed_at,
        )
        session.add(record)
        return record

    async def get_latest_prediction(
        self, session: AsyncSession, repository: str, pr_number: int
    ) -> RegressionPredictionResult | None:
        stmt = (
            select(RegressionPredictionResult)
            .where(
                RegressionPredictionResult.repository == repository,
                RegressionPredictionResult.pr_number == pr_number,
            )
            .order_by(RegressionPredictionResult.computed_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()
