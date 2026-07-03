import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sibyl.platform.events.outbox import OutboxRepository
from sibyl.pr_analysis.adapters.repository import PrAnalysisRepository
from sibyl.pr_analysis.domain.flaky_matching import match_known_flaky_areas
from sibyl.pr_analysis.domain.models import PrRiskContext
from sibyl.pr_analysis.domain.ports import ReasoningPort


class MalformedPrChangedPayload(Exception):
    pass


def _extract_context(payload: dict[str, Any]) -> PrRiskContext:
    try:
        pr = payload["pull_request"]
        repository = payload["repository"]["full_name"]
        return PrRiskContext(
            repository=repository,
            pr_number=payload["number"],
            head_sha=pr["head"]["sha"],
            base_sha=pr["base"]["sha"],
            author_login=pr["user"]["login"],
            files_changed=pr.get("changed_files", 0),
            additions=pr.get("additions", 0),
            deletions=pr.get("deletions", 0),
            changed_file_paths=[f["filename"] for f in payload.get("files", [])],
        )
    except KeyError as exc:
        raise MalformedPrChangedPayload(str(exc)) from exc


class PrAnalysisService:
    def __init__(
        self,
        repository: PrAnalysisRepository,
        outbox: OutboxRepository[Any],
        reasoning_port: ReasoningPort,
    ):
        self._repository = repository
        self._outbox = outbox
        self._reasoning_port = reasoning_port

    async def handle_pr_changed(
        self, session: AsyncSession, installation_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        context = _extract_context(payload)
        now = datetime.now(UTC)

        flaky_signals = await self._repository.get_flaky_signals(session, context.repository)
        context = context.model_copy(
            update={
                "known_flaky_areas": match_known_flaky_areas(
                    context.changed_file_paths,
                    [(s.test_identifier, s.flakiness_score) for s in flaky_signals],
                )
            }
        )

        pull_request = await self._repository.upsert_pull_request(
            session,
            installation_id=installation_id,
            repository=context.repository,
            pr_number=context.pr_number,
            head_sha=context.head_sha,
            base_sha=context.base_sha,
            author_login=context.author_login,
            files_changed=context.files_changed,
            additions=context.additions,
            deletions=context.deletions,
            opened_at=now,
        )

        assessment = await self._reasoning_port.assess_pr_risk(context)

        await self._repository.add_risk_assessment(session, pull_request, assessment, now)

        await self._outbox.add(
            session,
            event_type="pr-analysis.completed",
            installation_id=installation_id,
            payload={
                "repository": context.repository,
                "pr_number": context.pr_number,
                "head_sha": context.head_sha,
                "score": assessment.score,
                "rationale": assessment.rationale,
                "explanation_unavailable": assessment.explanation_unavailable,
            },
            occurred_at=now,
        )
        await session.commit()
