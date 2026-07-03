import uuid
from datetime import UTC, datetime
from typing import Any

from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository
from sibyl.test_intelligence.domain.models import TestResultItem

repository = TestIntelligenceRepository()


async def test_upsert_pr_changed_files_creates_new_row(db_session):
    row = await repository.upsert_pr_changed_files(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/repo-a",
        commit_sha="sha-1",
        pr_number=1,
        changed_file_paths=["a.py"],
        received_at=datetime.now(UTC),
    )

    assert row.changed_file_paths == ["a.py"]


async def test_upsert_pr_changed_files_updates_existing_row(db_session):
    await repository.upsert_pr_changed_files(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/repo-b",
        commit_sha="sha-2",
        pr_number=2,
        changed_file_paths=["a.py"],
        received_at=datetime.now(UTC),
    )

    updated = await repository.upsert_pr_changed_files(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/repo-b",
        commit_sha="sha-2",
        pr_number=2,
        changed_file_paths=["a.py", "b.py"],
        received_at=datetime.now(UTC),
    )

    assert updated.changed_file_paths == ["a.py", "b.py"]


async def test_upsert_test_run_is_idempotent_for_same_commit(db_session):
    tests = [TestResultItem(test_identifier="tests/test_x.py::test_x", status="passed")]
    kwargs: dict[str, Any] = dict(
        installation_id=uuid.uuid4(),
        repository="acme/repo-c",
        commit_sha="sha-3",
        ci_run_id=1,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        tests=tests,
    )

    first = await repository.upsert_test_run(db_session, **kwargs)
    await db_session.flush()
    second = await repository.upsert_test_run(db_session, **kwargs)

    assert first.id == second.id
    observed = await repository.get_observed_test_identifiers(db_session, "acme/repo-c")
    assert observed == ["tests/test_x.py::test_x"]


async def test_get_observed_test_identifiers_scoped_per_repository(db_session):
    tests = [TestResultItem(test_identifier="tests/test_y.py::test_y", status="passed")]
    await repository.upsert_test_run(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/repo-d",
        commit_sha="sha-4",
        ci_run_id=1,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        tests=tests,
    )

    observed_other_repo = await repository.get_observed_test_identifiers(
        db_session, "acme/unrelated-repo"
    )

    assert observed_other_repo == []


async def test_save_and_get_latest_test_impact(db_session):
    installation_id = uuid.uuid4()
    await repository.save_test_impact(
        db_session,
        installation_id=installation_id,
        repository="acme/repo-e",
        pr_number=5,
        commit_sha="sha-5",
        affected_tests=["tests/test_z.py::test_z"],
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    impact = await repository.get_latest_test_impact(db_session, "acme/repo-e", 5)

    assert impact is not None
    assert [t.test_identifier for t in impact.affected_tests] == ["tests/test_z.py::test_z"]
