import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.dependency_analysis.adapters.repository import DependencyAnalysisRepository
from sibyl.dependency_analysis.domain.models import DependencyManifestReport


class DependencyAnalysisService:
    def __init__(self, repository: DependencyAnalysisRepository):
        self._repository = repository

    async def handle_manifest_received(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        report = DependencyManifestReport.model_validate(payload)

        await self._repository.upsert_manifest_snapshot(
            session,
            installation_id=installation_id,
            repository=report.repository,
            commit_sha=report.commit_sha,
            ecosystem=report.ecosystem,
            packages=[package.model_dump() for package in report.packages],
            received_at=datetime.now(UTC),
        )

        await session.commit()
