import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.release_risk_analysis.adapters.repository import ReleaseRiskAnalysisRepository
from sibyl.release_risk_analysis.domain.models import CiRunCompletedReport
from sibyl.release_risk_analysis.domain.scoring import (
    compute_average_coverage_pct,
    compute_ci_success_rate,
    compute_release_risk_score,
)


class ReleaseRiskAnalysisService:
    def __init__(self, repository: ReleaseRiskAnalysisRepository, outbox: OutboxRepository[Any]):
        self._repository = repository
        self._outbox = outbox

    async def handle_ci_run_completed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        report = CiRunCompletedReport.model_validate(payload)
        passed_count = sum(1 for t in report.tests if t.status == "passed")
        failed_count = sum(1 for t in report.tests if t.status != "passed")

        await self._repository.upsert_ci_run(
            session,
            installation_id=installation_id,
            repository=report.repository,
            ci_run_id=report.ci_run_id,
            passed_count=passed_count,
            failed_count=failed_count,
            completed_at=report.completed_at,
        )
        await session.commit()

    async def handle_coverage_computed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        await self._repository.upsert_coverage_signal(
            session,
            installation_id=installation_id,
            repository=payload["repository"],
            file_path=payload["file_path"],
            coverage_pct=payload["coverage_pct"],
            computed_at=datetime.now(UTC),
        )
        await session.commit()

    async def handle_regression_prediction_completed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        repository = payload["repository"]
        pr_number = payload["pr_number"]
        head_sha = payload["head_sha"]
        regression_probability = payload["regression_probability"]
        now = datetime.now(UTC)

        await self._repository.upsert_regression_signal(
            session,
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            regression_probability=regression_probability,
            computed_at=now,
        )

        recent_ci_runs = await self._repository.get_recent_ci_runs(session, repository)
        ci_success_rate = compute_ci_success_rate([run.failed_count for run in recent_ci_runs])

        coverage_signals = await self._repository.get_coverage_signals(session, repository)
        coverage_pct = compute_average_coverage_pct(
            [signal.coverage_pct for signal in coverage_signals]
        )

        risk_score, considered_signals = compute_release_risk_score(
            regression_probability, ci_success_rate, coverage_pct
        )

        await self._repository.save_assessment(
            session,
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            risk_score=risk_score,
            considered_signals=considered_signals,
            regression_probability=regression_probability,
            ci_success_rate=ci_success_rate,
            coverage_pct=coverage_pct,
            computed_at=now,
        )

        await self._outbox.add(
            session,
            event_type="release-risk.completed",
            installation_id=installation_id,
            payload={
                "repository": repository,
                "pr_number": pr_number,
                "head_sha": head_sha,
                "risk_score": risk_score,
                "considered_signals": considered_signals,
                "regression_probability": regression_probability,
                "ci_success_rate": ci_success_rate,
                "coverage_pct": coverage_pct,
            },
            occurred_at=now,
        )
        await session.commit()
