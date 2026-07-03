import hashlib
import hmac
import json

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from sibyl.api.app import create_app
from sibyl.ingestion.adapters.db_models import IngestionOutboxEvent, WebhookDelivery
from sibyl.platform.config import Settings

WEBHOOK_SECRET = "test-webhook-secret"


def _settings(postgres_container: PostgresContainer, redis_container: RedisContainer) -> Settings:
    redis_url = (
        f"redis://{redis_container.get_container_host_ip()}:"
        f"{redis_container.get_exposed_port(6379)}/0"
    )
    return Settings(
        database_url=postgres_container.get_connection_url(),
        redis_url=redis_url,
        github_webhook_secret=WEBHOOK_SECRET,
    )


def _sign(body: bytes) -> str:
    digest = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _payload(installation_id: int = 123456) -> bytes:
    return json.dumps(
        {
            "action": "opened",
            "number": 42,
            "installation": {"id": installation_id, "account": {"login": "acme"}},
        }
    ).encode()


async def test_valid_webhook_is_accepted_and_persisted(
    postgres_container, redis_container, async_engine, db_session
):
    app = create_app(_settings(postgres_container, redis_container))
    body = _payload()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": _sign(body),
                    "X-GitHub-Delivery": "delivery-happy-path",
                    "X-GitHub-Event": "pull_request",
                },
            )

    assert response.status_code == 202
    delivery_stmt = select(WebhookDelivery).where(
        WebhookDelivery.github_delivery_id == "delivery-happy-path"
    )
    deliveries = (await db_session.execute(delivery_stmt)).scalars().all()
    assert len(deliveries) == 1

    outbox_stmt = select(IngestionOutboxEvent).where(
        IngestionOutboxEvent.event_type == "ingestion.pr-changed"
    )
    outbox_events = (await db_session.execute(outbox_stmt)).scalars().all()
    assert len(outbox_events) >= 1


async def test_invalid_signature_is_rejected(postgres_container, redis_container, async_engine):
    app = create_app(_settings(postgres_container, redis_container))
    body = _payload()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": "sha256=" + "0" * 64,
                    "X-GitHub-Delivery": "delivery-bad-signature",
                    "X-GitHub-Event": "pull_request",
                },
            )

    assert response.status_code == 401
    assert response.json()["code"] == "SIBYL_WEBHOOK_SIGNATURE_INVALID"


async def test_duplicate_delivery_is_not_persisted_twice(
    postgres_container, redis_container, async_engine, db_session
):
    app = create_app(_settings(postgres_container, redis_container))
    body = _payload()
    headers = {
        "X-Hub-Signature-256": _sign(body),
        "X-GitHub-Delivery": "delivery-duplicate",
        "X-GitHub-Event": "pull_request",
    }

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post("/webhooks/github", content=body, headers=headers)
            second = await client.post("/webhooks/github", content=body, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    delivery_stmt = select(WebhookDelivery).where(
        WebhookDelivery.github_delivery_id == "delivery-duplicate"
    )
    deliveries = (await db_session.execute(delivery_stmt)).scalars().all()
    assert len(deliveries) == 1


async def test_missing_headers_is_malformed(postgres_container, redis_container, async_engine):
    app = create_app(_settings(postgres_container, redis_container))
    body = _payload()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/webhooks/github",
                content=body,
                headers={"X-Hub-Signature-256": _sign(body)},
            )

    assert response.status_code == 400
    assert response.json()["code"] == "SIBYL_WEBHOOK_MALFORMED"
