import json
import uuid

import httpx
import pytest

from sibyl.identity.adapters.repository import InstallationRepository
from sibyl.platform.github.app_auth import GitHubAppAuthenticator
from sibyl.platform.github.checks_client import GitHubChecksClient
from sibyl.regression_prediction.adapters.checks_notifier import (
    RegressionPredictionChecksNotifier,
    UnknownInstallation,
)
from tests.contract.test_github_app_auth import PRIVATE_KEY_PEM

PAYLOAD = {
    "repository": "acme/widgets",
    "pr_number": 1,
    "head_sha": "sha-x",
    "regression_probability": 0.75,
    "rationale": "Touches historically fragile payment code.",
    "explanation_unavailable": False,
}


def _mock_client(check_run_requests: list[httpx.Request]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if "access_tokens" in str(request.url):
            return httpx.Response(
                201, json={"token": "ghs_test", "expires_at": "2099-01-01T00:00:00Z"}
            )
        check_run_requests.append(request)
        return httpx.Response(201, json={"id": 1})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_posts_action_required_for_high_probability(db_session, redis_client):
    installation = await InstallationRepository().get_or_create_by_github_id(
        db_session, github_installation_id=424245, organization_login="acme"
    )
    await db_session.commit()

    check_run_requests: list[httpx.Request] = []
    http_client = _mock_client(check_run_requests)
    authenticator = GitHubAppAuthenticator("app-1", PRIVATE_KEY_PEM, redis_client, http_client)
    notifier = RegressionPredictionChecksNotifier(
        authenticator, GitHubChecksClient(http_client), InstallationRepository()
    )

    await notifier.handle_prediction_ready(db_session, installation.id, PAYLOAD)

    assert len(check_run_requests) == 1
    body = json.loads(check_run_requests[0].content)
    assert body["conclusion"] == "action_required"


async def test_posts_success_for_low_probability(db_session, redis_client):
    installation = await InstallationRepository().get_or_create_by_github_id(
        db_session, github_installation_id=424246, organization_login="acme"
    )
    await db_session.commit()

    check_run_requests: list[httpx.Request] = []
    http_client = _mock_client(check_run_requests)
    authenticator = GitHubAppAuthenticator("app-1", PRIVATE_KEY_PEM, redis_client, http_client)
    notifier = RegressionPredictionChecksNotifier(
        authenticator, GitHubChecksClient(http_client), InstallationRepository()
    )

    await notifier.handle_prediction_ready(
        db_session, installation.id, {**PAYLOAD, "regression_probability": 0.1}
    )

    assert len(check_run_requests) == 1
    body = json.loads(check_run_requests[0].content)
    assert body["conclusion"] == "success"


async def test_summary_falls_back_when_explanation_unavailable(db_session, redis_client):
    installation = await InstallationRepository().get_or_create_by_github_id(
        db_session, github_installation_id=424247, organization_login="acme"
    )
    await db_session.commit()

    check_run_requests: list[httpx.Request] = []
    http_client = _mock_client(check_run_requests)
    authenticator = GitHubAppAuthenticator("app-1", PRIVATE_KEY_PEM, redis_client, http_client)
    notifier = RegressionPredictionChecksNotifier(
        authenticator, GitHubChecksClient(http_client), InstallationRepository()
    )

    await notifier.handle_prediction_ready(
        db_session, installation.id, {**PAYLOAD, "explanation_unavailable": True}
    )

    assert len(check_run_requests) == 1
    body = check_run_requests[0].content.decode()
    assert "unavailable" in body.lower()


async def test_raises_for_unknown_installation(db_session, redis_client):
    http_client = _mock_client([])
    authenticator = GitHubAppAuthenticator("app-1", PRIVATE_KEY_PEM, redis_client, http_client)
    notifier = RegressionPredictionChecksNotifier(
        authenticator, GitHubChecksClient(http_client), InstallationRepository()
    )

    with pytest.raises(UnknownInstallation):
        await notifier.handle_prediction_ready(db_session, uuid.uuid4(), PAYLOAD)
