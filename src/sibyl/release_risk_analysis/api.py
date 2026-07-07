from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sibyl.identity.auth import require_scope
from sibyl.platform.errors import ProblemException
from sibyl.release_risk_analysis.adapters.repository import ReleaseRiskAnalysisRepository

router = APIRouter()
_repository = ReleaseRiskAnalysisRepository()


class ReleaseRiskResponse(BaseModel):
    prNumber: int
    headSha: str
    riskScore: float
    consideredSignals: list[str]
    regressionProbability: float | None
    ciSuccessRate: float | None
    coveragePct: float | None
    computedAt: datetime


@router.get(
    "/repositories/{owner}/{repo}/pulls/{prNumber}/release-risk",
    response_model=ReleaseRiskResponse,
    dependencies=[Depends(require_scope("read:release-risk"))],
)
async def get_release_risk(
    owner: str, repo: str, prNumber: int, request: Request
) -> ReleaseRiskResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        assessment = await _repository.get_latest_assessment(
            session, f"{owner}/{repo}", prNumber
        )

    if assessment is None:
        raise ProblemException(
            status_code=404,
            title="No release risk assessment found for this pull request",
            code="SIBYL_NOT_FOUND",
        )

    return ReleaseRiskResponse(
        prNumber=assessment.pr_number,
        headSha=assessment.head_sha,
        riskScore=assessment.risk_score,
        consideredSignals=assessment.considered_signals,
        regressionProbability=assessment.regression_probability,
        ciSuccessRate=assessment.ci_success_rate,
        coveragePct=assessment.coverage_pct,
        computedAt=assessment.computed_at,
    )
