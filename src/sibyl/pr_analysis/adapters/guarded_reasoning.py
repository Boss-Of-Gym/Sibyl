from sibyl.platform.reasoning_guard import guarded_llm_call
from sibyl.pr_analysis.domain.models import PrRiskContext, RiskAssessment
from sibyl.pr_analysis.domain.ports import ReasoningPort


def _fallback_assessment() -> RiskAssessment:
    return RiskAssessment(
        score=0.0,
        rationale="",
        contributing_factors=[],
        llm_model="none",
        explanation_unavailable=True,
    )


class GuardedReasoningPort:
    def __init__(self, delegate: ReasoningPort, timeout_seconds: float = 15.0):
        self._delegate = delegate
        self._timeout_seconds = timeout_seconds

    async def assess_pr_risk(self, context: PrRiskContext) -> RiskAssessment:
        result, latency_ms = await guarded_llm_call(
            call=lambda: self._delegate.assess_pr_risk(context),
            fallback=_fallback_assessment,
            timeout_seconds=self._timeout_seconds,
        )
        return result.model_copy(update={"llm_latency_ms": latency_ms})
