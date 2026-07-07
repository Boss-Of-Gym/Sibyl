from sibyl.platform.observability import get_meter
from sibyl.platform.reasoning_guard import guarded_llm_call
from sibyl.root_cause_analysis.domain.models import RootCauseContext, RootCauseExplanation
from sibyl.root_cause_analysis.domain.ports import ReasoningPort

_tokens_used = get_meter(__name__).create_histogram("llm.tokens_used")


def _fallback_explanation() -> RootCauseExplanation:
    return RootCauseExplanation(
        hypothesis_text="",
        confidence=0.0,
        llm_model="none",
        explanation_unavailable=True,
    )


class GuardedReasoningPort:
    def __init__(self, delegate: ReasoningPort, timeout_seconds: float = 15.0):
        self._delegate = delegate
        self._timeout_seconds = timeout_seconds

    async def explain_root_cause(self, context: RootCauseContext) -> RootCauseExplanation:
        result, latency_ms = await guarded_llm_call(
            call=lambda: self._delegate.explain_root_cause(context),
            fallback=_fallback_explanation,
            timeout_seconds=self._timeout_seconds,
        )
        explanation = result.model_copy(update={"llm_latency_ms": latency_ms})
        if not explanation.explanation_unavailable:
            _tokens_used.record(explanation.llm_tokens_used)
        return explanation
