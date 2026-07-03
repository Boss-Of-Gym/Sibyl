from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sibyl.identity.auth import require_scope
from sibyl.platform.errors import ProblemException
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository

router = APIRouter()
_repository = TestIntelligenceRepository()


class TestImpactResponse(BaseModel):
    prNumber: int
    affectedTests: list[str]
    computedAt: datetime


class TestStabilityResponse(BaseModel):
    testIdentifier: str
    flakinessScore: float
    sampleSize: int
    lastComputedAt: datetime


class SlowTestEntryResponse(BaseModel):
    testIdentifier: str
    medianDurationMs: float
    sampleSize: int
    flakinessScore: float | None
    lastComputedAt: datetime


class SlowTestsResponse(BaseModel):
    items: list[SlowTestEntryResponse]


class CoverageGapEntryResponse(BaseModel):
    filePath: str
    coveragePct: float | None
    linesCovered: int | None
    linesTotal: int | None
    lastComputedAt: datetime | None


class CoverageGapsResponse(BaseModel):
    items: list[CoverageGapEntryResponse]


@router.get(
    "/repositories/{owner}/{repo}/pulls/{prNumber}/test-impact",
    response_model=TestImpactResponse,
    dependencies=[Depends(require_scope("read:test-intelligence"))],
)
async def get_test_impact(
    owner: str, repo: str, prNumber: int, request: Request
) -> TestImpactResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        impact = await _repository.get_latest_test_impact(session, f"{owner}/{repo}", prNumber)

    if impact is None:
        raise ProblemException(
            status_code=404,
            title="No test impact analysis found for this pull request",
            code="SIBYL_NOT_FOUND",
        )

    return TestImpactResponse(
        prNumber=impact.pr_number,
        affectedTests=[t.test_identifier for t in impact.affected_tests],
        computedAt=impact.computed_at,
    )


@router.get(
    "/repositories/{owner}/{repo}/tests/{testIdentifier:path}/stability",
    response_model=TestStabilityResponse,
    dependencies=[Depends(require_scope("read:test-intelligence"))],
)
async def get_test_stability(
    owner: str, repo: str, testIdentifier: str, request: Request
) -> TestStabilityResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        signal = await _repository.get_stability_signal(
            session, f"{owner}/{repo}", testIdentifier
        )

    if signal is None:
        raise ProblemException(
            status_code=404,
            title="No stability signal found for this test",
            code="SIBYL_NOT_FOUND",
        )

    return TestStabilityResponse(
        testIdentifier=signal.test_identifier,
        flakinessScore=signal.flakiness_score,
        sampleSize=signal.sample_size,
        lastComputedAt=signal.last_computed_at,
    )


@router.get(
    "/repositories/{owner}/{repo}/ci-cd/slow-tests",
    response_model=SlowTestsResponse,
    dependencies=[Depends(require_scope("read:test-intelligence"))],
)
async def list_slow_tests(
    owner: str, repo: str, request: Request, limit: int = Query(default=20, ge=1, le=100)
) -> SlowTestsResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        rows = await _repository.list_slow_tests(session, f"{owner}/{repo}", limit=limit)

    return SlowTestsResponse(
        items=[
            SlowTestEntryResponse(
                testIdentifier=signal.test_identifier,
                medianDurationMs=signal.median_duration_ms,
                sampleSize=signal.sample_size,
                flakinessScore=flakiness_score,
                lastComputedAt=signal.last_computed_at,
            )
            for signal, flakiness_score in rows
        ]
    )


@router.get(
    "/repositories/{owner}/{repo}/coverage/gaps",
    response_model=CoverageGapsResponse,
    dependencies=[Depends(require_scope("read:test-intelligence"))],
)
async def list_coverage_gaps(
    owner: str, repo: str, request: Request, limit: int = Query(default=20, ge=1, le=100)
) -> CoverageGapsResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        rows = await _repository.list_coverage_gaps(session, f"{owner}/{repo}", limit=limit)

    return CoverageGapsResponse(
        items=[
            CoverageGapEntryResponse(
                filePath=file_path,
                coveragePct=signal.coverage_pct if signal is not None else None,
                linesCovered=signal.lines_covered if signal is not None else None,
                linesTotal=signal.lines_total if signal is not None else None,
                lastComputedAt=signal.computed_at if signal is not None else None,
            )
            for file_path, signal in rows
        ]
    )
