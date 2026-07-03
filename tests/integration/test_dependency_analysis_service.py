import uuid

from sibyl.dependency_analysis.adapters.repository import DependencyAnalysisRepository
from sibyl.dependency_analysis.application import DependencyAnalysisService


def _service() -> DependencyAnalysisService:
    return DependencyAnalysisService(DependencyAnalysisRepository())


async def test_handle_manifest_received_persists_snapshot(db_session):
    repository = "acme/dependency-service-a"
    installation_id = uuid.uuid4()
    service = _service()

    await service.handle_manifest_received(
        db_session,
        installation_id,
        {
            "repository": repository,
            "commit_sha": "sha-1",
            "ecosystem": "npm",
            "packages": [
                {"name": "left-pad", "version": "1.3.0", "direct": True},
                {"name": "transitive-dep", "version": "0.1.0", "direct": False},
            ],
        },
    )

    snapshots = await DependencyAnalysisRepository().get_latest_snapshots_by_repository(
        db_session, repository
    )

    assert len(snapshots) == 1
    assert snapshots[0].commit_sha == "sha-1"
    assert snapshots[0].packages == [
        {"name": "left-pad", "version": "1.3.0", "direct": True},
        {"name": "transitive-dep", "version": "0.1.0", "direct": False},
    ]
