import uuid
from datetime import UTC, datetime
from typing import Any

from sibyl.root_cause_analysis.adapters.repository import RootCauseAnalysisRepository

repository = RootCauseAnalysisRepository()


async def test_upsert_failure_event_is_idempotent(db_session):
    kwargs: dict[str, Any] = dict(
        installation_id=uuid.uuid4(),
        repository="acme/rca-repo-a",
        test_identifier="tests/test_a.py::test_a",
        commit_sha="sha-1",
        ci_run_id=1,
        detected_at=datetime.now(UTC),
    )

    first = await repository.upsert_failure_event(db_session, **kwargs)
    await db_session.flush()
    second = await repository.upsert_failure_event(db_session, **kwargs)

    assert first.id == second.id


async def test_get_failure_events_by_commit_scoped_per_repository(db_session):
    await repository.upsert_failure_event(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/rca-repo-b",
        test_identifier="tests/test_b.py::test_b",
        commit_sha="sha-2",
        ci_run_id=1,
        detected_at=datetime.now(UTC),
    )
    await db_session.flush()

    same_repo = await repository.get_failure_events_by_commit(
        db_session, "acme/rca-repo-b", "sha-2"
    )
    other_repo = await repository.get_failure_events_by_commit(
        db_session, "acme/other-repo", "sha-2"
    )

    assert len(same_repo) == 1
    assert other_repo == []


async def test_get_failure_event_returns_none_when_absent(db_session):
    result = await repository.get_failure_event(db_session, uuid.uuid4())

    assert result is None


async def test_save_and_get_latest_hypothesis(db_session):
    failure_event = await repository.upsert_failure_event(
        db_session,
        installation_id=uuid.uuid4(),
        repository="acme/rca-repo-c",
        test_identifier="tests/test_c.py::test_c",
        commit_sha="sha-3",
        ci_run_id=1,
        detected_at=datetime.now(UTC),
    )
    await db_session.flush()

    assert await repository.get_latest_hypothesis(db_session, failure_event.id) is None

    await repository.save_hypothesis(
        db_session,
        failure_event_id=failure_event.id,
        hypothesis_text="likely broke because of X",
        confidence=0.7,
        suspected_commit_sha="sha-3",
        suspected_file_path="src/x.py",
        llm_model="fake",
        llm_tokens_used=42,
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    hypothesis = await repository.get_latest_hypothesis(db_session, failure_event.id)
    assert hypothesis is not None
    assert hypothesis.confidence == 0.7
    assert hypothesis.llm_tokens_used == 42


async def test_upsert_pr_context_projection_creates_then_updates(db_session):
    installation_id = uuid.uuid4()
    await repository.upsert_pr_context_projection(
        db_session,
        installation_id=installation_id,
        repository="acme/rca-repo-d",
        pr_number=1,
        head_sha="sha-4",
        risk_score=0.2,
        explanation_unavailable=False,
        received_at=datetime.now(UTC),
    )
    await db_session.flush()

    updated = await repository.upsert_pr_context_projection(
        db_session,
        installation_id=installation_id,
        repository="acme/rca-repo-d",
        pr_number=1,
        head_sha="sha-5",
        risk_score=0.9,
        explanation_unavailable=True,
        received_at=datetime.now(UTC),
    )

    assert updated.head_sha == "sha-5"
    assert updated.risk_score == 0.9

    by_head_sha = await repository.get_pr_context_by_head_sha(
        db_session, "acme/rca-repo-d", "sha-5"
    )
    assert by_head_sha is not None
    assert by_head_sha.pr_number == 1
    stale = await repository.get_pr_context_by_head_sha(db_session, "acme/rca-repo-d", "sha-4")
    assert stale is None


async def test_upsert_test_impact_projection_creates_then_updates(db_session):
    installation_id = uuid.uuid4()
    await repository.upsert_test_impact_projection(
        db_session,
        installation_id=installation_id,
        repository="acme/rca-repo-e",
        pr_number=1,
        affected_tests=["tests/test_e.py::test_e"],
        received_at=datetime.now(UTC),
    )
    await db_session.flush()

    updated = await repository.upsert_test_impact_projection(
        db_session,
        installation_id=installation_id,
        repository="acme/rca-repo-e",
        pr_number=1,
        affected_tests=["tests/test_e.py::test_e", "tests/test_f.py::test_f"],
        received_at=datetime.now(UTC),
    )

    assert updated.affected_tests == ["tests/test_e.py::test_e", "tests/test_f.py::test_f"]


async def test_upsert_flaky_signal_creates_then_updates(db_session):
    await repository.upsert_flaky_signal(
        db_session,
        repository="acme/rca-repo-f",
        test_identifier="tests/test_g.py::test_g",
        flakiness_score=0.1,
        updated_at=datetime.now(UTC),
    )
    await db_session.flush()

    updated = await repository.upsert_flaky_signal(
        db_session,
        repository="acme/rca-repo-f",
        test_identifier="tests/test_g.py::test_g",
        flakiness_score=0.6,
        updated_at=datetime.now(UTC),
    )

    assert updated.flakiness_score == 0.6
    fetched = await repository.get_flaky_signal(
        db_session, "acme/rca-repo-f", "tests/test_g.py::test_g"
    )
    assert fetched is not None
    assert fetched.flakiness_score == 0.6
