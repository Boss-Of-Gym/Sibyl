from typing import Protocol

from sibyl.regression_prediction.domain.models import (
    RegressionPrediction,
    RegressionPredictionContext,
)


class ReasoningPort(Protocol):
    async def predict_regression(
        self, context: RegressionPredictionContext
    ) -> RegressionPrediction: ...
