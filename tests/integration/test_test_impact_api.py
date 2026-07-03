import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from sibyl.api.app import create_app
from sibyl.identity.auth import create_access_token
from sibyl.platform.config import Settings
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository

JWT_SIGNING_KEY = "test-signing-key-for-test-impact"


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


def _token(scopes: list[str]) -> str:
    return create_access_token(
        subject="test-user",
        scopes=scopes,
        signing_key=JWT_SIGNING_KEY,
        expires_delta=timedelta(minutes=5),
    )


async def test_get_test_impact_returns_200_when_present(
    postgres_container, redis_container, async_engine, db_session
):
    await TestIntelligenceRepository().save_test_impact(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/impact-api-test",
        pr_number=3,
        commit_sha="sha-3",
        affected_tests=["tests/test_a.py::test_a"],
        computed_at=datetime.now(UTC),
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/impact-api-test/pulls/3/test-impact",
                headers={"Authorization": f"Bearer {_token(['read:test-intelligence'])}"},
            )

    assert response.status_code == 200
    assert response.json()["affectedTests"] == ["tests/test_a.py::test_a"]


async def test_get_test_impact_returns_404_when_missing(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/impact-api-test/pulls/9999/test-impact",
                headers={"Authorization": f"Bearer {_token(['read:test-intelligence'])}"},
            )

    assert response.status_code == 404
