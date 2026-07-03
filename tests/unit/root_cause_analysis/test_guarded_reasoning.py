import asyncio

from sibyl.root_cause_analysis.adapters.guarded_reasoning import GuardedReasoningPort
from sibyl.root_cause_analysis.domain.models import RootCauseContext, RootCauseExplanation

CONTEXT = RootCauseContext(
    repository="acme/widgets",
    test_identifier="tests/test_x.py::test_x",
    commit_sha="sha-1",
    pr_number=1,
    head_sha="sha-1",
    risk_score=None,
    affected_tests=[],
    flakiness_score=None,
)


class _SucceedingDelegate:
    async def explain_root_cause(self, context: RootCauseContext) -> RootCauseExplanation:
        return RootCauseExplanation(hypothesis_text="ok", confidence=0.5, llm_model="delegate")


class _RaisingDelegate:
    async def explain_root_cause(self, context: RootCauseContext) -> RootCauseExplanation:
        raise RuntimeError("provider exploded")


class _HangingDelegate:
    async def explain_root_cause(self, context: RootCauseContext) -> RootCauseExplanation:
        await asyncio.sleep(10)
        raise AssertionError("should have timed out first")


async def test_successful_delegate_call_passes_through():
    port = GuardedReasoningPort(_SucceedingDelegate())

    result = await port.explain_root_cause(CONTEXT)

    assert result.llm_model == "delegate"
    assert result.explanation_unavailable is False


async def test_delegate_error_falls_back_without_raising():
    port = GuardedReasoningPort(_RaisingDelegate())

    result = await port.explain_root_cause(CONTEXT)

    assert result.explanation_unavailable is True
    assert result.confidence == 0.0


async def test_delegate_timeout_falls_back_without_raising():
    port = GuardedReasoningPort(_HangingDelegate(), timeout_seconds=0.05)

    result = await port.explain_root_cause(CONTEXT)

    assert result.explanation_unavailable is True
