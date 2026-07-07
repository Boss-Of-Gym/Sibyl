import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from sibyl.api.app import create_app
from sibyl.identity.auth import create_access_token
from sibyl.platform.config import Settings
from sibyl.root_cause_analysis.adapters.repository import RootCauseAnalysisRepository

JWT_SIGNING_KEY = "test-signing-key-for-root-cause-api"


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


async def test_get_root_cause_returns_200_when_hypothesis_ready(
    postgres_container, redis_container, async_engine, db_session
):
    repository = RootCauseAnalysisRepository()
    failure_event = await repository.upsert_failure_event(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/rca-api-test",
        test_identifier="tests/test_a.py::test_a",
        commit_sha="sha-1",
        ci_run_id=1,
        detected_at=datetime.now(UTC),
    )
    await db_session.flush()
    await repository.save_hypothesis(
        db_session,
        failure_event_id=failure_event.id,
        hypothesis_text="likely caused by src/a.py",
        confidence=0.7,
        suspected_commit_sha="sha-1",
        suspected_file_path="src/a.py",
        llm_model="fake",
        llm_tokens_used=10,
        llm_latency_ms=500,
        computed_at=datetime.now(UTC),
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/repositories/acme/rca-api-test/failures/{failure_event.id}/root-cause",
                headers={"Authorization": f"Bearer {_token(['read:root-cause'])}"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["hypothesisText"] == "likely caused by src/a.py"
    assert body["confidence"] == 0.7


async def test_get_root_cause_returns_202_when_not_ready_yet(
    postgres_container, redis_container, async_engine, db_session
):
    repository = RootCauseAnalysisRepository()
    failure_event = await repository.upsert_failure_event(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/rca-api-pending",
        test_identifier="tests/test_b.py::test_b",
        commit_sha="sha-2",
        ci_run_id=1,
        detected_at=datetime.now(UTC),
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/repositories/acme/rca-api-pending/failures/{failure_event.id}/root-cause",
                headers={"Authorization": f"Bearer {_token(['read:root-cause'])}"},
            )

    assert response.status_code == 202
    assert response.json()["code"] == "SIBYL_ANALYSIS_NOT_READY"


async def test_get_root_cause_returns_404_for_unknown_failure_event(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/repositories/acme/rca-api-pending/failures/{uuid.uuid4()}/root-cause",
                headers={"Authorization": f"Bearer {_token(['read:root-cause'])}"},
            )

    assert response.status_code == 404


async def test_get_root_cause_returns_404_when_repository_does_not_match(
    postgres_container, redis_container, async_engine, db_session
):
    repository = RootCauseAnalysisRepository()
    failure_event = await repository.upsert_failure_event(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/rca-api-owned-by-someone-else",
        test_identifier="tests/test_c.py::test_c",
        commit_sha="sha-3",
        ci_run_id=1,
        detected_at=datetime.now(UTC),
    )
    await db_session.commit()

    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/repositories/acme/a-different-repo/failures/{failure_event.id}/root-cause",
                headers={"Authorization": f"Bearer {_token(['read:root-cause'])}"},
            )

    assert response.status_code == 404


async def test_get_root_cause_returns_403_without_scope(
    postgres_container, redis_container, async_engine
):
    app = create_app(_settings(postgres_container, redis_container))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/repositories/acme/rca-api-test/failures/{uuid.uuid4()}/root-cause",
                headers={"Authorization": f"Bearer {_token(['read:pr-analysis'])}"},
            )

    assert response.status_code == 403
