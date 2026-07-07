import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.root_cause_analysis.adapters.db_models import FailureEvent
from sibyl.root_cause_analysis.adapters.repository import RootCauseAnalysisRepository
from sibyl.root_cause_analysis.domain.models import CiRunCompletedReport, RootCauseContext
from sibyl.root_cause_analysis.domain.ports import ReasoningPort


class RootCauseAnalysisService:
    def __init__(
        self,
        repository: RootCauseAnalysisRepository,
        outbox: OutboxRepository[Any],
        reasoning_port: ReasoningPort,
    ):
        self._repository = repository
        self._outbox = outbox
        self._reasoning_port = reasoning_port

    async def handle_ci_run_completed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        report = CiRunCompletedReport.model_validate(payload)
        now = datetime.now(UTC)

        for test in report.tests:
            if test.status != "failed":
                continue
            failure_event = await self._repository.upsert_failure_event(
                session,
                installation_id=installation_id,
                repository=report.repository,
                test_identifier=test.test_identifier,
                commit_sha=report.commit_sha,
                ci_run_id=report.ci_run_id,
                detected_at=now,
            )
            await self._try_correlate(session, installation_id, failure_event)

        await session.commit()

    async def handle_pr_analysis_completed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        repository = payload["repository"]
        pr_number = payload["pr_number"]
        head_sha = payload["head_sha"]
        now = datetime.now(UTC)

        await self._repository.upsert_pr_context_projection(
            session,
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            risk_score=payload.get("score"),
            explanation_unavailable=payload.get("explanation_unavailable", False),
            received_at=now,
        )

        for failure_event in await self._repository.get_failure_events_by_commit(
            session, repository, head_sha
        ):
            await self._try_correlate(session, installation_id, failure_event)

        await session.commit()

    async def handle_impact_computed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        repository = payload["repository"]
        pr_number = payload["pr_number"]
        now = datetime.now(UTC)

        await self._repository.upsert_test_impact_projection(
            session,
            installation_id=installation_id,
            repository=repository,
            pr_number=pr_number,
            affected_tests=payload.get("affected_tests", []),
            received_at=now,
        )

        pr_context = await self._repository.get_pr_context(session, repository, pr_number)
        if pr_context is not None:
            for failure_event in await self._repository.get_failure_events_by_commit(
                session, repository, pr_context.head_sha
            ):
                await self._try_correlate(session, installation_id, failure_event)

        await session.commit()

    async def handle_flaky_signal_updated(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        await self._repository.upsert_flaky_signal(
            session,
            repository=payload["repository"],
            test_identifier=payload["test_identifier"],
            flakiness_score=payload["flakiness_score"],
            updated_at=datetime.now(UTC),
        )
        await session.commit()

    async def _try_correlate(
        self, session: AsyncSession, installation_id: uuid.UUID, failure_event: FailureEvent
    ) -> None:
        if await self._repository.get_latest_hypothesis(session, failure_event.id) is not None:
            return

        pr_context = await self._repository.get_pr_context_by_head_sha(
            session, failure_event.repository, failure_event.commit_sha
        )
        if pr_context is None:
            return

        test_impact = await self._repository.get_test_impact(
            session, failure_event.repository, pr_context.pr_number
        )
        if test_impact is None:
            return

        flaky_signal = await self._repository.get_flaky_signal(
            session, failure_event.repository, failure_event.test_identifier
        )

        context = RootCauseContext(
            repository=failure_event.repository,
            test_identifier=failure_event.test_identifier,
            commit_sha=failure_event.commit_sha,
            pr_number=pr_context.pr_number,
            head_sha=pr_context.head_sha,
            risk_score=pr_context.risk_score,
            affected_tests=test_impact.affected_tests,
            flakiness_score=flaky_signal.flakiness_score if flaky_signal is not None else None,
        )

        explanation = await self._reasoning_port.explain_root_cause(context)
        now = datetime.now(UTC)

        await self._repository.save_hypothesis(
            session,
            failure_event_id=failure_event.id,
            hypothesis_text=explanation.hypothesis_text,
            confidence=explanation.confidence,
            suspected_commit_sha=explanation.suspected_commit_sha,
            suspected_file_path=explanation.suspected_file_path,
            llm_model=explanation.llm_model,
            llm_tokens_used=explanation.llm_tokens_used,
            llm_latency_ms=explanation.llm_latency_ms,
            computed_at=now,
        )

        await self._outbox.add(
            session,
            event_type="root-cause.hypothesis-ready",
            installation_id=installation_id,
            payload={
                "repository": failure_event.repository,
                "pr_number": pr_context.pr_number,
                "head_sha": pr_context.head_sha,
                "failure_event_id": str(failure_event.id),
                "test_identifier": failure_event.test_identifier,
                "hypothesis_text": explanation.hypothesis_text,
                "confidence": explanation.confidence,
                "suspected_file_path": explanation.suspected_file_path,
                "explanation_unavailable": explanation.explanation_unavailable,
            },
            occurred_at=now,
        )
