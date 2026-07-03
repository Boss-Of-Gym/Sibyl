import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from sibyl.api.app import create_app
from sibyl.identity.auth import create_access_token
from sibyl.platform.config import Settings
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository

JWT_SIGNING_KEY = "test-signing-key-for-slow-tests"


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


async def test_list_slow_tests_returns_ranked_non_flaky_tests(
    postgres_container, redis_container, async_engine, db_session
):
    repository = TestIntelligenceRepository()
    now = datetime.now(UTC)
    installation_id = uuid.uuid4()

    await repository.upsert_duration_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/slow-tests-api",
        test_identifier="tests/test_slowest.py::test_it",
        median_duration_ms=9999.0,
        sample_size=10,
        computed_at=now,
    )
    await repository.upsert_duration_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/slow-tests-api",
        test_identifier="tests/test_flaky_and_slow.py::test_it",
        median_duration_ms=8888.0,
        sample_size=10,
        computed_at=now,
    )
    await repository.upsert_stability_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/slow-tests-api",
        test_identifier="tests/test_flaky_and_slow.py::test_it",
        flakiness_score=0.7,
        sample_size=10,
        computed_at=now,
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/slow-tests-api/ci-cd/slow-tests",
                headers={"Authorization": f"Bearer {_token(['read:test-intelligence'])}"},
            )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["testIdentifier"] for item in items] == ["tests/test_slowest.py::test_it"]
    assert items[0]["medianDurationMs"] == 9999.0
    assert items[0]["flakinessScore"] is None


async def test_list_slow_tests_respects_limit_query_param(
    postgres_container, redis_container, async_engine, db_session
):
    repository = TestIntelligenceRepository()
    now = datetime.now(UTC)
    installation_id = uuid.uuid4()

    for i in range(5):
        await repository.upsert_duration_signal(
            db_session,
            installation_id=installation_id,
            repository="acme/slow-tests-limit",
            test_identifier=f"tests/test_{i}.py::test_it",
            median_duration_ms=float(1000 + i),
            sample_size=5,
            computed_at=now,
        )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/slow-tests-limit/ci-cd/slow-tests?limit=2",
                headers={"Authorization": f"Bearer {_token(['read:test-intelligence'])}"},
            )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


async def test_list_slow_tests_returns_empty_list_when_none_exist(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/slow-tests-empty/ci-cd/slow-tests",
                headers={"Authorization": f"Bearer {_token(['read:test-intelligence'])}"},
            )

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_list_slow_tests_returns_403_without_scope(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/slow-tests-empty/ci-cd/slow-tests",
                headers={"Authorization": f"Bearer {_token(['read:pr-analysis'])}"},
            )

    assert response.status_code == 403
