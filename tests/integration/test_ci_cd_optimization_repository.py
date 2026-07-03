import uuid
from datetime import UTC, datetime, timedelta

from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository
from sibyl.test_intelligence.domain.models import TestResultItem

repository = TestIntelligenceRepository()


async def test_get_recent_durations_orders_most_recent_first(db_session):
    base_time = datetime.now(UTC)
    for i, duration in enumerate([100, 200, 300]):
        await repository.upsert_test_run(
            db_session,
            installation_id=uuid.uuid4(),
            repository="acme/duration-repo-a",
            commit_sha=f"sha-a-{i}",
            ci_run_id=i,
            started_at=base_time + timedelta(minutes=i),
            completed_at=base_time + timedelta(minutes=i),
            tests=[
                TestResultItem(
                    test_identifier="tests/test_a.py::test_a",
                    status="passed",
                    duration_ms=duration,
                )
            ],
        )
    await db_session.flush()

    durations = await repository.get_recent_durations(
        db_session, "acme/duration-repo-a", "tests/test_a.py::test_a"
    )

    assert durations == [300, 200, 100]


async def test_upsert_duration_signal_creates_then_updates(db_session):
    installation_id = uuid.uuid4()
    await repository.upsert_duration_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/duration-repo-b",
        test_identifier="tests/test_b.py::test_b",
        median_duration_ms=150.0,
        sample_size=3,
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    updated = await repository.upsert_duration_signal(
        db_session,
        installation_id=installation_id,
        repository="acme/duration-repo-b",
        test_identifier="tests/test_b.py::test_b",
        median_duration_ms=500.0,
        sample_size=5,
        computed_at=datetime.now(UTC),
    )

    assert updated.median_duration_ms == 500.0
    assert updated.sample_size == 5

    fetched = await repository.get_duration_signal(
        db_session, "acme/duration-repo-b", "tests/test_b.py::test_b"
    )
    assert fetched is not None
    assert fetched.median_duration_ms == 500.0


async def test_list_slow_tests_excludes_flaky_tests(db_session):
    repository_name = "acme/duration-repo-c"
    installation_id = uuid.uuid4()
    now = datetime.now(UTC)

    await repository.upsert_duration_signal(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        test_identifier="tests/test_slow_stable.py::test_it",
        median_duration_ms=9000.0,
        sample_size=10,
        computed_at=now,
    )
    await repository.upsert_duration_signal(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        test_identifier="tests/test_slow_flaky.py::test_it",
        median_duration_ms=8000.0,
        sample_size=10,
        computed_at=now,
    )
    await repository.upsert_stability_signal(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        test_identifier="tests/test_slow_flaky.py::test_it",
        flakiness_score=0.6,
        sample_size=10,
        computed_at=now,
    )
    await db_session.flush()

    rows = await repository.list_slow_tests(db_session, repository_name)

    identifiers = [signal.test_identifier for signal, _ in rows]
    assert identifiers == ["tests/test_slow_stable.py::test_it"]


async def test_list_slow_tests_orders_by_median_duration_descending(db_session):
    repository_name = "acme/duration-repo-d"
    installation_id = uuid.uuid4()
    now = datetime.now(UTC)

    for test_identifier, duration in [
        ("tests/test_fast.py::test_it", 100.0),
        ("tests/test_slowest.py::test_it", 9999.0),
        ("tests/test_medium.py::test_it", 1500.0),
    ]:
        await repository.upsert_duration_signal(
            db_session,
            installation_id=installation_id,
            repository=repository_name,
            test_identifier=test_identifier,
            median_duration_ms=duration,
            sample_size=5,
            computed_at=now,
        )
    await db_session.flush()

    rows = await repository.list_slow_tests(db_session, repository_name)

    identifiers = [signal.test_identifier for signal, _ in rows]
    assert identifiers == [
        "tests/test_slowest.py::test_it",
        "tests/test_medium.py::test_it",
        "tests/test_fast.py::test_it",
    ]


async def test_list_slow_tests_includes_flakiness_score_when_present(db_session):
    repository_name = "acme/duration-repo-e"
    installation_id = uuid.uuid4()
    now = datetime.now(UTC)

    await repository.upsert_duration_signal(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        test_identifier="tests/test_e.py::test_it",
        median_duration_ms=2000.0,
        sample_size=5,
        computed_at=now,
    )
    await repository.upsert_stability_signal(
        db_session,
        installation_id=installation_id,
        repository=repository_name,
        test_identifier="tests/test_e.py::test_it",
        flakiness_score=0.1,
        sample_size=5,
        computed_at=now,
    )
    await db_session.flush()

    rows = await repository.list_slow_tests(db_session, repository_name)

    assert len(rows) == 1
    signal, flakiness_score = rows[0]
    assert signal.test_identifier == "tests/test_e.py::test_it"
    assert flakiness_score == 0.1


async def test_list_slow_tests_respects_limit(db_session):
    repository_name = "acme/duration-repo-f"
    installation_id = uuid.uuid4()
    now = datetime.now(UTC)

    for i in range(5):
        await repository.upsert_duration_signal(
            db_session,
            installation_id=installation_id,
            repository=repository_name,
            test_identifier=f"tests/test_f{i}.py::test_it",
            median_duration_ms=float(i),
            sample_size=5,
            computed_at=now,
        )
    await db_session.flush()

    rows = await repository.list_slow_tests(db_session, repository_name, limit=2)

    assert len(rows) == 2
