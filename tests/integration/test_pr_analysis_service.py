import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.pr_analysis.adapters.db_models import PrAnalysisOutboxEvent
from sibyl.pr_analysis.adapters.fake_reasoning import FakeReasoningPort
from sibyl.pr_analysis.adapters.repository import PrAnalysisRepository
from sibyl.pr_analysis.application import MalformedPrChangedPayload, PrAnalysisService
from sibyl.pr_analysis.domain.models import (
    ContributingFactor,
    PrRiskContext,
    RiskAssessment,
)

PAYLOAD = {
    "number": 55,
    "repository": {"full_name": "acme/service-test"},
    "pull_request": {
        "head": {"sha": "head-sha"},
        "base": {"sha": "base-sha"},
        "user": {"login": "octocat"},
        "changed_files": 4,
        "additions": 80,
        "deletions": 20,
    },
    "files": [{"filename": "a.py"}],
}


async def test_handle_pr_changed_persists_pull_request_and_assessment(db_session):
    service = PrAnalysisService(
        PrAnalysisRepository(), OutboxRepository(PrAnalysisOutboxEvent), FakeReasoningPort()
    )
    installation_id = uuid.uuid4()

    await service.handle_pr_changed(db_session, installation_id, PAYLOAD)

    result = await PrAnalysisRepository().get_latest_assessment(db_session, "acme/service-test", 55)
    assert result is not None
    pr, assessment = result
    assert pr.installation_id == installation_id
    assert assessment.llm_model == "fake-reasoning-port"


async def test_handle_pr_changed_publishes_completion_event(db_session):
    service = PrAnalysisService(
        PrAnalysisRepository(), OutboxRepository(PrAnalysisOutboxEvent), FakeReasoningPort()
    )
    installation_id = uuid.uuid4()

    await service.handle_pr_changed(db_session, installation_id, {**PAYLOAD, "number": 56})

    stmt = select(PrAnalysisOutboxEvent).where(
        PrAnalysisOutboxEvent.event_type == "pr-analysis.completed",
        PrAnalysisOutboxEvent.installation_id == installation_id,
    )
    events = (await db_session.execute(stmt)).scalars().all()
    assert len(events) == 1
    assert events[0].payload["pr_number"] == 56


async def test_handle_pr_changed_raises_on_malformed_payload(db_session):
    service = PrAnalysisService(
        PrAnalysisRepository(), OutboxRepository(PrAnalysisOutboxEvent), FakeReasoningPort()
    )

    with pytest.raises(MalformedPrChangedPayload):
        await service.handle_pr_changed(db_session, uuid.uuid4(), {"number": 1})


class _RecordingReasoningPort:
    def __init__(self) -> None:
        self.received_contexts: list[PrRiskContext] = []

    async def assess_pr_risk(self, context: PrRiskContext) -> RiskAssessment:
        self.received_contexts.append(context)
        return RiskAssessment(
            score=0.1,
            rationale="recorded",
            contributing_factors=[ContributingFactor(factor="x", weight=0.1)],
            llm_model="recording-port",
        )


async def test_handle_pr_changed_populates_known_flaky_areas_from_changed_files(db_session):
    repository = "acme/known-flaky-test"
    await PrAnalysisRepository().upsert_local_flaky_signal(
        db_session,
        repository=repository,
        test_identifier="tests/test_a.py::test_a",
        flakiness_score=0.9,
        updated_at=datetime.now(UTC),
    )
    await db_session.flush()

    recorder = _RecordingReasoningPort()
    service = PrAnalysisService(
        PrAnalysisRepository(), OutboxRepository(PrAnalysisOutboxEvent), recorder
    )
    payload = {
        **PAYLOAD,
        "number": 57,
        "repository": {"full_name": repository},
        "files": [{"filename": "src/a.py"}],
    }

    await service.handle_pr_changed(db_session, uuid.uuid4(), payload)

    assert len(recorder.received_contexts) == 1
    assert recorder.received_contexts[0].known_flaky_areas == ["tests/test_a.py::test_a"]


async def test_handle_pr_changed_leaves_known_flaky_areas_empty_when_unrelated(db_session):
    repository = "acme/known-flaky-unrelated-test"
    await PrAnalysisRepository().upsert_local_flaky_signal(
        db_session,
        repository=repository,
        test_identifier="tests/test_b.py::test_b",
        flakiness_score=0.9,
        updated_at=datetime.now(UTC),
    )
    await db_session.flush()

    recorder = _RecordingReasoningPort()
    service = PrAnalysisService(
        PrAnalysisRepository(), OutboxRepository(PrAnalysisOutboxEvent), recorder
    )
    payload = {
        **PAYLOAD,
        "number": 58,
        "repository": {"full_name": repository},
        "files": [{"filename": "src/unrelated.py"}],
    }

    await service.handle_pr_changed(db_session, uuid.uuid4(), payload)

    assert recorder.received_contexts[0].known_flaky_areas == []
