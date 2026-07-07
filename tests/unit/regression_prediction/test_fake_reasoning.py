from datetime import UTC, datetime

from sibyl.regression_prediction.adapters.fake_reasoning import FakeReasoningPort
from sibyl.regression_prediction.domain.models import (
    HistoricalRegressionSignal,
    RegressionPrediction,
    RegressionPredictionContext,
)

CONTEXT = RegressionPredictionContext(
    repository="acme/widgets",
    pr_number=7,
    head_sha="sha-1",
    changed_file_paths=["src/payments/processor.py"],
)


async def test_higher_probability_with_more_historical_regressions():
    no_history = await FakeReasoningPort().predict_regression(CONTEXT)
    with_history = await FakeReasoningPort().predict_regression(
        CONTEXT.model_copy(
            update={
                "historical_regressions": [
                    HistoricalRegressionSignal(
                        file_path="src/payments/processor.py",
                        hypothesis_text="broke refunds",
                        confidence=0.7,
                        occurred_at=datetime.now(UTC),
                    )
                ]
            }
        )
    )

    assert with_history.regression_probability > no_history.regression_probability


async def test_no_history_means_zero_probability_and_no_contributing_signals():
    result = await FakeReasoningPort().predict_regression(CONTEXT)

    assert result.regression_probability == 0.0
    assert result.contributing_signals == []


async def test_canned_response_overrides_computed_result():
    canned = RegressionPrediction(
        regression_probability=0.99,
        rationale="canned",
        contributing_signals=[],
        llm_model="canned-model",
    )

    result = await FakeReasoningPort(canned_response=canned).predict_regression(CONTEXT)

    assert result is canned
