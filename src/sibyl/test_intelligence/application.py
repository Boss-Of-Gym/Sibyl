import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.platform.events.errors import MalformedEventError
from sibyl.platform.events.outbox import OutboxRepository
from sibyl.test_intelligence.adapters.repository import TestIntelligenceRepository
from sibyl.test_intelligence.domain.coverage import compute_coverage_pct
from sibyl.test_intelligence.domain.duration import compute_median_duration
from sibyl.test_intelligence.domain.flakiness import compute_flakiness, is_material_change
from sibyl.test_intelligence.domain.mapping import map_changed_files_to_affected_tests
from sibyl.test_intelligence.domain.models import CoverageReport, TestResultReport


class MalformedPrChangedPayload(MalformedEventError):
    pass


def _extract_changed_files(payload: dict[str, Any]) -> tuple[str, str, int, list[str]]:
    try:
        repository = payload["repository"]["full_name"]
        head_sha = payload["pull_request"]["head"]["sha"]
        pr_number = payload["number"]
    except KeyError as exc:
        raise MalformedPrChangedPayload(str(exc)) from exc
    changed_file_paths = [f["filename"] for f in payload.get("files", [])]
    return repository, head_sha, pr_number, changed_file_paths


class TestIntelligenceService:
    def __init__(self, repository: TestIntelligenceRepository, outbox: OutboxRepository[Any]):
        self._repository = repository
        self._outbox = outbox

    async def handle_pr_changed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        repository, commit_sha, pr_number, changed_file_paths = _extract_changed_files(payload)

        await self._repository.upsert_pr_changed_files(
            session,
            installation_id=installation_id,
            repository=repository,
            commit_sha=commit_sha,
            pr_number=pr_number,
            changed_file_paths=changed_file_paths,
            received_at=datetime.now(UTC),
        )

        test_run = await self._repository.get_test_run(session, repository, commit_sha)
        if test_run is not None:
            await self._compute_and_publish_impact(
                session, installation_id, repository, pr_number, commit_sha, changed_file_paths
            )
        await session.commit()

    async def handle_ci_run_completed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        report = TestResultReport.model_validate(payload)

        await self._repository.upsert_test_run(
            session,
            installation_id=installation_id,
            repository=report.repository,
            commit_sha=report.commit_sha,
            ci_run_id=report.ci_run_id,
            started_at=report.started_at,
            completed_at=report.completed_at,
            tests=report.tests,
        )

        for test_identifier in {t.test_identifier for t in report.tests}:
            await self._recompute_flakiness(
                session, installation_id, report.repository, test_identifier
            )
            await self._recompute_duration(
                session, installation_id, report.repository, test_identifier
            )

        projection = await self._repository.get_pr_changed_files(
            session, report.repository, report.commit_sha
        )
        if projection is not None:
            await self._compute_and_publish_impact(
                session,
                installation_id,
                report.repository,
                projection.pr_number,
                report.commit_sha,
                projection.changed_file_paths,
            )
        await session.commit()

    async def handle_coverage_report_received(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        report = CoverageReport.model_validate(payload)
        now = datetime.now(UTC)

        for file in report.files:
            coverage_pct = compute_coverage_pct(file.lines_covered, file.lines_total)
            await self._repository.upsert_file_coverage_signal(
                session,
                installation_id=installation_id,
                repository=report.repository,
                file_path=file.file_path,
                commit_sha=report.commit_sha,
                lines_covered=file.lines_covered,
                lines_total=file.lines_total,
                coverage_pct=coverage_pct,
                computed_at=now,
            )
            await self._outbox.add(
                session,
                event_type="test-intelligence.coverage-computed",
                installation_id=installation_id,
                payload={
                    "repository": report.repository,
                    "file_path": file.file_path,
                    "coverage_pct": coverage_pct,
                    "computed_at": now.isoformat(),
                },
                occurred_at=now,
            )

        await session.commit()

    async def _compute_and_publish_impact(
        self,
        session: AsyncSession,
        installation_id: uuid.UUID,
        repository: str,
        pr_number: int,
        commit_sha: str,
        changed_file_paths: list[str],
    ) -> None:
        known_test_identifiers = await self._repository.get_observed_test_identifiers(
            session, repository
        )
        affected_tests = map_changed_files_to_affected_tests(
            changed_file_paths, known_test_identifiers
        )
        now = datetime.now(UTC)

        await self._repository.save_test_impact(
            session,
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            commit_sha=commit_sha,
            affected_tests=affected_tests,
            computed_at=now,
        )

        await self._outbox.add(
            session,
            event_type="test-intelligence.impact-computed",
            installation_id=installation_id,
            payload={
                "repository": repository,
                "pr_number": pr_number,
                "affected_tests": affected_tests,
            },
            occurred_at=now,
        )

    async def _recompute_flakiness(
        self,
        session: AsyncSession,
        installation_id: uuid.UUID,
        repository: str,
        test_identifier: str,
    ) -> None:
        recent_statuses = await self._repository.get_recent_statuses(
            session, repository, test_identifier
        )
        score, sample_size = compute_flakiness(recent_statuses)
        if sample_size == 0:
            return

        existing_signal = await self._repository.get_stability_signal(
            session, repository, test_identifier
        )
        previous_score = existing_signal.flakiness_score if existing_signal is not None else None
        now = datetime.now(UTC)

        await self._repository.upsert_stability_signal(
            session,
            installation_id=installation_id,
            repository=repository,
            test_identifier=test_identifier,
            flakiness_score=score,
            sample_size=sample_size,
            computed_at=now,
        )

        if is_material_change(previous_score, score):
            await self._outbox.add(
                session,
                event_type="test-intelligence.flaky-signal-updated",
                installation_id=installation_id,
                payload={
                    "repository": repository,
                    "test_identifier": test_identifier,
                    "flakiness_score": score,
                },
                occurred_at=now,
            )

    async def _recompute_duration(
        self,
        session: AsyncSession,
        installation_id: uuid.UUID,
        repository: str,
        test_identifier: str,
    ) -> None:
        recent_durations = await self._repository.get_recent_durations(
            session, repository, test_identifier
        )
        median_duration_ms, sample_size = compute_median_duration(recent_durations)
        if sample_size == 0:
            return

        await self._repository.upsert_duration_signal(
            session,
            installation_id=installation_id,
            repository=repository,
            test_identifier=test_identifier,
            median_duration_ms=median_duration_ms,
            sample_size=sample_size,
            computed_at=datetime.now(UTC),
        )
