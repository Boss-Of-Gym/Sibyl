from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolChoiceToolParam, ToolParam
from pydantic import BaseModel

from sibyl.pr_analysis.domain.models import ContributingFactor, PrRiskContext, RiskAssessment


class _ToolOutput(BaseModel):
    score: float
    rationale: str
    contributing_factors: list[ContributingFactor]

ASSESS_PR_RISK_TOOL: ToolParam = {
    "name": "assess_pr_risk",
    "description": "Report a structured risk assessment for a pull request.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"},
            "contributing_factors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "factor": {"type": "string"},
                        "weight": {"type": "number"},
                    },
                    "required": ["factor", "weight"],
                },
            },
        },
        "required": ["score", "rationale", "contributing_factors"],
    },
}

ASSESS_PR_RISK_TOOL_CHOICE: ToolChoiceToolParam = {"type": "tool", "name": "assess_pr_risk"}


def _build_prompt(context: PrRiskContext) -> str:
    files = "\n".join(f"- {path}" for path in context.changed_file_paths)
    flaky = ", ".join(context.known_flaky_areas) or "none known"
    return (
        f"Repository: {context.repository}\n"
        f"PR #{context.pr_number} by {context.author_login}\n"
        f"Files changed: {context.files_changed} (+{context.additions}/-{context.deletions})\n"
        f"Changed files:\n{files}\n"
        f"Historically flaky areas touched: {flaky}\n"
        "Assess the engineering risk of merging this change."
    )


class AnthropicReasoningPort:
    def __init__(self, api_key: str, model: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def assess_pr_risk(self, context: PrRiskContext) -> RiskAssessment:
        messages: list[MessageParam] = [{"role": "user", "content": _build_prompt(context)}]
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            tools=[ASSESS_PR_RISK_TOOL],
            tool_choice=ASSESS_PR_RISK_TOOL_CHOICE,
            messages=messages,
        )

        tool_use = next(block for block in response.content if block.type == "tool_use")
        output = _ToolOutput.model_validate(tool_use.input)
        return RiskAssessment(
            score=output.score,
            rationale=output.rationale,
            contributing_factors=output.contributing_factors,
            llm_model=self._model,
            llm_tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )
