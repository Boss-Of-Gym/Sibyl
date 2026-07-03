from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sibyl.identity.auth import require_scope
from sibyl.platform.errors import ProblemException
from sibyl.pr_analysis.adapters.repository import PrAnalysisRepository

router = APIRouter()
_repository = PrAnalysisRepository()


class ContributingFactorResponse(BaseModel):
    factor: str
    weight: float


class PrAnalysisResponse(BaseModel):
    prNumber: int
    headSha: str
    score: float
    rationale: str
    contributingFactors: list[ContributingFactorResponse]
    llmModel: str
    computedAt: datetime


@router.get(
    "/repositories/{owner}/{repo}/pulls/{prNumber}/pr-analysis",
    response_model=PrAnalysisResponse,
    dependencies=[Depends(require_scope("read:pr-analysis"))],
)
async def get_pr_analysis(
    owner: str, repo: str, prNumber: int, request: Request
) -> PrAnalysisResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        result = await _repository.get_latest_assessment(session, f"{owner}/{repo}", prNumber)

    if result is None:
        raise ProblemException(
            status_code=404,
            title="No analysis found for this pull request",
            code="SIBYL_NOT_FOUND",
        )

    pull_request, assessment = result
    return PrAnalysisResponse(
        prNumber=pull_request.pr_number,
        headSha=pull_request.head_sha,
        score=assessment.score,
        rationale=assessment.rationale,
        contributingFactors=[
            ContributingFactorResponse.model_validate(f) for f in assessment.contributing_factors
        ],
        llmModel=assessment.llm_model,
        computedAt=assessment.computed_at,
    )
