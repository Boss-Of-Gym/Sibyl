import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sibyl.dependency_analysis.adapters.repository import DependencyAnalysisRepository

repository = DependencyAnalysisRepository()


async def test_upsert_manifest_snapshot_creates_new_row(db_session):
    snapshot = await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/dependency-repo-a",
        commit_sha="sha-1",
        ecosystem="npm",
        packages=[{"name": "left-pad", "version": "1.3.0", "direct": True}],
        received_at=datetime.now(UTC),
    )

    assert snapshot.packages == [{"name": "left-pad", "version": "1.3.0", "direct": True}]


async def test_upsert_manifest_snapshot_is_idempotent_for_same_commit_and_ecosystem(db_session):
    installation_id = uuid.uuid4()
    kwargs: dict[str, Any] = dict(
        installation_id=installation_id,
        repository="acme/dependency-repo-b",
        commit_sha="sha-1",
        ecosystem="npm",
        received_at=datetime.now(UTC),
    )

    first = await repository.upsert_manifest_snapshot(
        db_session, packages=[{"name": "a", "version": "1.0.0", "direct": True}], **kwargs
    )
    await db_session.flush()
    second = await repository.upsert_manifest_snapshot(
        db_session, packages=[{"name": "a", "version": "1.0.1", "direct": True}], **kwargs
    )

    assert first.id == second.id
    assert second.packages == [{"name": "a", "version": "1.0.1", "direct": True}]


async def test_upsert_manifest_snapshot_keeps_history_across_commits(db_session):
    installation_id = uuid.uuid4()
    repository_name = "acme/dependency-repo-c"

    await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-1",
        ecosystem="npm",
        packages=[{"name": "a", "version": "1.0.0", "direct": True}],
        received_at=datetime.now(UTC),
    )
    await db_session.flush()
    await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-2",
        ecosystem="npm",
        packages=[{"name": "a", "version": "1.1.0", "direct": True}],
        received_at=datetime.now(UTC),
    )
    await db_session.flush()

    snapshots = await repository.get_latest_snapshots_by_repository(db_session, repository_name)

    assert len(snapshots) == 1
    assert snapshots[0].commit_sha == "sha-2"


async def test_get_latest_snapshots_returns_one_per_ecosystem(db_session):
    installation_id = uuid.uuid4()
    repository_name = "acme/dependency-repo-d"
    base_time = datetime.now(UTC)

    await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-1",
        ecosystem="npm",
        packages=[{"name": "a", "version": "1.0.0", "direct": True}],
        received_at=base_time,
    )
    await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-1",
        ecosystem="pypi",
        packages=[{"name": "requests", "version": "2.31.0", "direct": True}],
        received_at=base_time + timedelta(minutes=1),
    )
    await db_session.flush()

    snapshots = await repository.get_latest_snapshots_by_repository(db_session, repository_name)

    assert {s.ecosystem for s in snapshots} == {"npm", "pypi"}


async def test_get_latest_snapshots_returns_empty_for_unknown_repository(db_session):
    snapshots = await repository.get_latest_snapshots_by_repository(
        db_session, "acme/dependency-repo-empty"
    )

    assert snapshots == []


async def test_get_recent_snapshots_returns_most_recent_first(db_session):
    installation_id = uuid.uuid4()
    repository_name = "acme/dependency-repo-e"
    base_time = datetime.now(UTC)

    for i, commit_sha in enumerate(["sha-1", "sha-2", "sha-3"]):
        await repository.upsert_manifest_snapshot(
            db_session,
            installation_id=installation_id,
            repository=repository_name,
            commit_sha=commit_sha,
            ecosystem="npm",
            packages=[{"name": "a", "version": f"1.{i}.0", "direct": True}],
            received_at=base_time + timedelta(minutes=i),
        )
        await db_session.flush()

    recent = await repository.get_recent_snapshots(db_session, repository_name, "npm")

    assert [s.commit_sha for s in recent] == ["sha-3", "sha-2"]


async def test_get_recent_snapshots_scoped_per_ecosystem(db_session):
    installation_id = uuid.uuid4()
    repository_name = "acme/dependency-repo-f"
    base_time = datetime.now(UTC)

    await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-1",
        ecosystem="npm",
        packages=[{"name": "a", "version": "1.0.0", "direct": True}],
        received_at=base_time,
    )
    await repository.upsert_manifest_snapshot(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        commit_sha="sha-1",
        ecosystem="pypi",
        packages=[{"name": "requests", "version": "2.31.0", "direct": True}],
        received_at=base_time,
    )
    await db_session.flush()

    recent = await repository.get_recent_snapshots(db_session, repository_name, "npm")

    assert len(recent) == 1
    assert recent[0].ecosystem == "npm"


async def test_get_recent_snapshots_returns_empty_when_none_exist(db_session):
    recent = await repository.get_recent_snapshots(
        db_session, "acme/dependency-repo-empty-2", "npm"
    )

    assert recent == []
