import uuid
from datetime import UTC, datetime

from sibyl.regression_prediction.adapters.repository import RegressionPredictionRepository

repository = RegressionPredictionRepository()


async def test_upsert_historical_regression_creates_then_updates(db_session):
    failure_event_id = uuid.uuid4()
    installation_id = uuid.uuid4()

    await repository.upsert_historical_regression(
        db_session,
        failure_event_id=failure_event_id,
        installation_id=installation_id,
        repository="acme/repo-a",
        file_path="src/a.py",
        hypothesis_text="first guess",
        confidence=0.4,
        occurred_at=datetime.now(UTC),
    )
    await db_session.flush()

    updated = await repository.upsert_historical_regression(
        db_session,
        failure_event_id=failure_event_id,
        installation_id=installation_id,
        repository="acme/repo-a",
        file_path="src/a.py",
        hypothesis_text="revised guess",
        confidence=0.9,
        occurred_at=datetime.now(UTC),
    )

    assert updated.hypothesis_text == "revised guess"
    assert updated.confidence == 0.9


async def test_get_historical_regressions_by_files_matches_only_requested_paths(db_session):
    installation_id = uuid.uuid4()
    await repository.upsert_historical_regression(
        db_session,
        failure_event_id=uuid.uuid4(),
        installation_id=installation_id,
        repository="acme/repo-b",
        file_path="src/checkout/pricing.py",
        hypothesis_text="pricing regression",
        confidence=0.6,
        occurred_at=datetime.now(UTC),
    )
    await repository.upsert_historical_regression(
        db_session,
        failure_event_id=uuid.uuid4(),
        installation_id=installation_id,
        repository="acme/repo-b",
        file_path="src/checkout/cart.py",
        hypothesis_text="unrelated regression",
        confidence=0.6,
        occurred_at=datetime.now(UTC),
    )
    await db_session.flush()

    matches = await repository.get_historical_regressions_by_files(
        db_session, "acme/repo-b", ["src/checkout/pricing.py"]
    )

    assert len(matches) == 1
    assert matches[0].file_path == "src/checkout/pricing.py"


async def test_get_historical_regressions_by_files_returns_empty_for_no_paths(db_session):
    matches = await repository.get_historical_regressions_by_files(db_session, "acme/repo-c", [])

    assert matches == []


async def test_save_and_get_latest_prediction(db_session):
    installation_id = uuid.uuid4()

    assert await repository.get_latest_prediction(db_session, "acme/repo-d", 42) is None

    await repository.save_prediction(
        db_session,
        installation_id=installation_id,
        repository="acme/repo-d",
        pr_number=42,
        head_sha="sha-1",
        regression_probability=0.7,
        rationale="looks risky",
        contributing_signals=[{"signal": "historical_regression_count", "weight": 0.7}],
        llm_model="test-model",
        llm_tokens_used=123,
        llm_latency_ms=456,
        computed_at=datetime.now(UTC),
    )
    await db_session.flush()

    result = await repository.get_latest_prediction(db_session, "acme/repo-d", 42)

    assert result is not None
    assert result.regression_probability == 0.7
    assert result.llm_tokens_used == 123
    assert result.llm_latency_ms == 456
