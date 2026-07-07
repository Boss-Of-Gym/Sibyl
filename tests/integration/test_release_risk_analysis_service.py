import uuid
from typing import Any

from sqlalchemy import select

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.release_risk_analysis.adapters.db_models import ReleaseRiskOutboxEvent
from sibyl.release_risk_analysis.adapters.repository import ReleaseRiskAnalysisRepository
from sibyl.release_risk_analysis.application import ReleaseRiskAnalysisService


def _service() -> ReleaseRiskAnalysisService:
    return ReleaseRiskAnalysisService(
        ReleaseRiskAnalysisRepository(), OutboxRepository(ReleaseRiskOutboxEvent)
    )


def _ci_run_completed_payload(repository: str, ci_run_id: int) -> dict[str, Any]:
    return {
        "repository": repository,
        "commit_sha": "sha-1",
        "ci_run_id": ci_run_id,
        "started_at": "2026-07-07T10:00:00Z",
        "completed_at": "2026-07-07T10:05:00Z",
        "tests": [
            {"test_identifier": "test_a", "status": "passed"},
            {"test_identifier": "test_b", "status": "failed"},
        ],
    }


def _coverage_computed_payload(
    repository: str, file_path: str, coverage_pct: float
) -> dict[str, Any]:
    return {
        "repository": repository,
        "file_path": file_path,
        "coverage_pct": coverage_pct,
        "computed_at": "2026-07-07T10:00:00Z",
    }


def _regression_prediction_completed_payload(
    repository: str, pr_number: int, head_sha: str, regression_probability: float
) -> dict[str, Any]:
    return {
        "repository": repository,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "regression_probability": regression_probability,
        "rationale": "looks risky",
        "explanation_unavailable": False,
    }


async def _get_completed_events(
    db_session, installation_id: uuid.UUID
) -> list[ReleaseRiskOutboxEvent]:
    stmt = select(ReleaseRiskOutboxEvent).where(
        ReleaseRiskOutboxEvent.event_type == "release-risk.completed",
        ReleaseRiskOutboxEvent.installation_id == installation_id,
    )
    return list((await db_session.execute(stmt)).scalars().all())


async def test_handle_ci_run_completed_upserts_ci_health(db_session):
    repository = ReleaseRiskAnalysisRepository()
    service = _service()
    installation_id = uuid.uuid4()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_run_completed_payload("acme/rr-service-a", 1)
    )

    rows = await repository.get_recent_ci_runs(db_session, "acme/rr-service-a")
    assert len(rows) == 1
    assert rows[0].passed_count == 1
    assert rows[0].failed_count == 1


async def test_handle_coverage_computed_upserts_coverage_signal(db_session):
    repository = ReleaseRiskAnalysisRepository()
    service = _service()
    installation_id = uuid.uuid4()

    await service.handle_coverage_computed(
        db_session,
        installation_id,
        _coverage_computed_payload("acme/rr-service-b", "src/a.py", 0.75),
    )

    rows = await repository.get_coverage_signals(db_session, "acme/rr-service-b")
    assert len(rows) == 1
    assert rows[0].coverage_pct == 0.75


async def test_handle_regression_prediction_completed_fuses_available_signals_and_publishes(
    db_session,
):
    repo_name = "acme/rr-service-c"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_run_completed_payload(repo_name, 1)
    )
    await service.handle_coverage_computed(
        db_session, installation_id, _coverage_computed_payload(repo_name, "src/a.py", 0.9)
    )

    await service.handle_regression_prediction_completed(
        db_session,
        installation_id,
        _regression_prediction_completed_payload(repo_name, 42, "sha-head", 0.6),
    )

    repository = ReleaseRiskAnalysisRepository()
    assessment = await repository.get_latest_assessment(db_session, repo_name, 42)
    assert assessment is not None
    assert assessment.regression_probability == 0.6
    assert assessment.ci_success_rate == 0.0
    assert assessment.coverage_pct == 0.9
    assert set(assessment.considered_signals) == {
        "regression_probability",
        "ci_success_rate",
        "coverage_pct",
    }

    events = await _get_completed_events(db_session, installation_id)
    assert len(events) == 1
    assert events[0].payload["risk_score"] == assessment.risk_score


async def test_handle_regression_prediction_completed_with_no_other_signals_yet(db_session):
    repo_name = "acme/rr-service-d"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_regression_prediction_completed(
        db_session,
        installation_id,
        _regression_prediction_completed_payload(repo_name, 7, "sha-head", 0.3),
    )

    repository = ReleaseRiskAnalysisRepository()
    assessment = await repository.get_latest_assessment(db_session, repo_name, 7)
    assert assessment is not None
    assert assessment.risk_score == 0.3
    assert assessment.considered_signals == ["regression_probability"]
    assert assessment.ci_success_rate is None
    assert assessment.coverage_pct is None
