import uuid
from typing import Any

from sqlalchemy import select

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.root_cause_analysis.adapters.db_models import RootCauseAnalysisOutboxEvent
from sibyl.root_cause_analysis.adapters.fake_reasoning import FakeReasoningPort
from sibyl.root_cause_analysis.adapters.repository import RootCauseAnalysisRepository
from sibyl.root_cause_analysis.application import RootCauseAnalysisService
from sibyl.root_cause_analysis.domain.models import RootCauseContext, RootCauseExplanation
from sibyl.root_cause_analysis.domain.ports import ReasoningPort


class RecordingReasoningPort:
    def __init__(self) -> None:
        self.received_contexts: list[RootCauseContext] = []

    async def explain_root_cause(self, context: RootCauseContext) -> RootCauseExplanation:
        self.received_contexts.append(context)
        return RootCauseExplanation(
            hypothesis_text="recorded",
            confidence=0.5,
            llm_model="recording-port",
        )


def _service(reasoning_port: ReasoningPort | None = None) -> RootCauseAnalysisService:
    return RootCauseAnalysisService(
        RootCauseAnalysisRepository(),
        OutboxRepository(RootCauseAnalysisOutboxEvent),
        reasoning_port or FakeReasoningPort(),
    )


def _ci_run_payload(
    repository: str, commit_sha: str, ci_run_id: int, test_identifier: str
) -> dict[str, Any]:
    return {
        "repository": repository,
        "commit_sha": commit_sha,
        "ci_run_id": ci_run_id,
        "tests": [{"test_identifier": test_identifier, "status": "failed"}],
    }


def _pr_analysis_completed_payload(
    repository: str, pr_number: int, head_sha: str
) -> dict[str, Any]:
    return {
        "repository": repository,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "score": 0.4,
        "rationale": "some risk",
        "explanation_unavailable": False,
    }


def _impact_computed_payload(
    repository: str, pr_number: int, affected_tests: list[str]
) -> dict[str, Any]:
    return {"repository": repository, "pr_number": pr_number, "affected_tests": affected_tests}


async def _get_hypothesis_ready_events(
    db_session, installation_id
) -> list[RootCauseAnalysisOutboxEvent]:
    stmt = select(RootCauseAnalysisOutboxEvent).where(
        RootCauseAnalysisOutboxEvent.event_type == "root-cause.hypothesis-ready",
        RootCauseAnalysisOutboxEvent.installation_id == installation_id,
    )
    return list((await db_session.execute(stmt)).scalars().all())


async def test_failure_event_arriving_last_triggers_correlation(db_session):
    repository = "acme/rca-service-a"
    installation_id = uuid.uuid4()
    test_identifier = "tests/test_a.py::test_a"
    service = _service()

    await service.handle_pr_analysis_completed(
        db_session, installation_id, _pr_analysis_completed_payload(repository, 1, "sha-a")
    )
    await service.handle_impact_computed(
        db_session, installation_id, _impact_computed_payload(repository, 1, [test_identifier])
    )
    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_run_payload(repository, "sha-a", 1, test_identifier)
    )

    events = await _get_hypothesis_ready_events(db_session, installation_id)
    assert len(events) == 1
    assert events[0].payload["test_identifier"] == test_identifier
    assert events[0].payload["head_sha"] == "sha-a"
    assert events[0].payload["explanation_unavailable"] is False


async def test_pr_context_arriving_last_triggers_correlation(db_session):
    repository = "acme/rca-service-b"
    installation_id = uuid.uuid4()
    test_identifier = "tests/test_b.py::test_b"
    service = _service()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_run_payload(repository, "sha-b", 1, test_identifier)
    )
    await service.handle_impact_computed(
        db_session, installation_id, _impact_computed_payload(repository, 1, [test_identifier])
    )
    await service.handle_pr_analysis_completed(
        db_session, installation_id, _pr_analysis_completed_payload(repository, 1, "sha-b")
    )

    events = await _get_hypothesis_ready_events(db_session, installation_id)
    assert len(events) == 1


