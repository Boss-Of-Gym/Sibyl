from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sibyl.dependency_analysis.adapters.repository import DependencyAnalysisRepository
from sibyl.dependency_analysis.domain.diffing import diff_packages
from sibyl.identity.auth import require_scope
from sibyl.platform.errors import ProblemException

router = APIRouter()
_repository = DependencyAnalysisRepository()


class DependencyPackageResponse(BaseModel):
    name: str
    version: str
    direct: bool


class DependencyManifestSnapshotResponse(BaseModel):
    ecosystem: str
    commitSha: str
    packages: list[DependencyPackageResponse]
    receivedAt: datetime


class DependenciesResponse(BaseModel):
    items: list[DependencyManifestSnapshotResponse]


class DependencyChangeResponse(BaseModel):
    name: str
    changeType: str
    oldVersion: str | None
    newVersion: str | None
    severity: str


class DependencyChangesResponse(BaseModel):
    ecosystem: str
    fromCommitSha: str
    toCommitSha: str
    changes: list[DependencyChangeResponse]


@router.get(
    "/repositories/{owner}/{repo}/dependencies",
    response_model=DependenciesResponse,
    dependencies=[Depends(require_scope("read:dependency-analysis"))],
)
async def list_dependency_manifests(
    owner: str, repo: str, request: Request
) -> DependenciesResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        snapshots = await _repository.get_latest_snapshots_by_repository(
            session, f"{owner}/{repo}"
        )

    return DependenciesResponse(
        items=[
            DependencyManifestSnapshotResponse(
                ecosystem=snapshot.ecosystem,
                commitSha=snapshot.commit_sha,
                packages=[
                    DependencyPackageResponse.model_validate(package)
                    for package in snapshot.packages
                ],
                receivedAt=snapshot.received_at,
            )
            for snapshot in snapshots
        ]
    )


@router.get(
    "/repositories/{owner}/{repo}/dependencies/changes",
    response_model=DependencyChangesResponse,
    dependencies=[Depends(require_scope("read:dependency-analysis"))],
)
async def list_dependency_changes(
    owner: str, repo: str, request: Request, ecosystem: str = Query(...)
) -> DependencyChangesResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        recent = await _repository.get_recent_snapshots(session, f"{owner}/{repo}", ecosystem)

    if len(recent) < 2:
        raise ProblemException(
            status_code=404,
            title="Not enough manifest history to compare for this repository/ecosystem",
            code="SIBYL_NOT_FOUND",
        )

    newest, previous = recent[0], recent[1]
    changes = diff_packages(previous.packages, newest.packages)

    return DependencyChangesResponse(
        ecosystem=ecosystem,
        fromCommitSha=previous.commit_sha,
        toCommitSha=newest.commit_sha,
        changes=[
            DependencyChangeResponse(
                name=change.name,
                changeType=change.change_type,
                oldVersion=change.old_version,
                newVersion=change.new_version,
                severity=change.severity,
            )
            for change in changes
        ],
    )
