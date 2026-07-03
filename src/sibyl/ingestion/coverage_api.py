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


class CoverageFileReportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_path: str = Field(alias="filePath")
    lines_covered: int = Field(alias="linesCovered")
    lines_total: int = Field(alias="linesTotal")


class CoverageReportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    repository: str
    commit_sha: str = Field(alias="commitSha")
    files: list[CoverageFileReportRequest]


@router.post("/ingest/coverage-report", status_code=202)
async def ingest_coverage_report(
    report: CoverageReportRequest,
    request: Request,
    token: TokenPayload = Depends(require_scope("write:coverage-reports")),
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
            event_type="ingestion.coverage-report-received",
            installation_id=installation.id,
            payload=report.model_dump(mode="json"),
            occurred_at=datetime.now(UTC),
        )
