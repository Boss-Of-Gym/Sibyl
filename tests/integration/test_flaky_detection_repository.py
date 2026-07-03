import uuid
from datetime import UTC, datetime, timedelta

from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository
from sibyl.test_intelligence.domain.models import TestResultItem, TestStatus

repository = TestIntelligenceRepository()


async def test_get_recent_statuses_orders_most_recent_first(db_session):
    base_time = datetime.now(UTC)
    statuses_to_record: list[TestStatus] = ["passed", "failed", "passed"]
    for i, status in enumerate(statuses_to_record):
        await repository.upsert_test_run(
            db_session,
            installation_id=uuid.uuid4(),
            repository="acme/flaky-repo-a",
            commit_sha=f"sha-a-{i}",
            ci_run_id=i,
            started_at=base_time + timedelta(minutes=i),
            completed_at=base_time + timedelta(minutes=i),
            tests=[TestResultItem(test_identifier="tests/test_a.py::test_a", status=status)],
        )
    await db_session.flush()

    statuses = await repository.get_recent_statuses(
        db_session, "acme/flaky-repo-a", "tests/test_a.py::test_a"
    )

    assert statuses == ["passed", "failed", "passed"]


async def test_get_recent_statuses_scoped_per_test_identifier(db_session):
    await repository.upsert_test_run(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/flaky-repo-b",
        commit_sha="sha-b-1",
        ci_run_id=1,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        tests=[
            TestResultItem(test_identifier="tests/test_b.py::test_b", status="passed"),
            TestResultItem(test_identifier="tests/test_c.py::test_c", status="failed"),
        ],
    )
    await db_session.flush()

    statuses = await repository.get_recent_statuses(
        db_session, "acme/flaky-repo-b", "tests/test_b.py::test_b"
    )

    assert statuses == ["passed"]


async def test_upsert_stability_signal_creates_new_row(db_session):
    await repository.upsert_stability_signal(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/flaky-repo-c",
        test_identifier="tests/test_d.py::test_d",
        flakiness_score=0.4,
        sample_size=5,
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    fetched = await repository.get_stability_signal(
        db_session, "acme/flaky-repo-c", "tests/test_d.py::test_d"
    )

    assert fetched is not None
    assert fetched.flakiness_score == 0.4
    assert fetched.sample_size == 5


async def test_upsert_stability_signal_updates_existing_row(db_session):
    installation_id = uuid.uuid4()
    await repository.upsert_stability_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/flaky-repo-d",
        test_identifier="tests/test_e.py::test_e",
        flakiness_score=0.2,
        sample_size=3,
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    updated = await repository.upsert_stability_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/flaky-repo-d",
        test_identifier="tests/test_e.py::test_e",
        flakiness_score=0.8,
        sample_size=4,
        computed_at=datetime.now(UTC),
    )

    assert updated.flakiness_score == 0.8
    assert updated.sample_size == 4

    fetched = await repository.get_stability_signal(
        db_session, "acme/flaky-repo-d", "tests/test_e.py::test_e"
    )
    assert fetched is not None
    assert fetched.flakiness_score == 0.8


async def test_get_stability_signal_returns_none_when_absent(db_session):
    fetched = await repository.get_stability_signal(
        db_session, "acme/flaky-repo-nonexistent", "tests/test_z.py::test_z"
    )

    assert fetched is None
