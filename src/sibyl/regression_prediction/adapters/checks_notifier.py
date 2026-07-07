import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.identity.adapters.repository import InstallationRepository
from sibyl.platform.github.app_auth import GitHubAppAuthenticator
from sibyl.platform.github.checks_client import CheckConclusion, GitHubChecksClient

CHECK_NAME = "Sibyl / Regression Prediction"

_HIGH_RISK_THRESHOLD = 0.6


class UnknownInstallation(Exception):
    pass


def _conclusion_for(probability: float, explanation_unavailable: bool) -> CheckConclusion:
    if explanation_unavailable:
        return "neutral"
    return "action_required" if probability >= _HIGH_RISK_THRESHOLD else "success"


class RegressionPredictionChecksNotifier:
    def __init__(
        self,
        authenticator: GitHubAppAuthenticator,
        checks_client: GitHubChecksClient,
        installation_repository: InstallationRepository,
    ):
        self._authenticator = authenticator
        self._checks_client = checks_client
        self._installation_repository = installation_repository

    async def handle_prediction_ready(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        installation = await self._installation_repository.get_by_id(session, installation_id)
        if installation is None:
            raise UnknownInstallation(str(installation_id))

        token = await self._authenticator.get_installation_token(
            installation.github_installation_id
        )

        explanation_unavailable = payload.get("explanation_unavailable", False)
        probability = payload["regression_probability"]
        conclusion = _conclusion_for(probability, explanation_unavailable)
        summary = (
            "Regression prediction unavailable — LLM call did not succeed."
            if explanation_unavailable
            else f"Predicted regression probability: {probability:.0%}. {payload['rationale']}"
        )

        await self._checks_client.create_check_run(
            installation_token=token,
            repository=payload["repository"],
            name=CHECK_NAME,
            head_sha=payload["head_sha"],
            conclusion=conclusion,
            title=f"Regression prediction for PR #{payload['pr_number']}",
            summary=summary,
        )
