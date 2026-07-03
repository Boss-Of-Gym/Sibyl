from typing import Protocol

from sibyl.pr_analysis.domain.models import PrRiskContext, RiskAssessment


class ReasoningPort(Protocol):
    async def assess_pr_risk(self, context: PrRiskContext) -> RiskAssessment: ...
