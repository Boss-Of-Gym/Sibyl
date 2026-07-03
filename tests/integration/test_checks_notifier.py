import uuid

import httpx
import pytest

from sibyl.identity.adapters.repository import InstallationRepository
from sibyl.platform.github.app_auth import GitHubAppAuthenticator
from sibyl.platform.github.checks_client import GitHubChecksClient
from sibyl.pr_analysis.adapters.checks_notifier import PrAnalysisChecksNotifier, UnknownInstallation
from tests.contract.test_github_app_auth import PRIVATE_KEY_PEM

PAYLOAD = {
    "repository": "acme/widgets",
    "pr_number": 1,
    "head_sha": "sha-x",
    "score": 0.8,
    "rationale": "Touches critical auth code.",
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


async def test_posts_a_check_run_for_a_known_installation(db_session, redis_client):
    installation = await InstallationRepository().get_or_create_by_github_id(
        db_session, github_installation_id=424242, organization_login="acme"
    )
    await db_session.commit()

    check_run_requests: list[httpx.Request] = []
    http_client = _mock_client(check_run_requests)
    authenticator = GitHubAppAuthenticator("app-1", PRIVATE_KEY_PEM, redis_client, http_client)
    notifier = PrAnalysisChecksNotifier(
        authenticator, GitHubChecksClient(http_client), InstallationRepository()
    )

    await notifier.handle_pr_analysis_completed(db_session, installation.id, PAYLOAD)

    assert len(check_run_requests) == 1
    assert "acme/widgets" in str(check_run_requests[0].url)


async def test_raises_for_unknown_installation(db_session, redis_client):
    http_client = _mock_client([])
    authenticator = GitHubAppAuthenticator("app-1", PRIVATE_KEY_PEM, redis_client, http_client)
    notifier = PrAnalysisChecksNotifier(
        authenticator, GitHubChecksClient(http_client), InstallationRepository()
    )

    with pytest.raises(UnknownInstallation):
        await notifier.handle_pr_analysis_completed(db_session, uuid.uuid4(), PAYLOAD)
