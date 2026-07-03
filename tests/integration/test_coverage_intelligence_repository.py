import uuid
from datetime import UTC, datetime, timedelta

from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository

repository = TestIntelligenceRepository()


async def test_upsert_file_coverage_signal_creates_then_updates(db_session):
    installation_id = uuid.uuid4()
    await repository.upsert_file_coverage_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/coverage-repo-a",
        file_path="src/a.py",
        commit_sha="sha-1",
        lines_covered=5,
        lines_total=10,
        coverage_pct=0.5,
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    updated = await repository.upsert_file_coverage_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/coverage-repo-a",
        file_path="src/a.py",
        commit_sha="sha-2",
        lines_covered=9,
        lines_total=10,
        coverage_pct=0.9,
        computed_at=datetime.now(UTC),
    )

    assert updated.commit_sha == "sha-2"
    assert updated.coverage_pct == 0.9

    fetched = await repository.get_file_coverage_signal(
        db_session, "acme/coverage-repo-a", "src/a.py"
    )
    assert fetched is not None
    assert fetched.coverage_pct == 0.9


async def test_get_recently_changed_files_dedupes_across_prs(db_session):
    repository_name = "acme/coverage-repo-b"
    installation_id = uuid.uuid4()
    base_time = datetime.now(UTC)

    await repository.upsert_pr_changed_files(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-b-1",
        pr_number=1,
        changed_file_paths=["src/a.py", "src/b.py"],
        received_at=base_time,
    )
    await repository.upsert_pr_changed_files(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-b-2",
        pr_number=2,
        changed_file_paths=["src/b.py", "src/c.py"],
        received_at=base_time + timedelta(minutes=1),
    )
    await db_session.flush()

    files = await repository.get_recently_changed_files(db_session, repository_name)

    assert set(files) == {"src/a.py", "src/b.py", "src/c.py"}


async def test_get_recently_changed_files_respects_pr_window(db_session):
    repository_name = "acme/coverage-repo-c"
    installation_id = uuid.uuid4()
    base_time = datetime.now(UTC)

    for i in range(3):
        await repository.upsert_pr_changed_files(
            db_session,
            installation_id=installation_id,
            repository=repository_name,
            commit_sha=f"sha-c-{i}",
            pr_number=i,
            changed_file_paths=[f"src/file_{i}.py"],
            received_at=base_time + timedelta(minutes=i),
        )
    await db_session.flush()

    files = await repository.get_recently_changed_files(db_session, repository_name, pr_window=1)

    assert files == ["src/file_2.py"]


async def test_list_coverage_gaps_ranks_no_signal_files_first(db_session):
    repository_name = "acme/coverage-repo-d"
    installation_id = uuid.uuid4()
    now = datetime.now(UTC)

    await repository.upsert_pr_changed_files(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-d-1",
        pr_number=1,
        changed_file_paths=["src/known.py", "src/unknown.py"],
        received_at=now,
    )
    await repository.upsert_file_coverage_signal(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        file_path="src/known.py",
        commit_sha="sha-d-1",
        lines_covered=9,
        lines_total=10,
        coverage_pct=0.9,
        computed_at=now,
    )
    await db_session.flush()

    gaps = await repository.list_coverage_gaps(db_session, repository_name)

    assert gaps[0] == ("src/unknown.py", None)
    assert gaps[1][0] == "src/known.py"
    assert gaps[1][1] is not None
    assert gaps[1][1].coverage_pct == 0.9


async def test_list_coverage_gaps_orders_known_signals_ascending(db_session):
    repository_name = "acme/coverage-repo-e"
    installation_id = uuid.uuid4()
    now = datetime.now(UTC)

    await repository.upsert_pr_changed_files(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-e-1",
        pr_number=1,
        changed_file_paths=["src/high.py", "src/low.py"],
        received_at=now,
    )
    await repository.upsert_file_coverage_signal(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        file_path="src/high.py",
        commit_sha="sha-e-1",
        lines_covered=9,
        lines_total=10,
        coverage_pct=0.9,
        computed_at=now,
    )
    await repository.upsert_file_coverage_signal(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        file_path="src/low.py",
        commit_sha="sha-e-1",
        lines_covered=1,
        lines_total=10,
        coverage_pct=0.1,
        computed_at=now,
    )
    await db_session.flush()

    gaps = await repository.list_coverage_gaps(db_session, repository_name)

    assert [path for path, _ in gaps] == ["src/low.py", "src/high.py"]


async def test_list_coverage_gaps_respects_limit(db_session):
    repository_name = "acme/coverage-repo-f"
    installation_id = uuid.uuid4()
    now = datetime.now(UTC)

    await repository.upsert_pr_changed_files(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-f-1",
        pr_number=1,
        changed_file_paths=[f"src/file_{i}.py" for i in range(5)],
        received_at=now,
    )
    await db_session.flush()

    gaps = await repository.list_coverage_gaps(db_session, repository_name, limit=2)

    assert len(gaps) == 2


async def test_list_coverage_gaps_returns_empty_when_no_files_changed(db_session):
    gaps = await repository.list_coverage_gaps(db_session, "acme/coverage-repo-empty")

    assert gaps == []
