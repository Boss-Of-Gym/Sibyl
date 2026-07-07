import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from sibyl.engineering_metrics.adapters.repository import EngineeringMetricsRepository
from sibyl.engineering_metrics.application import (
    EngineeringMetricsService,
    MalformedPrChangedPayload,
)

_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


def _service() -> EngineeringMetricsService:
    return EngineeringMetricsService(EngineeringMetricsRepository())


def _pr_changed_payload(
    repository: str,
    pr_number: int,
    created_at: str,
    merged_at: str | None,
    closed_at: str | None,
    merged: bool,
) -> dict[str, Any]:
    return {
        "number": pr_number,
        "repository": {"full_name": repository},
        "pull_request": {
            "created_at": created_at,
            "merged_at": merged_at,
            "closed_at": closed_at,
            "merged": merged,
        },
    }


def _ci_run_completed_payload(
    repository: str, ci_run_id: int, commit_sha: str
) -> dict[str, Any]:
    return {
        "repository": repository,
        "commit_sha": commit_sha,
        "ci_run_id": ci_run_id,
        "started_at": "2026-07-01T10:00:00Z",
        "completed_at": "2026-07-01T10:05:00Z",
        "tests": [
            {"test_identifier": "test_a", "status": "passed"},
            {"test_identifier": "test_b", "status": "failed"},
            {"test_identifier": "test_c", "status": "skipped"},
        ],
    }


async def test_handle_pr_changed_persists_open_pr(db_session):
    repository = EngineeringMetricsRepository()
    service = _service()
    installation_id = uuid.uuid4()

    await service.handle_pr_changed(
        db_session,
        installation_id,
        _pr_changed_payload(
            "acme/em-service-a", 1, "2026-07-01T10:00:00Z", None, None, False
        ),
    )

    rows = await repository.get_pr_lifecycle_in_window(db_session, "acme/em-service-a", _EPOCH)
    assert len(rows) == 1
    assert rows[0].merged is False
    assert rows[0].merged_at is None


async def test_handle_pr_changed_raises_on_malformed_payload(db_session):
    service = _service()

    with pytest.raises(MalformedPrChangedPayload):
        await service.handle_pr_changed(db_session, uuid.uuid4(), {"not": "a real payload"})


async def test_handle_pr_changed_reflects_mixed_lifecycle_states(db_session):
    repository = EngineeringMetricsRepository()
    service = _service()
    installation_id = uuid.uuid4()
    repo_name = "acme/em-service-b"

    await service.handle_pr_changed(
        db_session,
        installation_id,
        _pr_changed_payload(repo_name, 1, "2026-07-01T10:00:00Z", None, None, False),
    )
    await service.handle_pr_changed(
        db_session,
        installation_id,
        _pr_changed_payload(
            repo_name,
            2,
            "2026-07-01T10:00:00Z",
            "2026-07-01T12:00:00Z",
            "2026-07-01T12:00:00Z",
            True,
        ),
    )
    await service.handle_pr_changed(
        db_session,
        installation_id,
        _pr_changed_payload(
            repo_name, 3, "2026-07-01T10:00:00Z", None, "2026-07-01T11:00:00Z", False
        ),
    )

    rows = await repository.get_pr_lifecycle_in_window(db_session, repo_name, _EPOCH)
    by_number = {row.pr_number: row for row in rows}

    assert by_number[1].merged is False and by_number[1].closed_at is None
    assert by_number[2].merged is True and by_number[2].merged_at is not None
    assert by_number[3].merged is False and by_number[3].closed_at is not None


async def test_handle_ci_run_completed_counts_test_statuses(db_session):
    repository = EngineeringMetricsRepository()
    service = _service()
    installation_id = uuid.uuid4()

    await service.handle_ci_run_completed(
        db_session,
        installation_id,
        _ci_run_completed_payload("acme/em-service-c", 500, "sha-1"),
    )

    rows = await repository.get_ci_runs_in_window(db_session, "acme/em-service-c", _EPOCH)
    assert len(rows) == 1
    assert rows[0].passed_count == 1
    assert rows[0].failed_count == 1
    assert rows[0].skipped_count == 1
