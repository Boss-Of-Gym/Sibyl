import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from sibyl.api.app import create_app
from sibyl.identity.auth import create_access_token
from sibyl.platform.config import Settings
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository

JWT_SIGNING_KEY = "test-signing-key-for-coverage-gaps"


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


async def test_list_coverage_gaps_returns_ranked_files(
    postgres_container, redis_container, async_engine, db_session
):
    repository = TestIntelligenceRepository()
    now = datetime.now(UTC)
    installation_id = uuid.uuid4()

    await repository.upsert_pr_changed_files(
        db_session,
        installation_id=installation_id,
        repository="acme/coverage-gaps-api",
        commit_sha="sha-1",
        pr_number=1,
        changed_file_paths=["src/no_signal.py", "src/low.py"],
        received_at=now,
    )
    await repository.upsert_file_coverage_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/coverage-gaps-api",
        file_path="src/low.py",
        commit_sha="sha-1",
        lines_covered=1,
        lines_total=10,
        coverage_pct=0.1,
        computed_at=now,
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/coverage-gaps-api/coverage/gaps",
                headers={"Authorization": f"Bearer {_token(['read:test-intelligence'])}"},
            )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["filePath"] for item in items] == ["src/no_signal.py", "src/low.py"]
    assert items[0]["coveragePct"] is None
    assert items[1]["coveragePct"] == 0.1


async def test_list_coverage_gaps_returns_empty_list_when_nothing_changed(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/coverage-gaps-empty/coverage/gaps",
                headers={"Authorization": f"Bearer {_token(['read:test-intelligence'])}"},
            )

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_list_coverage_gaps_respects_limit_query_param(
    postgres_container, redis_container, async_engine, db_session
):
    repository = TestIntelligenceRepository()
    now = datetime.now(UTC)
    installation_id = uuid.uuid4()

    await repository.upsert_pr_changed_files(
        db_session,
        installation_id=installation_id,
        repository="acme/coverage-gaps-limit",
        commit_sha="sha-1",
        pr_number=1,
        changed_file_paths=[f"src/file_{i}.py" for i in range(5)],
        received_at=now,
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/coverage-gaps-limit/coverage/gaps?limit=2",
                headers={"Authorization": f"Bearer {_token(['read:test-intelligence'])}"},
            )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


async def test_list_coverage_gaps_returns_403_without_scope(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/coverage-gaps-empty/coverage/gaps",
                headers={"Authorization": f"Bearer {_token(['read:pr-analysis'])}"},
            )

    assert response.status_code == 403
