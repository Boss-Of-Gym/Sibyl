import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.engineering_metrics.adapters.repository import EngineeringMetricsRepository
from sibyl.engineering_metrics.domain.models import CiRunCompletedReport
from sibyl.platform.events.errors import MalformedEventError


class MalformedPrChangedPayload(MalformedEventError):
    pass


def _extract_pr_lifecycle(
    payload: dict[str, Any],
) -> tuple[str, int, datetime, datetime | None, datetime | None, bool]:
    try:
        pr = payload["pull_request"]
        repository = payload["repository"]["full_name"]
        pr_number = payload["number"]
        opened_at = datetime.fromisoformat(pr["created_at"])
        merged_at = datetime.fromisoformat(pr["merged_at"]) if pr["merged_at"] else None
        closed_at = datetime.fromisoformat(pr["closed_at"]) if pr["closed_at"] else None
        merged = bool(pr["merged"])
    except KeyError as exc:
        raise MalformedPrChangedPayload(str(exc)) from exc
    return repository, pr_number, opened_at, merged_at, closed_at, merged


class EngineeringMetricsService:
    def __init__(self, repository: EngineeringMetricsRepository):
        self._repository = repository

    async def handle_pr_changed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        repository, pr_number, opened_at, merged_at, closed_at, merged = _extract_pr_lifecycle(
            payload
        )

        await self._repository.upsert_pr_lifecycle(
            session,
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            opened_at=opened_at,
            merged_at=merged_at,
            closed_at=closed_at,
            merged=merged,
        )
        await session.commit()

    async def handle_ci_run_completed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        report = CiRunCompletedReport.model_validate(payload)

        passed_count = sum(1 for t in report.tests if t.status == "passed")
        failed_count = sum(1 for t in report.tests if t.status == "failed")
        skipped_count = sum(1 for t in report.tests if t.status == "skipped")

        await self._repository.upsert_ci_run(
            session,
            installation_id=installation_id,
            repository=report.repository,
            ci_run_id=report.ci_run_id,
            commit_sha=report.commit_sha,
            started_at=report.started_at,
            completed_at=report.completed_at,
            passed_count=passed_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        )
        await session.commit()
