import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.identity.adapters.repository import InstallationRepository
from sibyl.platform.github.app_auth import GitHubAppAuthenticator
from sibyl.platform.github.checks_client import GitHubChecksClient

CHECK_NAME = "Sibyl / Root Cause Analysis"


class UnknownInstallation(Exception):
    pass


class RootCauseChecksNotifier:
    def __init__(
        self,
        authenticator: GitHubAppAuthenticator,
        checks_client: GitHubChecksClient,
        installation_repository: InstallationRepository,
    ):
        self._authenticator = authenticator
        self._checks_client = checks_client
        self._installation_repository = installation_repository

    async def handle_hypothesis_ready(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        installation = await self._installation_repository.get_by_id(session, installation_id)
        if installation is None:
            raise UnknownInstallation(str(installation_id))

        token = await self._authenticator.get_installation_token(
            installation.github_installation_id
        )
        summary = payload["hypothesis_text"] or (
            "Explanation unavailable — failure detected, no hypothesis synthesized."
        )

        await self._checks_client.create_check_run(
            installation_token=token,
            repository=payload["repository"],
            name=CHECK_NAME,
            head_sha=payload["head_sha"],
            conclusion="neutral",
            title=f"Root cause hypothesis: {payload['test_identifier']}",
            summary=summary,
        )
