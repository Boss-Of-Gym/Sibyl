import asyncio

from sibyl.pr_analysis.adapters.guarded_reasoning import GuardedReasoningPort
from sibyl.pr_analysis.domain.models import ContributingFactor, PrRiskContext, RiskAssessment

CONTEXT = PrRiskContext(
    repository="acme/widgets",
    pr_number=1,
    head_sha="a",
    base_sha="b",
    author_login="octocat",
    files_changed=1,
    additions=1,
    deletions=1,
    changed_file_paths=[],
)


class _SucceedingDelegate:
    async def assess_pr_risk(self, context: PrRiskContext) -> RiskAssessment:
        return RiskAssessment(
            score=0.5,
            rationale="ok",
            contributing_factors=[ContributingFactor(factor="x", weight=0.5)],
            llm_model="delegate",
        )


class _RaisingDelegate:
    async def assess_pr_risk(self, context: PrRiskContext) -> RiskAssessment:
        raise RuntimeError("provider exploded")


class _HangingDelegate:
    async def assess_pr_risk(self, context: PrRiskContext) -> RiskAssessment:
        await asyncio.sleep(10)
        raise AssertionError("should have timed out first")


async def test_successful_delegate_call_passes_through():
    port = GuardedReasoningPort(_SucceedingDelegate())

    result = await port.assess_pr_risk(CONTEXT)

    assert result.llm_model == "delegate"
    assert result.explanation_unavailable is False
    assert result.llm_latency_ms >= 0


async def test_delegate_error_falls_back_without_raising():
    port = GuardedReasoningPort(_RaisingDelegate())

    result = await port.assess_pr_risk(CONTEXT)

    assert result.explanation_unavailable is True
    assert result.llm_latency_ms >= 0


async def test_delegate_timeout_falls_back_without_raising():
    port = GuardedReasoningPort(_HangingDelegate(), timeout_seconds=0.05)

    result = await port.assess_pr_risk(CONTEXT)

    assert result.explanation_unavailable is True
    assert result.llm_latency_ms >= 40
