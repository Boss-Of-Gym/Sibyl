import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from sibyl.api.app import create_app
from sibyl.dependency_analysis.adapters.repository import DependencyAnalysisRepository
from sibyl.identity.auth import create_access_token
from sibyl.platform.config import Settings

JWT_SIGNING_KEY = "test-signing-key-for-dependency-api"


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


async def test_list_dependency_manifests_returns_latest_per_ecosystem(
    postgres_container, redis_container, async_engine, db_session
):
    repository = DependencyAnalysisRepository()
    now = datetime.now(UTC)
    installation_id = uuid.uuid4()

    await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=installation_id,
        repository="acme/dependency-api-test",
        commit_sha="sha-1",
        ecosystem="npm",
        packages=[{"name": "left-pad", "version": "1.3.0", "direct": True}],
        received_at=now,
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/dependency-api-test/dependencies",
                headers={"Authorization": f"Bearer {_token(['read:dependency-analysis'])}"},
            )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["ecosystem"] == "npm"
    assert items[0]["commitSha"] == "sha-1"
    assert items[0]["packages"] == [{"name": "left-pad", "version": "1.3.0", "direct": True}]


async def test_list_dependency_manifests_returns_empty_list_when_none_reported(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/dependency-api-empty/dependencies",
                headers={"Authorization": f"Bearer {_token(['read:dependency-analysis'])}"},
            )

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_list_dependency_manifests_returns_403_without_scope(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/dependency-api-empty/dependencies",
                headers={"Authorization": f"Bearer {_token(['read:test-intelligence'])}"},
            )

    assert response.status_code == 403


async def test_list_dependency_changes_returns_classified_diff(
    postgres_container, redis_container, async_engine, db_session
):
    repository = DependencyAnalysisRepository()
    installation_id = uuid.uuid4()
    base_time = datetime.now(UTC)

    await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=installation_id,
        repository="acme/dependency-changes-api",
        commit_sha="sha-1",
        ecosystem="npm",
        packages=[{"name": "left-pad", "version": "1.0.0", "direct": True}],
        received_at=base_time,
    )
    await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=installation_id,
        repository="acme/dependency-changes-api",
        commit_sha="sha-2",
        ecosystem="npm",
        packages=[{"name": "left-pad", "version": "2.0.0", "direct": True}],
        received_at=base_time + timedelta(minutes=1),
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/dependency-changes-api/dependencies/changes?ecosystem=npm",
                headers={"Authorization": f"Bearer {_token(['read:dependency-analysis'])}"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["fromCommitSha"] == "sha-1"
    assert body["toCommitSha"] == "sha-2"
    assert body["changes"] == [
        {
            "name": "left-pad",
            "changeType": "version_changed",
            "oldVersion": "1.0.0",
            "newVersion": "2.0.0",
            "severity": "breaking",
        }
    ]


async def test_list_dependency_changes_returns_404_when_not_enough_history(
    postgres_container, redis_container, async_engine, db_session
):
    repository = DependencyAnalysisRepository()
    await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/dependency-changes-insufficient",
        commit_sha="sha-1",
        ecosystem="npm",
        packages=[{"name": "left-pad", "version": "1.0.0", "direct": True}],
        received_at=datetime.now(UTC),
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/dependency-changes-insufficient/dependencies/changes"
                "?ecosystem=npm",
                headers={"Authorization": f"Bearer {_token(['read:dependency-analysis'])}"},
            )

    assert response.status_code == 404


async def test_list_dependency_changes_returns_403_without_scope(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/repositories/acme/dependency-changes-empty/dependencies/changes?ecosystem=npm",
                headers={"Authorization": f"Bearer {_token(['read:test-intelligence'])}"},
            )

    assert response.status_code == 403
