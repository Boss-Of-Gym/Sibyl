import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.identity.adapters.repository import InstallationRepository
from sibyl.platform.github.app_auth import GitHubAppAuthenticator
from sibyl.platform.github.checks_client import CheckConclusion, GitHubChecksClient

CHECK_NAME = "Sibyl / PR Analysis"


class UnknownInstallation(Exception):
    pass


def _conclusion_for(score: float, explanation_unavailable: bool) -> CheckConclusion:
    if explanation_unavailable:
        return "neutral"
    if score < 0.3:
        return "success"
    if score < 0.7:
        return "neutral"
    return "action_required"


def _title_for(conclusion: CheckConclusion) -> str:
    return {
        "success": "Low risk",
        "neutral": "Moderate risk",
        "action_required": "High risk — review recommended",
    }.get(conclusion, "Risk assessment")


class PrAnalysisChecksNotifier:
    def __init__(
        self,
        authenticator: GitHubAppAuthenticator,
        checks_client: GitHubChecksClient,
        installation_repository: InstallationRepository,
    ):
        self._authenticator = authenticator
        self._checks_client = checks_client
        self._installation_repository = installation_repository

    async def handle_pr_analysis_completed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        installation = await self._installation_repository.get_by_id(session, installation_id)
        if installation is None:
            raise UnknownInstallation(str(installation_id))

        token = await self._authenticator.get_installation_token(
            installation.github_installation_id
        )
        conclusion = _conclusion_for(payload["score"], payload["explanation_unavailable"])
        summary = payload["rationale"] or "Explanation unavailable — risk signal only."

        await self._checks_client.create_check_run(
            installation_token=token,
            repository=payload["repository"],
            name=CHECK_NAME,
            head_sha=payload["head_sha"],
            conclusion=conclusion,
            title=_title_for(conclusion),
            summary=summary,
        )
