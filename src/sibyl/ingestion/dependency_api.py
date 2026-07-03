from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sibyl.identity.adapters.repository import InstallationRepository
from sibyl.identity.auth import TokenPayload, require_scope
from sibyl.ingestion.adapters.db_models import IngestionOutboxEvent
from sibyl.platform.errors import ProblemException
from sibyl.platform.events.outbox import OutboxRepository

router = APIRouter()
_outbox_repository = OutboxRepository(IngestionOutboxEvent)
_installation_repository = InstallationRepository()


class DependencyPackageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    version: str
    direct: bool


class DependencyManifestReportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    repository: str
    commit_sha: str = Field(alias="commitSha")
    ecosystem: str
    packages: list[DependencyPackageRequest]


@router.post("/ingest/dependency-manifest", status_code=202)
async def ingest_dependency_manifest(
    report: DependencyManifestReportRequest,
    request: Request,
    token: TokenPayload = Depends(require_scope("write:dependency-manifests")),
) -> None:
    organization_login = report.repository.split("/", 1)[0]

    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        installation = await _installation_repository.get_by_organization_login(
            session, organization_login
        )
        if installation is None:
            raise ProblemException(
                status_code=404,
                title="No installation found for this repository's organization",
                code="SIBYL_NOT_FOUND",
            )

        if token.installation_id != str(installation.id):
            raise ProblemException(
                status_code=403,
                title="Token is not authorized for this installation",
                code="SIBYL_INSTALLATION_MISMATCH",
            )

        await _outbox_repository.add(
            session,
            event_type="ingestion.dependency-manifest-received",
            installation_id=installation.id,
            payload=report.model_dump(mode="json"),
            occurred_at=datetime.now(UTC),
        )
