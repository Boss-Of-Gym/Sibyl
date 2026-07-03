import uuid
from datetime import UTC, datetime
from typing import Any

from sibyl.pr_analysis.adapters.repository import PrAnalysisRepository
from sibyl.pr_analysis.domain.models import ContributingFactor, RiskAssessment

repository = PrAnalysisRepository()


def _kwargs(**overrides: Any) -> dict[str, Any]:
    base = dict(
        installation_id=uuid.uuid4(),
        repository="acme/widgets",
        pr_number=1,
        head_sha="sha-1",
        base_sha="sha-0",
        author_login="octocat",
        files_changed=2,
        additions=10,
        deletions=5,
        opened_at=datetime.now(UTC),
    )
    base.update(overrides)
    return base


async def test_upsert_creates_a_new_pull_request(db_session):
    pr = await repository.upsert_pull_request(db_session, **_kwargs(repository="acme/repo-a"))

    assert pr.repository == "acme/repo-a"
    assert pr.head_sha == "sha-1"


async def test_upsert_updates_head_sha_on_second_call(db_session):
    kwargs = _kwargs(repository="acme/repo-b", pr_number=7)
    first = await repository.upsert_pull_request(db_session, **kwargs)

    second = await repository.upsert_pull_request(db_session, **{**kwargs, "head_sha": "sha-2"})

    assert first.id == second.id
    assert second.head_sha == "sha-2"


async def test_get_latest_assessment_returns_none_when_absent(db_session):
    result = await repository.get_latest_assessment(db_session, "acme/nonexistent", 999)

    assert result is None


async def test_add_and_fetch_latest_assessment(db_session):
    pr = await repository.upsert_pull_request(db_session, **_kwargs(repository="acme/repo-c"))
    assessment = RiskAssessment(
        score=0.7,
        rationale="looks risky",
        contributing_factors=[ContributingFactor(factor="files_changed", weight=0.7)],
        llm_model="test-model",
    )

    await repository.add_risk_assessment(db_session, pr, assessment, datetime.now(UTC))
    await db_session.flush()

    result = await repository.get_latest_assessment(db_session, "acme/repo-c", pr.pr_number)

    assert result is not None
    fetched_pr, fetched_assessment = result
    assert fetched_pr.id == pr.id
    assert fetched_assessment.score == 0.7
    assert fetched_assessment.llm_model == "test-model"
