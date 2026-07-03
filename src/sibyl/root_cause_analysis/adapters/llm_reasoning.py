from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolChoiceToolParam, ToolParam
from pydantic import BaseModel

from sibyl.root_cause_analysis.domain.models import RootCauseContext, RootCauseExplanation


class _ToolOutput(BaseModel):
    hypothesis_text: str
    confidence: float
    suspected_commit_sha: str | None = None
    suspected_file_path: str | None = None


EXPLAIN_ROOT_CAUSE_TOOL: ToolParam = {
    "name": "explain_root_cause",
    "description": "Report a structured root-cause hypothesis for a failing test.",
    "input_schema": {
        "type": "object",
        "properties": {
            "hypothesis_text": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "suspected_commit_sha": {"type": "string"},
            "suspected_file_path": {"type": "string"},
        },
        "required": ["hypothesis_text", "confidence"],
    },
}

EXPLAIN_ROOT_CAUSE_TOOL_CHOICE: ToolChoiceToolParam = {"type": "tool", "name": "explain_root_cause"}


def _build_prompt(context: RootCauseContext) -> str:
    affected = "\n".join(f"- {test_id}" for test_id in context.affected_tests) or "none known"
    risk_score = "unknown" if context.risk_score is None else f"{context.risk_score:.2f}"
    flakiness = "unknown" if context.flakiness_score is None else f"{context.flakiness_score:.2f}"
    return (
        f"Repository: {context.repository}\n"
        f"Failing test: {context.test_identifier}\n"
        f"Failing commit: {context.commit_sha}\n"
        f"PR #{context.pr_number} (head {context.head_sha})\n"
        f"PR risk score: {risk_score}\n"
        f"Tests this PR's changes are known to affect:\n{affected}\n"
        f"Historical flakiness score for the failing test: {flakiness}\n"
        "Hypothesize the most likely root cause of this test failure."
    )


class AnthropicReasoningPort:
    def __init__(self, api_key: str, model: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def explain_root_cause(self, context: RootCauseContext) -> RootCauseExplanation:
        messages: list[MessageParam] = [{"role": "user", "content": _build_prompt(context)}]
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            tools=[EXPLAIN_ROOT_CAUSE_TOOL],
            tool_choice=EXPLAIN_ROOT_CAUSE_TOOL_CHOICE,
            messages=messages,
        )

        tool_use = next(block for block in response.content if block.type == "tool_use")
        output = _ToolOutput.model_validate(tool_use.input)
        return RootCauseExplanation(
            hypothesis_text=output.hypothesis_text,
            confidence=output.confidence,
            suspected_commit_sha=output.suspected_commit_sha,
            suspected_file_path=output.suspected_file_path,
            llm_model=self._model,
            llm_tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )
