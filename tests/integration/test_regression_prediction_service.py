import uuid
from typing import Any

import pytest
from sqlalchemy import select

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.regression_prediction.adapters.db_models import RegressionPredictionOutboxEvent
from sibyl.regression_prediction.adapters.fake_reasoning import FakeReasoningPort
from sibyl.regression_prediction.adapters.repository import RegressionPredictionRepository
from sibyl.regression_prediction.application import (
    MalformedPrChangedPayload,
    RegressionPredictionService,
)
from sibyl.regression_prediction.domain.models import (
    RegressionPrediction,
    RegressionPredictionContext,
)
from sibyl.regression_prediction.domain.ports import ReasoningPort


class RecordingReasoningPort:
    def __init__(self) -> None:
        self.received_contexts: list[RegressionPredictionContext] = []

    async def predict_regression(
        self, context: RegressionPredictionContext
    ) -> RegressionPrediction:
        self.received_contexts.append(context)
        return RegressionPrediction(
            regression_probability=0.5,
            rationale="recorded",
            contributing_signals=[],
            llm_model="recording-port",
        )


def _service(reasoning_port: ReasoningPort | None = None) -> RegressionPredictionService:
    return RegressionPredictionService(
        RegressionPredictionRepository(),
        OutboxRepository(RegressionPredictionOutboxEvent),
        reasoning_port or FakeReasoningPort(),
    )


def _pr_changed_payload(
    repository: str, pr_number: int, head_sha: str, changed_files: list[str]
) -> dict[str, Any]:
    return {
        "number": pr_number,
        "repository": {"full_name": repository},
        "pull_request": {"head": {"sha": head_sha}},
        "files": [{"filename": path} for path in changed_files],
    }


def _hypothesis_ready_payload(
    repository: str, failure_event_id: uuid.UUID, file_path: str | None
) -> dict[str, Any]:
    return {
        "repository": repository,
        "failure_event_id": str(failure_event_id),
        "hypothesis_text": "likely caused by this file",
        "confidence": 0.7,
        "suspected_file_path": file_path,
    }


async def _get_completed_events(
    db_session, installation_id: uuid.UUID
) -> list[RegressionPredictionOutboxEvent]:
    stmt = select(RegressionPredictionOutboxEvent).where(
        RegressionPredictionOutboxEvent.event_type == "regression-prediction.completed",
        RegressionPredictionOutboxEvent.installation_id == installation_id,
    )
    return list((await db_session.execute(stmt)).scalars().all())


async def test_handle_pr_changed_persists_and_publishes(db_session):
    repository = "acme/rp-service-a"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_pr_changed(
        db_session,
        installation_id,
        _pr_changed_payload(repository, 1, "sha-a", ["src/a.py"]),
    )

    events = await _get_completed_events(db_session, installation_id)
    assert len(events) == 1
    assert events[0].payload["repository"] == repository
    assert events[0].payload["head_sha"] == "sha-a"


async def test_handle_pr_changed_raises_on_malformed_payload(db_session):
    service = _service()

    with pytest.raises(MalformedPrChangedPayload):
        await service.handle_pr_changed(db_session, uuid.uuid4(), {"not": "a real payload"})


async def test_handle_hypothesis_ready_skips_when_no_suspected_file_path(db_session):
    repository_name = "acme/rp-service-b"
    installation_id = uuid.uuid4()
    service = _service()
    prediction_repository = RegressionPredictionRepository()

    await service.handle_hypothesis_ready(
        db_session,
        installation_id,
        _hypothesis_ready_payload(repository_name, uuid.uuid4(), None),
    )

    matches = await prediction_repository.get_historical_regressions_by_files(
        db_session, repository_name, ["src/anything.py"]
    )
    assert matches == []


async def test_historical_regression_is_picked_up_by_a_later_pr_changed_event(db_session):
    repository = "acme/rp-service-c"
    installation_id = uuid.uuid4()
    recorder = RecordingReasoningPort()
    service = _service(recorder)

    await service.handle_hypothesis_ready(
        db_session,
        installation_id,
        _hypothesis_ready_payload(repository, uuid.uuid4(), "src/payments/processor.py"),
    )
    await service.handle_pr_changed(
        db_session,
        installation_id,
        _pr_changed_payload(repository, 5, "sha-c", ["src/payments/processor.py"]),
    )

    assert len(recorder.received_contexts) == 1
    context = recorder.received_contexts[0]
    assert len(context.historical_regressions) == 1
    assert context.historical_regressions[0].file_path == "src/payments/processor.py"
