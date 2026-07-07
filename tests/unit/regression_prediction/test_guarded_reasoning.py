import asyncio

from pydantic import BaseModel

from sibyl.regression_prediction.adapters.guarded_reasoning import GuardedReasoningPort
from sibyl.regression_prediction.domain.models import (
    RegressionPrediction,
    RegressionPredictionContext,
)

CONTEXT = RegressionPredictionContext(
    repository="acme/widgets",
    pr_number=1,
    head_sha="a",
    changed_file_paths=[],
)


class _SucceedingDelegate:
    async def predict_regression(
        self, context: RegressionPredictionContext
    ) -> RegressionPrediction:
        return RegressionPrediction(
            regression_probability=0.5,
            rationale="ok",
            contributing_signals=[],
            llm_model="delegate",
        )


class _RaisingDelegate:
    async def predict_regression(
        self, context: RegressionPredictionContext
    ) -> RegressionPrediction:
        raise RuntimeError("provider exploded")


class _HangingDelegate:
    async def predict_regression(
        self, context: RegressionPredictionContext
    ) -> RegressionPrediction:
        await asyncio.sleep(10)
        raise AssertionError("should have timed out first")


class _RequiredField(BaseModel):
    value: str


class _SchemaInvalidDelegate:
    async def predict_regression(
        self, context: RegressionPredictionContext
    ) -> RegressionPrediction:
        _RequiredField.model_validate({})
        raise AssertionError("model_validate should have raised first")


async def test_successful_delegate_call_passes_through():
    port = GuardedReasoningPort(_SucceedingDelegate())

    result = await port.predict_regression(CONTEXT)

    assert result.llm_model == "delegate"
    assert result.explanation_unavailable is False
    assert result.llm_latency_ms >= 0


async def test_delegate_error_falls_back_without_raising():
    port = GuardedReasoningPort(_RaisingDelegate())

    result = await port.predict_regression(CONTEXT)

    assert result.explanation_unavailable is True
    assert result.llm_latency_ms >= 0


async def test_delegate_timeout_falls_back_without_raising():
    port = GuardedReasoningPort(_HangingDelegate(), timeout_seconds=0.05)

    result = await port.predict_regression(CONTEXT)

    assert result.explanation_unavailable is True
    assert result.llm_latency_ms >= 40


async def test_schema_validation_failure_falls_back_without_raising():
    port = GuardedReasoningPort(_SchemaInvalidDelegate())

    result = await port.predict_regression(CONTEXT)

    assert result.explanation_unavailable is True
    assert result.llm_latency_ms >= 0
