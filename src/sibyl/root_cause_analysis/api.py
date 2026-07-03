import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sibyl.identity.auth import require_scope
from sibyl.platform.errors import ProblemException
from sibyl.root_cause_analysis.adapters.repository import RootCauseAnalysisRepository

router = APIRouter()
_repository = RootCauseAnalysisRepository()


class RootCauseHypothesisResponse(BaseModel):
    failureEventId: uuid.UUID
    hypothesisText: str
    confidence: float
    suspectedCommitSha: str | None
    suspectedFilePath: str | None
    llmModel: str
    computedAt: datetime


@router.get(
    "/repositories/{owner}/{repo}/failures/{failureEventId}/root-cause",
    response_model=RootCauseHypothesisResponse,
    dependencies=[Depends(require_scope("read:root-cause"))],
)
async def get_root_cause_hypothesis(
    owner: str, repo: str, failureEventId: uuid.UUID, request: Request
) -> RootCauseHypothesisResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        failure_event = await _repository.get_failure_event(session, failureEventId)
        if failure_event is None or failure_event.repository != f"{owner}/{repo}":
            raise ProblemException(
                status_code=404,
                title="No failure event found for this repository",
                code="SIBYL_NOT_FOUND",
            )

        hypothesis = await _repository.get_latest_hypothesis(session, failureEventId)

    if hypothesis is None:
        raise ProblemException(
            status_code=202,
            title="Root cause hypothesis has not been computed yet",
            code="SIBYL_ANALYSIS_NOT_READY",
        )

    return RootCauseHypothesisResponse(
        failureEventId=failure_event.id,
        hypothesisText=hypothesis.hypothesis_text,
        confidence=hypothesis.confidence,
        suspectedCommitSha=hypothesis.suspected_commit_sha,
        suspectedFilePath=hypothesis.suspected_file_path,
        llmModel=hypothesis.llm_model,
        computedAt=hypothesis.computed_at,
    )
