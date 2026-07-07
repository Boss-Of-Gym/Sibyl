import asyncio
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.dependency_analysis.adapters.repository import DependencyAnalysisRepository
from sibyl.dependency_analysis.application import DependencyAnalysisService
from sibyl.engineering_metrics.adapters.repository import EngineeringMetricsRepository
from sibyl.engineering_metrics.application import EngineeringMetricsService
from sibyl.identity.adapters.repository import InstallationRepository
from sibyl.ingestion.adapters.db_models import IngestionOutboxEvent
from sibyl.platform.config import Settings, get_settings
from sibyl.platform.db import make_session_factory
from sibyl.platform.events.kafka import KafkaConsumerClient, KafkaProducerClient
from sibyl.platform.events.outbox import OutboxRepository
from sibyl.platform.events.relay import run_relay_forever
from sibyl.platform.github.app_auth import GitHubAppAuthenticator
from sibyl.platform.github.checks_client import GitHubChecksClient
from sibyl.platform.observability import configure_observability, get_logger, get_meter, get_tracer
from sibyl.pr_analysis.adapters.checks_notifier import PrAnalysisChecksNotifier
from sibyl.pr_analysis.adapters.db_models import PrAnalysisOutboxEvent
from sibyl.pr_analysis.adapters.guarded_reasoning import GuardedReasoningPort
from sibyl.pr_analysis.adapters.llm_reasoning import AnthropicReasoningPort
from sibyl.pr_analysis.adapters.repository import PrAnalysisRepository
from sibyl.pr_analysis.application import PrAnalysisService
from sibyl.regression_prediction.adapters.checks_notifier import RegressionPredictionChecksNotifier
from sibyl.regression_prediction.adapters.db_models import RegressionPredictionOutboxEvent
from sibyl.regression_prediction.adapters.guarded_reasoning import (
    GuardedReasoningPort as RegressionPredictionGuardedReasoningPort,
)
from sibyl.regression_prediction.adapters.llm_reasoning import (
    AnthropicReasoningPort as RegressionPredictionAnthropicReasoningPort,
)
from sibyl.regression_prediction.adapters.repository import RegressionPredictionRepository
from sibyl.regression_prediction.application import RegressionPredictionService
from sibyl.release_risk_analysis.adapters.db_models import ReleaseRiskOutboxEvent
from sibyl.release_risk_analysis.adapters.repository import ReleaseRiskAnalysisRepository
from sibyl.release_risk_analysis.application import ReleaseRiskAnalysisService
from sibyl.root_cause_analysis.adapters.checks_notifier import RootCauseChecksNotifier
from sibyl.root_cause_analysis.adapters.db_models import RootCauseAnalysisOutboxEvent
from sibyl.root_cause_analysis.adapters.guarded_reasoning import (
    GuardedReasoningPort as RootCauseGuardedReasoningPort,
)
from sibyl.root_cause_analysis.adapters.llm_reasoning import (
    AnthropicReasoningPort as RootCauseAnthropicReasoningPort,
)
from sibyl.root_cause_analysis.adapters.repository import RootCauseAnalysisRepository
from sibyl.root_cause_analysis.application import RootCauseAnalysisService
from sibyl.test_intelligence.adapters.db_models import TestIntelligenceOutboxEvent
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository
from sibyl.test_intelligence.application import TestIntelligenceService

logger = get_logger(__name__)
tracer = get_tracer(__name__)
meter = get_meter(__name__)

_processed_total = meter.create_counter("consumer.processed_total")

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
Handler = Callable[[dict[str, Any]], Awaitable[None]]


def make_pr_changed_handler(session_factory: SessionFactory, service: PrAnalysisService) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_pr_changed(session, installation_id, envelope["payload"])
        logger.info(
            "worker.pr_analysis.processed", repository=envelope["payload"].get("repository")
        )

    return handle


