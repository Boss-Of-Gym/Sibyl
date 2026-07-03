import uuid
from datetime import timedelta

from httpx import ASGITransport, AsyncClient

from sibyl.api.app import create_app
from sibyl.identity.adapters.repository import InstallationRepository
from sibyl.identity.auth import create_access_token
from sibyl.platform.config import Settings

JWT_SIGNING_KEY = "test-signing-key-for-coverage-ingest"

REPORT_PAYLOAD = {
    "repository": "acme-coverage-test/widgets",
    "commitSha": "sha-coverage",
    "files": [{"filePath": "src/a.py", "linesCovered": 8, "linesTotal": 10}],
}


def _settings(postgres_container, redis_container) -> Settings:
    redis_url = (
        f"redis://{redis_container.get_container_host_ip()}:"
        f"{redis_container.get_exposed_port(6379)}/0"
    )
    return Settings(
        database_url=postgres_container.get_connection_url(),
        redis_url=redis_url,
        jwt_signing_key=JWT_SIGNING_KEY,
    )


def _token(scopes: list[str], installation_id: str | None = None) -> str:
    return create_access_token(
        subject="ci-job",
        scopes=scopes,
        signing_key=JWT_SIGNING_KEY,
        expires_delta=timedelta(minutes=5),
        installation_id=installation_id,
    )


async def test_ingest_returns_202_when_token_matches_the_resolved_installation(
    postgres_container, redis_container, async_engine, db_session
):
    installation = await InstallationRepository().get_or_create_by_github_id(
        db_session, github_installation_id=655, organization_login="acme-coverage-test"
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ingest/coverage-report",
                json=REPORT_PAYLOAD,
                headers={
                    "Authorization": (
                        f"Bearer {_token(['write:coverage-reports'], str(installation.id))}"
                    )
                },
            )

    assert response.status_code == 202


async def test_ingest_returns_403_when_token_has_no_installation_claim(
    postgres_container, redis_container, async_engine, db_session
):
    await InstallationRepository().get_or_create_by_github_id(
        db_session, github_installation_id=656, organization_login="acme-coverage-test-2"
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ingest/coverage-report",
                json={**REPORT_PAYLOAD, "repository": "acme-coverage-test-2/widgets"},
                headers={"Authorization": f"Bearer {_token(['write:coverage-reports'])}"},
            )

    assert response.status_code == 403
    assert response.json()["code"] == "SIBYL_INSTALLATION_MISMATCH"


async def test_ingest_returns_403_when_token_is_scoped_to_a_different_installation(
    postgres_container, redis_container, async_engine, db_session
):
    await InstallationRepository().get_or_create_by_github_id(
        db_session, github_installation_id=657, organization_login="acme-coverage-test-3"
    )
    await db_session.commit()
    someone_elses_installation_id = str(uuid.uuid4())

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ingest/coverage-report",
                json={**REPORT_PAYLOAD, "repository": "acme-coverage-test-3/widgets"},
                headers={
                    "Authorization": (
                        f"Bearer "
                        f"{_token(['write:coverage-reports'], someone_elses_installation_id)}"
                    )
                },
            )

    assert response.status_code == 403
    assert response.json()["code"] == "SIBYL_INSTALLATION_MISMATCH"


async def test_ingest_returns_404_for_unknown_organization(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ingest/coverage-report",
                json={**REPORT_PAYLOAD, "repository": "no-such-org/repo"},
                headers={"Authorization": f"Bearer {_token(['write:coverage-reports'])}"},
            )

    assert response.status_code == 404
    assert response.json()["code"] == "SIBYL_NOT_FOUND"


async def test_ingest_returns_403_without_scope(postgres_container, redis_container, async_engine):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ingest/coverage-report",
                json=REPORT_PAYLOAD,
                headers={"Authorization": f"Bearer {_token(['read:pr-analysis'])}"},
            )

    assert response.status_code == 403
