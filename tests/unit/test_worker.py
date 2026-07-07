import uuid
from contextlib import asynccontextmanager
from typing import Any

from sibyl.dependency_analysis.adapters.repository import DependencyAnalysisRepository
from sibyl.dependency_analysis.application import DependencyAnalysisService
from sibyl.platform.events.outbox import OutboxRepository
from sibyl.pr_analysis.adapters.db_models import LocalFlakySignalProjection, PrAnalysisOutboxEvent
from sibyl.pr_analysis.adapters.fake_reasoning import FakeReasoningPort
from sibyl.pr_analysis.adapters.repository import PrAnalysisRepository
from sibyl.pr_analysis.application import PrAnalysisService
from sibyl.root_cause_analysis.adapters.db_models import RootCauseAnalysisOutboxEvent
from sibyl.root_cause_analysis.adapters.fake_reasoning import (
    FakeReasoningPort as RootCauseFakeReasoningPort,
)
from sibyl.root_cause_analysis.adapters.repository import RootCauseAnalysisRepository
from sibyl.root_cause_analysis.application import RootCauseAnalysisService
from sibyl.test_intelligence.adapters.db_models import TestIntelligenceOutboxEvent
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository
from sibyl.test_intelligence.application import TestIntelligenceService
from sibyl.worker import (
    make_ci_run_completed_handler,
    make_coverage_report_received_handler,
    make_dependency_manifest_received_handler,
    make_dispatcher,
    make_flaky_signal_updated_handler,
    make_pr_changed_handler,
    make_root_cause_ci_run_completed_handler,
    make_root_cause_flaky_signal_updated_handler,
    make_root_cause_impact_computed_handler,
    make_root_cause_pr_analysis_completed_handler,
    make_test_intelligence_pr_changed_handler,
)

PAYLOAD = {
    "number": 77,
    "repository": {"full_name": "acme/worker-test"},
    "pull_request": {
        "head": {"sha": "h"},
        "base": {"sha": "b"},
        "user": {"login": "octocat"},
        "changed_files": 1,
        "additions": 1,
        "deletions": 1,
    },
    "files": [],
}


async def test_handler_processes_envelope_and_persists_result(db_session):
    @asynccontextmanager
    async def session_scope():
        yield db_session

    service = PrAnalysisService(
        PrAnalysisRepository(), OutboxRepository(PrAnalysisOutboxEvent), FakeReasoningPort()
    )
    handler = make_pr_changed_handler(session_scope, service)
    installation_id = uuid.uuid4()

    await handler({"installation_id": str(installation_id), "payload": PAYLOAD})

    result = await PrAnalysisRepository().get_latest_assessment(db_session, "acme/worker-test", 77)
    assert result is not None
    assert result[0].installation_id == installation_id


async def test_dispatcher_routes_to_the_matching_handler():
    calls = []

    async def handler_a(envelope):
        calls.append(("a", envelope))

    async def handler_b(envelope):
        calls.append(("b", envelope))

    dispatcher = make_dispatcher(
        {"type-a": handler_a, "type-b": handler_b}, group_name="test-group"
    )

    await dispatcher({"event_type": "type-b", "payload": {}})

    assert calls == [("b", {"event_type": "type-b", "payload": {}})]


async def test_dispatcher_ignores_unknown_event_type_without_raising():
    async def handler_a(envelope):
        raise AssertionError("should not be called")

    dispatcher = make_dispatcher({"type-a": handler_a}, group_name="test-group")

    await dispatcher({"event_type": "unknown-type", "payload": {}})


async def test_test_intelligence_handlers_correlate_across_two_calls(db_session):
    @asynccontextmanager
    async def session_scope():
        yield db_session

    service = TestIntelligenceService(
        TestIntelligenceRepository(), OutboxRepository(TestIntelligenceOutboxEvent)
    )
    pr_changed_handler = make_test_intelligence_pr_changed_handler(session_scope, service)
    ci_run_handler = make_ci_run_completed_handler(session_scope, service)
    installation_id = uuid.uuid4()

    await pr_changed_handler(
        {
            "installation_id": str(installation_id),
            "payload": {
                "number": 1,
                "repository": {"full_name": "acme/worker-ti-test"},
                "pull_request": {"head": {"sha": "sha-ti"}},
                "files": [{"filename": "src/x.py"}],
            },
        }
    )
    await ci_run_handler(
        {
            "installation_id": str(installation_id),
            "payload": {
                "repository": "acme/worker-ti-test",
                "commit_sha": "sha-ti",
                "ci_run_id": 1,
                "started_at": "2026-07-02T00:00:00Z",
                "completed_at": "2026-07-02T00:01:00Z",
                "tests": [{"test_identifier": "tests/test_x.py::test_x", "status": "passed"}],
            },
        }
    )

    impact = await TestIntelligenceRepository().get_latest_test_impact(
        db_session, "acme/worker-ti-test", 1
    )
    assert impact is not None


async def test_flaky_signal_updated_handler_projects_into_pr_analysis(db_session):
    @asynccontextmanager
    async def session_scope():
        yield db_session

    handler = make_flaky_signal_updated_handler(session_scope, PrAnalysisRepository())

    await handler(
        {
            "installation_id": str(uuid.uuid4()),
            "payload": {
                "repository": "acme/worker-flaky-test",
                "test_identifier": "tests/test_flaky.py::test_flaky",
                "flakiness_score": 0.6,
            },
        }
    )

    projection = await db_session.get(
        LocalFlakySignalProjection,
        ("tests/test_flaky.py::test_flaky", "acme/worker-flaky-test"),
    )
    assert projection is not None
    assert projection.flakiness_score == 0.6