def make_pr_analysis_completed_handler(
    session_factory: SessionFactory, notifier: PrAnalysisChecksNotifier
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await notifier.handle_pr_analysis_completed(
                session, installation_id, envelope["payload"]
            )
        logger.info(
            "worker.checks_notifier.processed", repository=envelope["payload"].get("repository")
        )

    return handle


def make_test_intelligence_pr_changed_handler(
    session_factory: SessionFactory, service: TestIntelligenceService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_pr_changed(session, installation_id, envelope["payload"])
        logger.info(
            "worker.test_intelligence.pr_changed_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_ci_run_completed_handler(
    session_factory: SessionFactory, service: TestIntelligenceService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_ci_run_completed(session, installation_id, envelope["payload"])
        logger.info(
            "worker.test_intelligence.ci_run_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_coverage_report_received_handler(
    session_factory: SessionFactory, service: TestIntelligenceService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_coverage_report_received(
                session, installation_id, envelope["payload"]
            )
        logger.info(
            "worker.test_intelligence.coverage_report_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_flaky_signal_updated_handler(
    session_factory: SessionFactory, repository: PrAnalysisRepository
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        payload = envelope["payload"]
        async with session_factory() as session, session.begin():
            await repository.upsert_local_flaky_signal(
                session,
                repository=payload["repository"],
                test_identifier=payload["test_identifier"],
                flakiness_score=payload["flakiness_score"],
                updated_at=datetime.now(UTC),
            )
        logger.info(
            "worker.pr_analysis.flaky_signal_projected",
            test_identifier=payload.get("test_identifier"),
        )

    return handle


def make_root_cause_ci_run_completed_handler(
    session_factory: SessionFactory, service: RootCauseAnalysisService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_ci_run_completed(session, installation_id, envelope["payload"])
        logger.info(
            "worker.root_cause_analysis.ci_run_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_root_cause_pr_analysis_completed_handler(
    session_factory: SessionFactory, service: RootCauseAnalysisService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_pr_analysis_completed(
                session, installation_id, envelope["payload"]
            )
        logger.info(
            "worker.root_cause_analysis.pr_analysis_completed_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_root_cause_impact_computed_handler(
    session_factory: SessionFactory, service: RootCauseAnalysisService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_impact_computed(session, installation_id, envelope["payload"])
        logger.info(
            "worker.root_cause_analysis.impact_computed_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_root_cause_flaky_signal_updated_handler(
    session_factory: SessionFactory, service: RootCauseAnalysisService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_flaky_signal_updated(
                session, installation_id, envelope["payload"]
            )
        logger.info(
            "worker.root_cause_analysis.flaky_signal_processed",
            test_identifier=envelope["payload"].get("test_identifier"),
        )

    return handle


def make_root_cause_hypothesis_ready_handler(
    session_factory: SessionFactory, notifier: RootCauseChecksNotifier
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await notifier.handle_hypothesis_ready(session, installation_id, envelope["payload"])
        logger.info(
            "worker.root_cause_checks_notifier.processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_dependency_manifest_received_handler(
    session_factory: SessionFactory, service: DependencyAnalysisService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_manifest_received(session, installation_id, envelope["payload"])
        logger.info(
            "worker.dependency_analysis.manifest_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_regression_prediction_pr_changed_handler(
    session_factory: SessionFactory, service: RegressionPredictionService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_pr_changed(session, installation_id, envelope["payload"])
        logger.info(
            "worker.regression_prediction.pr_changed_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_regression_prediction_hypothesis_ready_handler(
    session_factory: SessionFactory, service: RegressionPredictionService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_hypothesis_ready(session, installation_id, envelope["payload"])
        logger.info(
            "worker.regression_prediction.hypothesis_projected",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_regression_prediction_completed_handler(
    session_factory: SessionFactory, notifier: RegressionPredictionChecksNotifier
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await notifier.handle_prediction_ready(session, installation_id, envelope["payload"])
        logger.info(
            "worker.regression_prediction_checks_notifier.processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_engineering_metrics_pr_changed_handler(
    session_factory: SessionFactory, service: EngineeringMetricsService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_pr_changed(session, installation_id, envelope["payload"])
        logger.info(
            "worker.engineering_metrics.pr_changed_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_engineering_metrics_ci_run_completed_handler(
    session_factory: SessionFactory, service: EngineeringMetricsService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_ci_run_completed(session, installation_id, envelope["payload"])
        logger.info(
            "worker.engineering_metrics.ci_run_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_release_risk_ci_run_completed_handler(
    session_factory: SessionFactory, service: ReleaseRiskAnalysisService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_ci_run_completed(session, installation_id, envelope["payload"])
        logger.info(
            "worker.release_risk_analysis.ci_run_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_release_risk_coverage_computed_handler(
    session_factory: SessionFactory, service: ReleaseRiskAnalysisService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_coverage_computed(session, installation_id, envelope["payload"])
        logger.info(
            "worker.release_risk_analysis.coverage_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_release_risk_prediction_completed_handler(
    session_factory: SessionFactory, service: ReleaseRiskAnalysisService
) -> Handler:
    async def handle(envelope: dict[str, Any]) -> None:
        installation_id = uuid.UUID(envelope["installation_id"])
        async with session_factory() as session:
            await service.handle_regression_prediction_completed(
                session, installation_id, envelope["payload"]
            )
        logger.info(
            "worker.release_risk_analysis.assessment_processed",
            repository=envelope["payload"].get("repository"),
        )

    return handle


def make_dispatcher(handlers: dict[str, Handler], group_name: str) -> Handler:
    async def dispatch(envelope: dict[str, Any]) -> None:
        with tracer.start_as_current_span("consumer.process") as span:
            span.set_attribute("consumer.group", group_name)
            span.set_attribute("consumer.event_type", envelope["event_type"])

            handler = handlers.get(envelope["event_type"])
            if handler is None:
                logger.warning("worker.unhandled_event_type", event_type=envelope["event_type"])
                return
            await handler(envelope)
            _processed_total.add(1, {"consumer.group": group_name})

    return dispatch


def _build_checks_notifiers(
    settings: Settings, redis: Redis
) -> tuple[PrAnalysisChecksNotifier, RootCauseChecksNotifier, RegressionPredictionChecksNotifier]:
    private_key = Path(settings.github_app_private_key_path).read_text()
    http_client = httpx.AsyncClient()
    authenticator = GitHubAppAuthenticator(settings.github_app_id, private_key, redis, http_client)
    checks_client = GitHubChecksClient(http_client)
    installation_repository = InstallationRepository()
    return (
        PrAnalysisChecksNotifier(authenticator, checks_client, installation_repository),
        RootCauseChecksNotifier(authenticator, checks_client, installation_repository),
        RegressionPredictionChecksNotifier(authenticator, checks_client, installation_repository),
    )


async def _run_consumer_group(
    group_id: str,
    topics: list[str],
    bootstrap_servers: str,
    dispatcher: Handler,
    dlq_producer: KafkaProducerClient,
) -> None:
    consumer = KafkaConsumerClient(
        topics=topics,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        dlq_producer=dlq_producer,
    )
    await consumer.start()
    try:
        await consumer.consume_forever(dispatcher)
    finally:
        await consumer.stop()


def _build_health_app(session_factory: SessionFactory, redis: Redis) -> FastAPI:
    app = FastAPI()

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        await redis.ping()
        return {"status": "ready"}

    return app


async def _run_health_server(app: FastAPI, port: int) -> None:
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def run() -> None:
    settings = get_settings()
    configure_observability("sibyl-worker", settings)

    session_factory = make_session_factory(settings)
    redis = Redis.from_url(settings.redis_url)
    kafka_producer = KafkaProducerClient(settings.kafka_bootstrap_servers)
    await kafka_producer.start()

    ingestion_outbox_repository = OutboxRepository(IngestionOutboxEvent)
    pr_analysis_outbox_repository = OutboxRepository(PrAnalysisOutboxEvent)
    test_intelligence_outbox_repository = OutboxRepository(TestIntelligenceOutboxEvent)
    root_cause_analysis_outbox_repository = OutboxRepository(RootCauseAnalysisOutboxEvent)
    regression_prediction_outbox_repository = OutboxRepository(RegressionPredictionOutboxEvent)
    release_risk_outbox_repository = OutboxRepository(ReleaseRiskOutboxEvent)

    reasoning_port = GuardedReasoningPort(
        AnthropicReasoningPort(settings.llm_provider_api_key, settings.llm_provider_model)
    )
    pr_analysis_service = PrAnalysisService(
        PrAnalysisRepository(), pr_analysis_outbox_repository, reasoning_port
    )
    checks_notifier, root_cause_checks_notifier, regression_prediction_checks_notifier = (
        _build_checks_notifiers(settings, redis)
    )
    test_intelligence_service = TestIntelligenceService(
        TestIntelligenceRepository(), test_intelligence_outbox_repository
    )
    root_cause_reasoning_port = RootCauseGuardedReasoningPort(
        RootCauseAnthropicReasoningPort(settings.llm_provider_api_key, settings.llm_provider_model)
    )
    root_cause_analysis_service = RootCauseAnalysisService(
        RootCauseAnalysisRepository(),
        root_cause_analysis_outbox_repository,
        root_cause_reasoning_port,
    )
    dependency_analysis_service = DependencyAnalysisService(DependencyAnalysisRepository())
    engineering_metrics_service = EngineeringMetricsService(EngineeringMetricsRepository())

    regression_prediction_reasoning_port = RegressionPredictionGuardedReasoningPort(
        RegressionPredictionAnthropicReasoningPort(
            settings.llm_provider_api_key, settings.llm_provider_model
        )
    )
    regression_prediction_service = RegressionPredictionService(
        RegressionPredictionRepository(),
        regression_prediction_outbox_repository,
        regression_prediction_reasoning_port,
    )
    release_risk_analysis_service = ReleaseRiskAnalysisService(
        ReleaseRiskAnalysisRepository(), release_risk_outbox_repository
    )

    pr_analysis_repository = PrAnalysisRepository()
    pr_analysis_dispatcher = make_dispatcher(
        {
            "ingestion.pr-changed": make_pr_changed_handler(session_factory, pr_analysis_service),
            "pr-analysis.completed": make_pr_analysis_completed_handler(
                session_factory, checks_notifier
            ),
            "test-intelligence.flaky-signal-updated": make_flaky_signal_updated_handler(
                session_factory, pr_analysis_repository
            ),
            "root-cause.hypothesis-ready": make_root_cause_hypothesis_ready_handler(
                session_factory, root_cause_checks_notifier
            ),
            "regression-prediction.completed": make_regression_prediction_completed_handler(
                session_factory, regression_prediction_checks_notifier
            ),
        },
        group_name="pr-analysis-worker",
    )
    regression_prediction_dispatcher = make_dispatcher(
        {
            "ingestion.pr-changed": make_regression_prediction_pr_changed_handler(
                session_factory, regression_prediction_service
            ),
            "root-cause.hypothesis-ready": make_regression_prediction_hypothesis_ready_handler(
                session_factory, regression_prediction_service
            ),
        },
        group_name="regression-prediction-worker",
    )
    test_intelligence_dispatcher = make_dispatcher(
        {
            "ingestion.pr-changed": make_test_intelligence_pr_changed_handler(
                session_factory, test_intelligence_service
            ),
            "ingestion.ci-run-completed": make_ci_run_completed_handler(
                session_factory, test_intelligence_service
            ),
            "ingestion.coverage-report-received": make_coverage_report_received_handler(
                session_factory, test_intelligence_service
            ),
        },
        group_name="test-intelligence-worker",
    )
    root_cause_analysis_dispatcher = make_dispatcher(
        {
            "ingestion.ci-run-completed": make_root_cause_ci_run_completed_handler(
                session_factory, root_cause_analysis_service
            ),
            "pr-analysis.completed": make_root_cause_pr_analysis_completed_handler(
                session_factory, root_cause_analysis_service
            ),
            "test-intelligence.impact-computed": make_root_cause_impact_computed_handler(
                session_factory, root_cause_analysis_service
            ),
            "test-intelligence.flaky-signal-updated": make_root_cause_flaky_signal_updated_handler(
                session_factory, root_cause_analysis_service
            ),
        },
        group_name="root-cause-analysis-worker",
    )

    dependency_analysis_dispatcher = make_dispatcher(
        {
            "ingestion.dependency-manifest-received": make_dependency_manifest_received_handler(
                session_factory, dependency_analysis_service
            ),
        },
        group_name="dependency-analysis-worker",
    )

    engineering_metrics_dispatcher = make_dispatcher(
        {
            "ingestion.pr-changed": make_engineering_metrics_pr_changed_handler(
                session_factory, engineering_metrics_service
            ),
            "ingestion.ci-run-completed": make_engineering_metrics_ci_run_completed_handler(
                session_factory, engineering_metrics_service
            ),
        },
        group_name="engineering-metrics-worker",
    )

    release_risk_analysis_dispatcher = make_dispatcher(
        {
            "ingestion.ci-run-completed": make_release_risk_ci_run_completed_handler(
                session_factory, release_risk_analysis_service
            ),
            "test-intelligence.coverage-computed": make_release_risk_coverage_computed_handler(
                session_factory, release_risk_analysis_service
            ),
            "regression-prediction.completed": make_release_risk_prediction_completed_handler(
                session_factory, release_risk_analysis_service
            ),
        },
        group_name="release-risk-analysis-worker",
    )

    try:
        await asyncio.gather(
            _run_health_server(
                _build_health_app(session_factory, redis), settings.worker_health_port
            ),
            run_relay_forever(session_factory, ingestion_outbox_repository, kafka_producer),
            run_relay_forever(session_factory, pr_analysis_outbox_repository, kafka_producer),
            run_relay_forever(
                session_factory, test_intelligence_outbox_repository, kafka_producer
            ),
            run_relay_forever(
                session_factory, root_cause_analysis_outbox_repository, kafka_producer
            ),
            run_relay_forever(
                session_factory, regression_prediction_outbox_repository, kafka_producer
            ),
            run_relay_forever(session_factory, release_risk_outbox_repository, kafka_producer),
            _run_consumer_group(
                "pr-analysis-worker",
                [
                    "ingestion.pr-changed",
                    "pr-analysis.completed",
                    "test-intelligence.flaky-signal-updated",
                    "root-cause.hypothesis-ready",
                    "regression-prediction.completed",
                ],
                settings.kafka_bootstrap_servers,
                pr_analysis_dispatcher,
                kafka_producer,
            ),
            _run_consumer_group(
                "regression-prediction-worker",
                ["ingestion.pr-changed", "root-cause.hypothesis-ready"],
                settings.kafka_bootstrap_servers,
                regression_prediction_dispatcher,
                kafka_producer,
            ),
            _run_consumer_group(
                "test-intelligence-worker",
                [
                    "ingestion.pr-changed",
                    "ingestion.ci-run-completed",
                    "ingestion.coverage-report-received",
                ],
                settings.kafka_bootstrap_servers,
                test_intelligence_dispatcher,
                kafka_producer,
            ),
            _run_consumer_group(
                "root-cause-analysis-worker",
                [
                    "ingestion.ci-run-completed",
                    "pr-analysis.completed",
                    "test-intelligence.impact-computed",
                    "test-intelligence.flaky-signal-updated",
                ],
                settings.kafka_bootstrap_servers,
                root_cause_analysis_dispatcher,
                kafka_producer,
            ),
            _run_consumer_group(
                "dependency-analysis-worker",
                ["ingestion.dependency-manifest-received"],
                settings.kafka_bootstrap_servers,
                dependency_analysis_dispatcher,
                kafka_producer,
            ),
            _run_consumer_group(
                "engineering-metrics-worker",
                ["ingestion.pr-changed", "ingestion.ci-run-completed"],
                settings.kafka_bootstrap_servers,
                engineering_metrics_dispatcher,
                kafka_producer,
            ),
            _run_consumer_group(
                "release-risk-analysis-worker",
                [
                    "ingestion.ci-run-completed",
                    "test-intelligence.coverage-computed",
                    "regression-prediction.completed",
                ],
                settings.kafka_bootstrap_servers,
                release_risk_analysis_dispatcher,
                kafka_producer,
            ),
        )
    finally:
        await kafka_producer.stop()
        await redis.aclose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
