from sibyl.platform.observability import get_meter
from sibyl.platform.reasoning_guard import guarded_llm_call
from sibyl.regression_prediction.domain.models import (
    RegressionPrediction,
    RegressionPredictionContext,
)
from sibyl.regression_prediction.domain.ports import ReasoningPort

_tokens_used = get_meter(__name__).create_histogram("llm.tokens_used")


def _fallback_prediction() -> RegressionPrediction:
    return RegressionPrediction(
        regression_probability=0.0,
        rationale="",
        contributing_signals=[],
        llm_model="none",
        explanation_unavailable=True,
    )


class GuardedReasoningPort:
    def __init__(self, delegate: ReasoningPort, timeout_seconds: float = 15.0):
        self._delegate = delegate
        self._timeout_seconds = timeout_seconds

    async def predict_regression(
        self, context: RegressionPredictionContext
    ) -> RegressionPrediction:
        result, latency_ms = await guarded_llm_call(
            call=lambda: self._delegate.predict_regression(context),
            fallback=_fallback_prediction,
            timeout_seconds=self._timeout_seconds,
        )
        prediction = result.model_copy(update={"llm_latency_ms": latency_ms})
        if not prediction.explanation_unavailable:
            _tokens_used.record(prediction.llm_tokens_used)
        return prediction
