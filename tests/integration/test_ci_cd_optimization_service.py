import uuid
from typing import Any

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.test_intelligence.adapters.db_models import TestIntelligenceOutboxEvent
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository
from sibyl.test_intelligence.application import TestIntelligenceService

REPOSITORY = "acme/ci-cd-service-test"
TEST_IDENTIFIER = "tests/test_slow.py::test_slow"


def _service() -> TestIntelligenceService:
    return TestIntelligenceService(
        TestIntelligenceRepository(), OutboxRepository(TestIntelligenceOutboxEvent)
    )


def _ci_payload(
    repository: str, commit_sha: str, ci_run_id: int, duration_ms: int
) -> dict[str, Any]:
    return {
        "repository": repository,
        "commit_sha": commit_sha,
        "ci_run_id": ci_run_id,
        "started_at": "2026-07-02T00:00:00Z",
        "completed_at": f"2026-07-02T00:{ci_run_id:02d}:00Z",
        "tests": [
            {"test_identifier": TEST_IDENTIFIER, "status": "passed", "duration_ms": duration_ms}
        ],
    }


async def test_duration_signal_recomputes_median_across_ci_runs(db_session):
    repository = "acme/ci-cd-service-median"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-1", 1, 100)
    )
    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-2", 2, 300)
    )
    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-3", 3, 200)
    )

    signal = await TestIntelligenceRepository().get_duration_signal(
        db_session, repository, TEST_IDENTIFIER
    )
    assert signal is not None
    assert signal.median_duration_ms == 200.0
    assert signal.sample_size == 3


async def test_duration_signal_is_independent_of_flakiness_signal(db_session):
    repository = "acme/ci-cd-service-independent"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_ci_run_completed(
        db_session, installation_id, _ci_payload(repository, "sha-1", 1, 5000)
    )

    duration_signal = await TestIntelligenceRepository().get_duration_signal(
        db_session, repository, TEST_IDENTIFIER
    )
    stability_signal = await TestIntelligenceRepository().get_stability_signal(
        db_session, repository, TEST_IDENTIFIER
    )

    assert duration_signal is not None
    assert duration_signal.median_duration_ms == 5000.0
    assert stability_signal is not None
    assert stability_signal.flakiness_score == 0.0
