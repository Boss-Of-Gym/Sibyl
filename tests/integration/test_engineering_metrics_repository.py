import uuid
from datetime import UTC, datetime, timedelta

from sibyl.engineering_metrics.adapters.repository import EngineeringMetricsRepository

repository = EngineeringMetricsRepository()


async def test_upsert_pr_lifecycle_creates_then_updates(db_session):
    installation_id = uuid.uuid4()
    opened_at = datetime.now(UTC) - timedelta(days=1)

    await repository.upsert_pr_lifecycle(
        db_session,
        installation_id=installation_id,
        repository="acme/em-repo-a",
        pr_number=1,
        opened_at=opened_at,
        merged_at=None,
        closed_at=None,
        merged=False,
    )
    await db_session.flush()

    merged_at = datetime.now(UTC)
    updated = await repository.upsert_pr_lifecycle(
        db_session,
        installation_id=installation_id,
        repository="acme/em-repo-a",
        pr_number=1,
        opened_at=opened_at,
        merged_at=merged_at,
        closed_at=merged_at,
        merged=True,
    )

    assert updated.merged is True
    assert updated.merged_at == merged_at


async def test_upsert_ci_run_creates_then_updates(db_session):
    installation_id = uuid.uuid4()
    started_at = datetime.now(UTC) - timedelta(minutes=10)
    completed_at = datetime.now(UTC)

    await repository.upsert_ci_run(
        db_session,
        installation_id=installation_id,
        repository="acme/em-repo-b",
        ci_run_id=100,
        commit_sha="sha-1",
        started_at=started_at,
        completed_at=completed_at,
        passed_count=10,
        failed_count=0,
        skipped_count=0,
    )
    await db_session.flush()

    updated = await repository.upsert_ci_run(
        db_session,
        installation_id=installation_id,
        repository="acme/em-repo-b",
        ci_run_id=100,
        commit_sha="sha-2",
        started_at=started_at,
        completed_at=completed_at,
        passed_count=8,
        failed_count=2,
        skipped_count=0,
    )

    assert updated.commit_sha == "sha-2"
    assert updated.failed_count == 2


async def test_get_pr_lifecycle_in_window_excludes_prs_before_since(db_session):
    installation_id = uuid.uuid4()
    now = datetime.now(UTC)

    await repository.upsert_pr_lifecycle(
        db_session,
        installation_id=installation_id,
        repository="acme/em-repo-c",
        pr_number=1,
        opened_at=now - timedelta(days=40),
        merged_at=None,
        closed_at=None,
        merged=False,
    )
    await repository.upsert_pr_lifecycle(
        db_session,
        installation_id=installation_id,
        repository="acme/em-repo-c",
        pr_number=2,
        opened_at=now - timedelta(days=1),
        merged_at=None,
        closed_at=None,
        merged=False,
    )
    await db_session.flush()

    rows = await repository.get_pr_lifecycle_in_window(
        db_session, "acme/em-repo-c", now - timedelta(days=30)
    )

    assert [row.pr_number for row in rows] == [2]


async def test_get_ci_runs_in_window_excludes_runs_before_since(db_session):
    installation_id = uuid.uuid4()
    now = datetime.now(UTC)

    await repository.upsert_ci_run(
        db_session,
        installation_id=installation_id,
        repository="acme/em-repo-d",
        ci_run_id=1,
        commit_sha="sha-old",
        started_at=now - timedelta(days=40),
        completed_at=now - timedelta(days=40),
        passed_count=1,
        failed_count=0,
        skipped_count=0,
    )
    await repository.upsert_ci_run(
        db_session,
        installation_id=installation_id,
        repository="acme/em-repo-d",
        ci_run_id=2,
        commit_sha="sha-new",
        started_at=now - timedelta(days=1),
        completed_at=now - timedelta(days=1),
        passed_count=1,
        failed_count=0,
        skipped_count=0,
    )
    await db_session.flush()

    rows = await repository.get_ci_runs_in_window(
        db_session, "acme/em-repo-d", now - timedelta(days=30)
    )

    assert [row.ci_run_id for row in rows] == [2]
