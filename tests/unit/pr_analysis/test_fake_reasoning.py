from sibyl.pr_analysis.adapters.fake_reasoning import FakeReasoningPort
from sibyl.pr_analysis.domain.models import ContributingFactor, PrRiskContext, RiskAssessment

CONTEXT = PrRiskContext(
    repository="acme/widgets",
    pr_number=1,
    head_sha="a",
    base_sha="b",
    author_login="octocat",
    files_changed=2,
    additions=10,
    deletions=5,
    changed_file_paths=["a.py", "b.py"],
)


async def test_score_scales_with_change_size():
    small = await FakeReasoningPort().assess_pr_risk(
        CONTEXT.model_copy(update={"files_changed": 1, "additions": 1, "deletions": 0})
    )
    large = await FakeReasoningPort().assess_pr_risk(
        CONTEXT.model_copy(update={"files_changed": 20, "additions": 500, "deletions": 500})
    )

    assert small.score < large.score


async def test_score_is_capped_at_one():
    huge = CONTEXT.model_copy(update={"files_changed": 1000, "additions": 100000, "deletions": 0})

    result = await FakeReasoningPort().assess_pr_risk(huge)

    assert result.score == 1.0


async def test_canned_response_overrides_computed_score():
    canned = RiskAssessment(
        score=0.42,
        rationale="canned",
        contributing_factors=[ContributingFactor(factor="test", weight=1.0)],
        llm_model="canned-model",
    )

    result = await FakeReasoningPort(canned_response=canned).assess_pr_risk(CONTEXT)

    assert result is canned
