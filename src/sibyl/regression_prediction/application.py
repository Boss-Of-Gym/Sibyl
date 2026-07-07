import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.platform.events.errors import MalformedEventError
from sibyl.platform.events.outbox import OutboxRepository
from sibyl.regression_prediction.adapters.repository import RegressionPredictionRepository
from sibyl.regression_prediction.domain.models import (
    HistoricalRegressionSignal,
    RegressionPredictionContext,
)
from sibyl.regression_prediction.domain.ports import ReasoningPort


class MalformedPrChangedPayload(MalformedEventError):
    pass


def _extract_pr_context(payload: dict[str, Any]) -> tuple[str, int, str, list[str]]:
    try:
        pr = payload["pull_request"]
        repository = payload["repository"]["full_name"]
        return (
            repository,
            payload["number"],
            pr["head"]["sha"],
            [f["filename"] for f in payload.get("files", [])],
        )
    except KeyError as exc:
        raise MalformedPrChangedPayload(str(exc)) from exc


class RegressionPredictionService:
    def __init__(
        self,
        repository: RegressionPredictionRepository,
        outbox: OutboxRepository[Any],
        reasoning_port: ReasoningPort,
    ):
        self._repository = repository
        self._outbox = outbox
        self._reasoning_port = reasoning_port

    async def handle_pr_changed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        repository, pr_number, head_sha, changed_file_paths = _extract_pr_context(payload)

        historical = await self._repository.get_historical_regressions_by_files(
            session, repository, changed_file_paths
        )
        context = RegressionPredictionContext(
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            changed_file_paths=changed_file_paths,
            historical_regressions=[
                HistoricalRegressionSignal(
                    file_path=h.file_path,
                    hypothesis_text=h.hypothesis_text,
                    confidence=h.confidence,
                    occurred_at=h.occurred_at,
                )
                for h in historical
            ],
        )

        prediction = await self._reasoning_port.predict_regression(context)
        now = datetime.now(UTC)

        await self._repository.save_prediction(
            session,
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            regression_probability=prediction.regression_probability,
            rationale=prediction.rationale,
            contributing_signals=[s.model_dump() for s in prediction.contributing_signals],
            llm_model=prediction.llm_model,
            llm_tokens_used=prediction.llm_tokens_used,
            llm_latency_ms=prediction.llm_latency_ms,
            computed_at=now,
        )

        await self._outbox.add(
            session,
            event_type="regression-prediction.completed",
            installation_id=installation_id,
            payload={
                "repository": repository,
                "pr_number": pr_number,
                "head_sha": head_sha,
                "regression_probability": prediction.regression_probability,
                "rationale": prediction.rationale,
                "explanation_unavailable": prediction.explanation_unavailable,
            },
            occurred_at=now,
        )
        await session.commit()

    async def handle_hypothesis_ready(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        file_path = payload.get("suspected_file_path")
        if file_path is None:
            return

        await self._repository.upsert_historical_regression(
            session,
            failure_event_id=uuid.UUID(payload["failure_event_id"]),
            installation_id=installation_id,
            repository=payload["repository"],
            file_path=file_path,
            hypothesis_text=payload["hypothesis_text"],
            confidence=payload["confidence"],
            occurred_at=datetime.now(UTC),
        )
        await session.commit()
