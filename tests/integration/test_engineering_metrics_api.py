import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from sibyl.api.app import create_app
from sibyl.engineering_metrics.adapters.repository import EngineeringMetricsRepository
from sibyl.identity.auth import create_access_token
from sibyl.platform.config import Settings

JWT_SIGNING_KEY = "test-signing-key-for-engineering-metrics-api"


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


async def test_get_engineering_metrics_returns_computed_aggregates(
    postgres_container, redis_container, async_engine, db_session
):
    repository = EngineeringMetricsRepository()
    now = datetime.now(UTC)

    await repository.upsert_pr_lifecycle(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/em-api-test",
        pr_number=1,
        opened_at=now - timedelta(hours=10),
        merged_at=now - timedelta(hours=4),
        closed_at=now - timedelta(hours=4),
        merged=True,
    )
    await repository.upsert_ci_run(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/em-api-test",
        ci_run_id=1,
        commit_sha="sha-1",
        started_at=now - timedelta(minutes=10),
        completed_at=now - timedelta(minutes=5),
        passed_count=10,
        failed_count=0,
        skipped_count=0,
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/em-api-test/engineering-metrics",
                headers={"Authorization": f"Bearer {_token(['read:engineering-metrics'])}"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["windowDays"] == 30
    assert body["pullRequestCount"] == 1
    assert body["medianPrCycleTimeHours"] == 6.0
    assert body["ciRunCount"] == 1
    assert body["ciSuccessRate"] == 1.0
    assert body["medianCiDurationMinutes"] == 5.0


async def test_get_engineering_metrics_returns_nulls_for_empty_window(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/em-api-nonexistent/engineering-metrics",
                headers={"Authorization": f"Bearer {_token(['read:engineering-metrics'])}"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["pullRequestCount"] == 0
    assert body["medianPrCycleTimeHours"] is None
    assert body["ciSuccessRate"] is None


async def test_get_engineering_metrics_returns_403_without_scope(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/em-api-test/engineering-metrics",
                headers={"Authorization": f"Bearer {_token(['read:pr-analysis'])}"},
            )

    assert response.status_code == 403
