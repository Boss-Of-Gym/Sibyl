from datetime import UTC, datetime

from fastapi import APIRouter, Header, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sibyl.identity.adapters.repository import InstallationRepository
from sibyl.ingestion.adapters.db_models import IngestionOutboxEvent, WebhookDelivery
from sibyl.ingestion.adapters.dedup import is_duplicate_delivery
from sibyl.ingestion.adapters.signature import verify_github_signature
from sibyl.ingestion.topics import resolve_topic
from sibyl.platform.errors import ProblemException
from sibyl.platform.events.outbox import OutboxRepository
from sibyl.platform.observability import get_logger

router = APIRouter()
logger = get_logger(__name__)

_outbox_repository = OutboxRepository(IngestionOutboxEvent)
_installation_repository = InstallationRepository()


@router.post("/webhooks/github", status_code=202)
async def receive_github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> Response:
    body = await request.body()
    settings = request.app.state.settings

    if not verify_github_signature(body, x_hub_signature_256, settings.github_webhook_secret):
        raise ProblemException(
            status_code=401,
            title="Invalid webhook signature",
            code="SIBYL_WEBHOOK_SIGNATURE_INVALID",
        )

    if not x_github_delivery or not x_github_event:
        raise ProblemException(
            status_code=400,
            title="Missing required GitHub webhook headers",
            code="SIBYL_WEBHOOK_MALFORMED",
        )

    try:
        payload = await request.json()
    except ValueError as exc:
        raise ProblemException(
            status_code=400,
            title="Malformed JSON payload",
            code="SIBYL_WEBHOOK_MALFORMED",
        ) from exc

    redis: Redis = request.app.state.redis
    if await is_duplicate_delivery(redis, x_github_delivery):
        logger.info("webhook.duplicate", delivery_id=x_github_delivery)
        return Response(status_code=202)

    github_installation_id = payload.get("installation", {}).get("id")
    if github_installation_id is None:
        raise ProblemException(
            status_code=400,
            title="Payload missing installation context",
            code="SIBYL_WEBHOOK_MALFORMED",
        )

    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        installation = await _installation_repository.get_or_create_by_github_id(
            session,
            github_installation_id,
            organization_login=payload.get("installation", {}).get("account", {}).get("login", ""),
        )

        now = datetime.now(UTC)
        session.add(
            WebhookDelivery(
                github_delivery_id=x_github_delivery,
                installation_id=installation.id,
                event_type=x_github_event,
                received_at=now,
                status="accepted",
            )
        )

        topic = resolve_topic(x_github_event)
        if topic is not None:
            await _outbox_repository.add(
                session,
                event_type=topic,
                installation_id=installation.id,
                payload=payload,
                occurred_at=now,
            )

    logger.info("webhook.accepted", delivery_id=x_github_delivery, event_type=x_github_event)
    return Response(status_code=202)
