from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sibyl.engineering_metrics.adapters.repository import EngineeringMetricsRepository
from sibyl.engineering_metrics.domain.metrics import compute_ci_success_rate, compute_median
from sibyl.identity.auth import require_scope

router = APIRouter()
_repository = EngineeringMetricsRepository()


class EngineeringMetricsResponse(BaseModel):
    windowDays: int
    pullRequestCount: int
    medianPrCycleTimeHours: float | None
    ciRunCount: int
    ciSuccessRate: float | None
    medianCiDurationMinutes: float | None


@router.get(
    "/repositories/{owner}/{repo}/engineering-metrics",
    response_model=EngineeringMetricsResponse,
    dependencies=[Depends(require_scope("read:engineering-metrics"))],
)
async def get_engineering_metrics(
    owner: str,
    repo: str,
    request: Request,
    windowDays: int = Query(default=30, ge=1, le=365),
) -> EngineeringMetricsResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    repository = f"{owner}/{repo}"
    since = datetime.now(UTC) - timedelta(days=windowDays)

    async with session_factory() as session:
        pr_lifecycles = await _repository.get_pr_lifecycle_in_window(session, repository, since)
        ci_runs = await _repository.get_ci_runs_in_window(session, repository, since)

    cycle_time_hours = [
        (pr.merged_at - pr.opened_at).total_seconds() / 3600
        for pr in pr_lifecycles
        if pr.merged and pr.merged_at is not None
    ]
    ci_duration_minutes = [
        (run.completed_at - run.started_at).total_seconds() / 60 for run in ci_runs
    ]
    ci_failed_counts = [run.failed_count for run in ci_runs]

    return EngineeringMetricsResponse(
        windowDays=windowDays,
        pullRequestCount=len(pr_lifecycles),
        medianPrCycleTimeHours=compute_median(cycle_time_hours),
        ciRunCount=len(ci_runs),
        ciSuccessRate=compute_ci_success_rate(ci_failed_counts),
        medianCiDurationMinutes=compute_median(ci_duration_minutes),
    )
