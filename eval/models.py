from pydantic import BaseModel

from sibyl.pr_analysis.domain.models import PrRiskContext
from sibyl.root_cause_analysis.domain.models import RootCauseContext


class PrAnalysisExpectation(BaseModel):
    score_min: float
    score_max: float


class PrAnalysisGoldenCase(BaseModel):
    id: str
    notes: str
    context: PrRiskContext
    expected: PrAnalysisExpectation


class RootCauseExpectation(BaseModel):
    confidence_min: float
    suspected_file_path: str | None = None


class RootCauseGoldenCase(BaseModel):
    id: str
    notes: str
    context: RootCauseContext
    expected: RootCauseExpectation
