from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolChoiceToolParam, ToolParam
from pydantic import BaseModel

from sibyl.regression_prediction.domain.models import (
    ContributingSignal,
    RegressionPrediction,
    RegressionPredictionContext,
)


class _ToolOutput(BaseModel):
    regression_probability: float
    rationale: str
    contributing_signals: list[ContributingSignal]


PREDICT_REGRESSION_TOOL: ToolParam = {
    "name": "predict_regression",
    "description": "Report a structured regression-risk prediction for a pull request.",
    "input_schema": {
        "type": "object",
        "properties": {
            "regression_probability": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"},
            "contributing_signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "signal": {"type": "string"},
                        "weight": {"type": "number"},
                    },
                    "required": ["signal", "weight"],
                },
            },
        },
        "required": ["regression_probability", "rationale", "contributing_signals"],
    },
}

PREDICT_REGRESSION_TOOL_CHOICE: ToolChoiceToolParam = {"type": "tool", "name": "predict_regression"}


def _build_prompt(context: RegressionPredictionContext) -> str:
    files = "\n".join(f"- {path}" for path in context.changed_file_paths)
    history = (
        "\n".join(
            f"- {signal.file_path}: {signal.hypothesis_text} "
            f"(confidence {signal.confidence:.2f}, {signal.occurred_at.date()})"
            for signal in context.historical_regressions
        )
        or "none known"
    )
    return (
        f"Repository: {context.repository}\n"
        f"PR #{context.pr_number} (head {context.head_sha})\n"
        f"Changed files:\n{files}\n"
        f"Historical regressions previously tied to these files:\n{history}\n"
        "Predict the likelihood this PR introduces a regression, based on how often "
        "these files have been implicated in past failures."
    )


class AnthropicReasoningPort:
    def __init__(self, api_key: str, model: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def predict_regression(
        self, context: RegressionPredictionContext
    ) -> RegressionPrediction:
        messages: list[MessageParam] = [{"role": "user", "content": _build_prompt(context)}]
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            tools=[PREDICT_REGRESSION_TOOL],
            tool_choice=PREDICT_REGRESSION_TOOL_CHOICE,
            messages=messages,
        )

        tool_use = next(block for block in response.content if block.type == "tool_use")
        output = _ToolOutput.model_validate(tool_use.input)
        return RegressionPrediction(
            regression_probability=output.regression_probability,
            rationale=output.rationale,
            contributing_signals=output.contributing_signals,
            llm_model=self._model,
            llm_tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )
