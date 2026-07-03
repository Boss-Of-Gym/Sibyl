from sibyl.pr_analysis.domain.models import ContributingFactor, PrRiskContext, RiskAssessment


class FakeReasoningPort:
    def __init__(self, canned_response: RiskAssessment | None = None):
        self._canned_response = canned_response

    async def assess_pr_risk(self, context: PrRiskContext) -> RiskAssessment:
        if self._canned_response is not None:
            return self._canned_response

        change_volume = context.additions + context.deletions
        score = min(1.0, 0.1 * context.files_changed + 0.001 * change_volume)
        return RiskAssessment(
            score=score,
            rationale=f"Fake assessment: {context.files_changed} files changed.",
            contributing_factors=[ContributingFactor(factor="files_changed", weight=score)],
            llm_model="fake-reasoning-port",
        )
