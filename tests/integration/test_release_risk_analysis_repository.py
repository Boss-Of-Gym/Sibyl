import uuid
from datetime import UTC, datetime, timedelta

from sibyl.release_risk_analysis.adapters.repository import ReleaseRiskAnalysisRepository

repository = ReleaseRiskAnalysisRepository()


async def test_upsert_regression_signal_creates_then_updates(db_session):
    installation_id = uuid.uuid4()

    await repository.upsert_regression_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/rr-repo-a",
        pr_number=1,
        head_sha="sha-1",
        regression_probability=0.3,
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    updated = await repository.upsert_regression_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/rr-repo-a",
        pr_number=1,
        head_sha="sha-2",
        regression_probability=0.7,
        computed_at=datetime.now(UTC),
    )

    assert updated.head_sha == "sha-2"
    assert updated.regression_probability == 0.7


async def test_upsert_ci_run_creates_then_updates(db_session):
    installation_id = uuid.uuid4()

    await repository.upsert_ci_run(
        db_session,
        installation_id=installation_id,
        repository="acme/rr-repo-b",
        ci_run_id=100,
        passed_count=10,
        failed_count=0,
        completed_at=datetime.now(UTC),
    )
    await db_session.flush()

    updated = await repository.upsert_ci_run(
        db_session,
        installation_id=installation_id,
        repository="acme/rr-repo-b",
        ci_run_id=100,
        passed_count=8,
        failed_count=2,
        completed_at=datetime.now(UTC),
    )

    assert updated.failed_count == 2


async def test_upsert_coverage_signal_creates_then_updates(db_session):
    installation_id = uuid.uuid4()

    await repository.upsert_coverage_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/rr-repo-c",
        file_path="src/a.py",
        coverage_pct=0.5,
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    updated = await repository.upsert_coverage_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/rr-repo-c",
        file_path="src/a.py",
        coverage_pct=0.9,
        computed_at=datetime.now(UTC),
    )

    assert updated.coverage_pct == 0.9


async def test_get_recent_ci_runs_respects_limit_and_recency_order(db_session):
    installation_id = uuid.uuid4()
    now = datetime.now(UTC)

    for i in range(3):
        await repository.upsert_ci_run(
            db_session,
            installation_id=installation_id,
            repository="acme/rr-repo-d",
            ci_run_id=i,
            passed_count=1,
            failed_count=0,
            completed_at=now - timedelta(minutes=3 - i),
        )
    await db_session.flush()

    rows = await repository.get_recent_ci_runs(db_session, "acme/rr-repo-d", limit=2)

    assert [row.ci_run_id for row in rows] == [2, 1]


async def test_get_coverage_signals_returns_all_files_for_repository(db_session):
    installation_id = uuid.uuid4()

    await repository.upsert_coverage_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/rr-repo-e",
        file_path="src/a.py",
        coverage_pct=0.5,
        computed_at=datetime.now(UTC),
    )
    await repository.upsert_coverage_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/rr-repo-e",
        file_path="src/b.py",
        coverage_pct=0.9,
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    rows = await repository.get_coverage_signals(db_session, "acme/rr-repo-e")

    assert {row.file_path for row in rows} == {"src/a.py", "src/b.py"}


async def test_save_and_get_latest_assessment(db_session):
    installation_id = uuid.uuid4()

    assert await repository.get_latest_assessment(db_session, "acme/rr-repo-f", 1) is None

    await repository.save_assessment(
        db_session,
        installation_id=installation_id,
        repository="acme/rr-repo-f",
        pr_number=1,
        head_sha="sha-1",
        risk_score=0.4,
        considered_signals=["regression_probability", "ci_success_rate"],
        regression_probability=0.4,
        ci_success_rate=0.9,
        coverage_pct=None,
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    result = await repository.get_latest_assessment(db_session, "acme/rr-repo-f", 1)

    assert result is not None
    assert result.risk_score == 0.4
    assert result.considered_signals == ["regression_probability", "ci_success_rate"]
    assert result.coverage_pct is None