async def test_flaky_signal_updated_handler_updates_existing_projection(db_session):
    @asynccontextmanager
    async def session_scope():
        yield db_session

    handler = make_flaky_signal_updated_handler(session_scope, PrAnalysisRepository())
    installation_id = str(uuid.uuid4())

    def _envelope(flakiness_score: float) -> dict[str, Any]:
        return {
            "installation_id": installation_id,
            "payload": {
                "repository": "acme/worker-flaky-update-test",
                "test_identifier": "tests/test_flaky.py::test_flaky",
                "flakiness_score": flakiness_score,
            },
        }

    await handler(_envelope(0.2))
    await handler(_envelope(0.9))

    projection = await db_session.get(
        LocalFlakySignalProjection,
        ("tests/test_flaky.py::test_flaky", "acme/worker-flaky-update-test"),
    )
    assert projection is not None
    assert projection.flakiness_score == 0.9


async def test_root_cause_handlers_correlate_across_three_calls(db_session):
    @asynccontextmanager
    async def session_scope():
        yield db_session

    service = RootCauseAnalysisService(
        RootCauseAnalysisRepository(),
        OutboxRepository(RootCauseAnalysisOutboxEvent),
        RootCauseFakeReasoningPort(),
    )
    ci_run_handler = make_root_cause_ci_run_completed_handler(session_scope, service)
    pr_analysis_handler = make_root_cause_pr_analysis_completed_handler(session_scope, service)
    impact_handler = make_root_cause_impact_computed_handler(session_scope, service)
    installation_id = str(uuid.uuid4())
    repository = "acme/worker-rca-test"

    await ci_run_handler(
        {
            "installation_id": installation_id,
            "payload": {
                "repository": repository,
                "commit_sha": "sha-rca",
                "ci_run_id": 1,
                "tests": [{"test_identifier": "tests/test_x.py::test_x", "status": "failed"}],
            },
        }
    )
    await pr_analysis_handler(
        {
            "installation_id": installation_id,
            "payload": {
                "repository": repository,
                "pr_number": 1,
                "head_sha": "sha-rca",
                "score": 0.5,
                "rationale": "risk",
                "explanation_unavailable": False,
            },
        }
    )
    await impact_handler(
        {
            "installation_id": installation_id,
            "payload": {
                "repository": repository,
                "pr_number": 1,
                "affected_tests": ["tests/test_x.py::test_x"],
            },
        }
    )

    failure_events = await RootCauseAnalysisRepository().get_failure_events_by_commit(
        db_session, repository, "sha-rca"
    )
    assert len(failure_events) == 1
    hypothesis = await RootCauseAnalysisRepository().get_latest_hypothesis(
        db_session, failure_events[0].id
    )
    assert hypothesis is not None


async def test_root_cause_flaky_signal_updated_handler_projects_locally(db_session):
    @asynccontextmanager
    async def session_scope():
        yield db_session

    service = RootCauseAnalysisService(
        RootCauseAnalysisRepository(),
        OutboxRepository(RootCauseAnalysisOutboxEvent),
        RootCauseFakeReasoningPort(),
    )
    handler = make_root_cause_flaky_signal_updated_handler(session_scope, service)

    await handler(
        {
            "installation_id": str(uuid.uuid4()),
            "payload": {
                "repository": "acme/worker-rca-flaky-test",
                "test_identifier": "tests/test_y.py::test_y",
                "flakiness_score": 0.3,
            },
        }
    )

    signal = await RootCauseAnalysisRepository().get_flaky_signal(
        db_session, "acme/worker-rca-flaky-test", "tests/test_y.py::test_y"
    )
    assert signal is not None
    assert signal.flakiness_score == 0.3


async def test_coverage_report_received_handler_upserts_file_coverage_signal(db_session):
    @asynccontextmanager
    async def session_scope():
        yield db_session

    service = TestIntelligenceService(
        TestIntelligenceRepository(), OutboxRepository(TestIntelligenceOutboxEvent)
    )
    handler = make_coverage_report_received_handler(session_scope, service)

    await handler(
        {
            "installation_id": str(uuid.uuid4()),
            "payload": {
                "repository": "acme/worker-coverage-test",
                "commit_sha": "sha-1",
                "files": [{"file_path": "src/a.py", "lines_covered": 7, "lines_total": 10}],
            },
        }
    )

    signal = await TestIntelligenceRepository().get_file_coverage_signal(
        db_session, "acme/worker-coverage-test", "src/a.py"
    )
    assert signal is not None
    assert signal.coverage_pct == 0.7


async def test_dependency_manifest_received_handler_persists_snapshot(db_session):
    @asynccontextmanager
    async def session_scope():
        yield db_session

    service = DependencyAnalysisService(DependencyAnalysisRepository())
    handler = make_dependency_manifest_received_handler(session_scope, service)

    await handler(
        {
            "installation_id": str(uuid.uuid4()),
            "payload": {
                "repository": "acme/worker-dependency-test",
                "commit_sha": "sha-1",
                "ecosystem": "npm",
                "packages": [{"name": "left-pad", "version": "1.3.0", "direct": True}],
            },
        }
    )

    snapshots = await DependencyAnalysisRepository().get_latest_snapshots_by_repository(
        db_session, "acme/worker-dependency-test"
    )
    assert len(snapshots) == 1
    assert snapshots[0].ecosystem == "npm"
