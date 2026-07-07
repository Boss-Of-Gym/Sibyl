import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from sibyl.api.app import create_app
from sibyl.identity.auth import create_access_token
from sibyl.platform.config import Settings
from sibyl.release_risk_analysis.adapters.repository import ReleaseRiskAnalysisRepository

JWT_SIGNING_KEY = "test-signing-key-for-release-risk-analysis-api"


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


async def test_get_release_risk_returns_200_when_available(
    postgres_container, redis_container, async_engine, db_session
):
    repository = ReleaseRiskAnalysisRepository()
    await repository.save_assessment(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/rr-api-test",
        pr_number=9,
        head_sha="sha-1",
        risk_score=0.55,
        considered_signals=["regression_probability", "ci_success_rate", "coverage_pct"],
        regression_probability=0.6,
        ci_success_rate=0.9,
        coverage_pct=0.8,
        computed_at=datetime.now(UTC),
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/rr-api-test/pulls/9/release-risk",
                headers={"Authorization": f"Bearer {_token(['read:release-risk'])}"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["riskScore"] == 0.55
    assert body["headSha"] == "sha-1"
    assert set(body["consideredSignals"]) == {
        "regression_probability",
        "ci_success_rate",
        "coverage_pct",
    }


async def test_get_release_risk_returns_404_when_absent(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/rr-api-nonexistent/pulls/1/release-risk",
                headers={"Authorization": f"Bearer {_token(['read:release-risk'])}"},
            )

    assert response.status_code == 404


async def test_get_release_risk_returns_403_without_scope(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/rr-api-test/pulls/9/release-risk",
                headers={"Authorization": f"Bearer {_token(['read:pr-analysis'])}"},
            )

    assert response.status_code == 403
