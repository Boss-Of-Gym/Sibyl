import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from sibyl.api.app import create_app
from sibyl.identity.auth import create_access_token
from sibyl.platform.config import Settings
from sibyl.regression_prediction.adapters.repository import RegressionPredictionRepository

JWT_SIGNING_KEY = "test-signing-key-for-regression-prediction-api"


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


async def test_get_regression_prediction_returns_200_when_available(
    postgres_container, redis_container, async_engine, db_session
):
    repository = RegressionPredictionRepository()
    await repository.save_prediction(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/rp-api-test",
        pr_number=9,
        head_sha="sha-1",
        regression_probability=0.65,
        rationale="touches historically fragile code",
        contributing_signals=[{"signal": "historical_regression_count", "weight": 0.65}],
        llm_model="fake",
        llm_tokens_used=42,
        llm_latency_ms=500,
        computed_at=datetime.now(UTC),
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/rp-api-test/pulls/9/regression-prediction",
                headers={"Authorization": f"Bearer {_token(['read:regression-prediction'])}"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["regressionProbability"] == 0.65
    assert body["headSha"] == "sha-1"


async def test_get_regression_prediction_returns_404_when_absent(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/rp-api-nonexistent/pulls/1/regression-prediction",
                headers={"Authorization": f"Bearer {_token(['read:regression-prediction'])}"},
            )

    assert response.status_code == 404


async def test_get_regression_prediction_returns_403_without_scope(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/rp-api-test/pulls/9/regression-prediction",
                headers={"Authorization": f"Bearer {_token(['read:pr-analysis'])}"},
            )

    assert response.status_code == 403
