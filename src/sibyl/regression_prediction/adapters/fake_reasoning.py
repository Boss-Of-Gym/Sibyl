from sibyl.regression_prediction.domain.models import (
    ContributingSignal,
    RegressionPrediction,
    RegressionPredictionContext,
)


class FakeReasoningPort:
    def __init__(self, canned_response: RegressionPrediction | None = None):
        self._canned_response = canned_response

    async def predict_regression(
        self, context: RegressionPredictionContext
    ) -> RegressionPrediction:
        if self._canned_response is not None:
            return self._canned_response

        match_count = len(context.historical_regressions)
        probability = min(1.0, 0.2 * match_count)
        contributing_signals = (
            [ContributingSignal(signal="historical_regression_count", weight=probability)]
            if match_count
            else []
        )
        return RegressionPrediction(
            regression_probability=probability,
            rationale=(
                f"Fake prediction: {match_count} historical regression(s) "
                "tied to these changed files."
            ),
            contributing_signals=contributing_signals,
            llm_model="fake-reasoning-port",
        )
