from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sibyl.identity.auth import require_scope
from sibyl.platform.errors import ProblemException
from sibyl.regression_prediction.adapters.repository import RegressionPredictionRepository

router = APIRouter()
_repository = RegressionPredictionRepository()


class ContributingSignalResponse(BaseModel):
    signal: str
    weight: float


class RegressionPredictionResponse(BaseModel):
    prNumber: int
    headSha: str
    regressionProbability: float
    rationale: str
    contributingSignals: list[ContributingSignalResponse]
    llmModel: str
    computedAt: datetime


@router.get(
    "/repositories/{owner}/{repo}/pulls/{prNumber}/regression-prediction",
    response_model=RegressionPredictionResponse,
    dependencies=[Depends(require_scope("read:regression-prediction"))],
)
async def get_regression_prediction(
    owner: str, repo: str, prNumber: int, request: Request
) -> RegressionPredictionResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        result = await _repository.get_latest_prediction(session, f"{owner}/{repo}", prNumber)

    if result is None:
        raise ProblemException(
            status_code=404,
            title="No regression prediction found for this pull request",
            code="SIBYL_NOT_FOUND",
        )

    return RegressionPredictionResponse(
        prNumber=result.pr_number,
        headSha=result.head_sha,
        regressionProbability=result.regression_probability,
        rationale=result.rationale,
        contributingSignals=[
            ContributingSignalResponse.model_validate(s) for s in result.contributing_signals
        ],
        llmModel=result.llm_model,
        computedAt=result.computed_at,
    )
