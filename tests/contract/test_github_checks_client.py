import json

import httpx
import pytest

from sibyl.platform.github.checks_client import GitHubChecksClient


async def test_create_check_run_sends_expected_request() -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(201, json={"id": 1})

    client = GitHubChecksClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    await client.create_check_run(
        installation_token="ghs_token",
        repository="acme/widgets",
        name="Sibyl / PR Analysis",
        head_sha="abc123",
        conclusion="neutral",
        title="Moderate risk",
        summary="Some rationale.",
    )

    request = captured["request"]
    assert request.method == "POST"
    assert str(request.url) == "https://api.github.com/repos/acme/widgets/check-runs"
    assert request.headers["Authorization"] == "Bearer ghs_token"
    body = json.loads(request.content)
    assert body["head_sha"] == "abc123"
    assert body["conclusion"] == "neutral"
    assert body["output"]["title"] == "Moderate risk"


async def test_create_check_run_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "invalid"})

    client = GitHubChecksClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    with pytest.raises(httpx.HTTPStatusError):
        await client.create_check_run(
            installation_token="t",
            repository="acme/widgets",
            name="n",
            head_sha="s",
            conclusion="success",
            title="t",
            summary="s",
        )
