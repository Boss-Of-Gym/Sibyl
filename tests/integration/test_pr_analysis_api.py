import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from sibyl.api.app import create_app
from sibyl.identity.auth import create_access_token
from sibyl.platform.config import Settings
from sibyl.pr_analysis.adapters.repository import PrAnalysisRepository
from sibyl.pr_analysis.domain.models import ContributingFactor, RiskAssessment

JWT_SIGNING_KEY = "test-signing-key-for-api"


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


async def test_get_pr_analysis_returns_200_for_existing_assessment(
    postgres_container, redis_container, async_engine, db_session
):
    repository = PrAnalysisRepository()
    pr = await repository.upsert_pull_request(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/api-test",
        pr_number=10,
        head_sha="sha-a",
        base_sha="sha-b",
        author_login="octocat",
        files_changed=1,
        additions=5,
        deletions=1,
        opened_at=datetime.now(UTC),
    )
    assessment = RiskAssessment(
        score=0.3,
        rationale="fine",
        contributing_factors=[ContributingFactor(factor="size", weight=0.3)],
        llm_model="test-model",
    )
    await repository.add_risk_assessment(db_session, pr, assessment, datetime.now(UTC))
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/api-test/pulls/10/pr-analysis",
                headers={"Authorization": f"Bearer {_token(['read:pr-analysis'])}"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 0.3
    assert body["llmModel"] == "test-model"


async def test_get_pr_analysis_returns_404_when_missing(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/api-test/pulls/999999/pr-analysis",
                headers={"Authorization": f"Bearer {_token(['read:pr-analysis'])}"},
            )

    assert response.status_code == 404
    assert response.json()["code"] == "SIBYL_NOT_FOUND"


async def test_get_pr_analysis_returns_403_without_scope(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/api-test/pulls/10/pr-analysis",
                headers={"Authorization": f"Bearer {_token(['admin:installations'])}"},
            )

    assert response.status_code == 403
    assert response.json()["code"] == "SIBYL_SCOPE_INSUFFICIENT"


async def test_get_pr_analysis_returns_401_without_token(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/repositories/acme/api-test/pulls/10/pr-analysis")

    assert response.status_code == 401