async def test_test_impact_arriving_last_triggers_correlation(db_session):
    repository = "acme/rca-service-c"
    installation_id = uuid.uuid4()
    test_identifier = "tests/test_c.py::test_c"
    service = _service()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_run_payload(repository, "sha-c", 1, test_identifier)
    )
    await service.handle_pr_analysis_completed(
        db_session, installation_id, _pr_analysis_completed_payload(repository, 1, "sha-c")
    )
    await service.handle_impact_computed(
        db_session, installation_id, _impact_computed_payload(repository, 1, [test_identifier])
    )

    events = await _get_hypothesis_ready_events(db_session, installation_id)
    assert len(events) == 1


async def test_correlation_does_not_recompute_once_a_hypothesis_exists(db_session):
    repository = "acme/rca-service-d"
    installation_id = uuid.uuid4()
    test_identifier = "tests/test_d.py::test_d"
    service = _service()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_run_payload(repository, "sha-d", 1, test_identifier)
    )
    await service.handle_pr_analysis_completed(
        db_session, installation_id, _pr_analysis_completed_payload(repository, 1, "sha-d")
    )
    await service.handle_impact_computed(
        db_session, installation_id, _impact_computed_payload(repository, 1, [test_identifier])
    )
    await service.handle_impact_computed(
        db_session, installation_id, _impact_computed_payload(repository, 1, [test_identifier])
    )

    events = await _get_hypothesis_ready_events(db_session, installation_id)
    assert len(events) == 1


async def test_no_hypothesis_without_pr_context(db_session):
    repository = "acme/rca-service-e"
    installation_id = uuid.uuid4()
    service = _service()

    payload = _ci_run_payload(repository, "sha-e", 1, "tests/test_e.py::test_e")
    await service.handle_ci_run_completed(db_session, installation_id, payload)

    events = await _get_hypothesis_ready_events(db_session, installation_id)
    assert events == []


async def test_flakiness_score_is_included_in_context_when_available(db_session):
    repository = "acme/rca-service-f"
    installation_id = uuid.uuid4()
    test_identifier = "tests/test_f.py::test_f"
    recorder = RecordingReasoningPort()
    service = _service(recorder)

    await service.handle_flaky_signal_updated(
        db_session,
        installation_id,
        {"repository": repository, "test_identifier": test_identifier, "flakiness_score": 0.8},
    )
    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_run_payload(repository, "sha-f", 1, test_identifier)
    )
    await service.handle_pr_analysis_completed(
        db_session, installation_id, _pr_analysis_completed_payload(repository, 1, "sha-f")
    )
    await service.handle_impact_computed(
        db_session, installation_id, _impact_computed_payload(repository, 1, [test_identifier])
    )

    assert len(recorder.received_contexts) == 1
    assert recorder.received_contexts[0].flakiness_score == 0.8


async def test_flakiness_score_is_none_when_never_reported(db_session):
    repository = "acme/rca-service-g"
    installation_id = uuid.uuid4()
    test_identifier = "tests/test_g.py::test_g"
    recorder = RecordingReasoningPort()
    service = _service(recorder)

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_run_payload(repository, "sha-g", 1, test_identifier)
    )
    await service.handle_pr_analysis_completed(
        db_session, installation_id, _pr_analysis_completed_payload(repository, 1, "sha-g")
    )
    await service.handle_impact_computed(
        db_session, installation_id, _impact_computed_payload(repository, 1, [test_identifier])
    )

    assert len(recorder.received_contexts) == 1
    assert recorder.received_contexts[0].flakiness_score is None


async def test_passing_tests_do_not_create_failure_events(db_session):
    repository = "acme/rca-service-h"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_ci_run_completed(
        db_session,
        installation_id,
        {
            "repository": repository,
            "commit_sha": "sha-h",
            "ci_run_id": 1,
            "tests": [{"test_identifier": "tests/test_h.py::test_h", "status": "passed"}],
        },
    )
    await service.handle_pr_analysis_completed(
        db_session, installation_id, _pr_analysis_completed_payload(repository, 1, "sha-h")
    )
    await service.handle_impact_computed(
        db_session,
        installation_id,
        _impact_computed_payload(repository, 1, ["tests/test_h.py::test_h"]),
    )

    events = await _get_hypothesis_ready_events(db_session, installation_id)
    assert events == []
