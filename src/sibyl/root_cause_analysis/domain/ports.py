from typing import Protocol

from sibyl.root_cause_analysis.domain.models import RootCauseContext, RootCauseExplanation


class ReasoningPort(Protocol):
    async def explain_root_cause(self, context: RootCauseContext) -> RootCauseExplanation: ...
