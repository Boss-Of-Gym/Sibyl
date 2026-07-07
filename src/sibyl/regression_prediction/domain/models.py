from datetime import datetime

from pydantic import BaseModel, Field


class HistoricalRegressionSignal(BaseModel):
    file_path: str
    hypothesis_text: str
    confidence: float
    occurred_at: datetime


class RegressionPredictionContext(BaseModel):
    repository: str
    pr_number: int
    head_sha: str
    changed_file_paths: list[str]
    historical_regressions: list[HistoricalRegressionSignal] = Field(default_factory=list)


class ContributingSignal(BaseModel):
    signal: str
    weight: float


class RegressionPrediction(BaseModel):
    regression_probability: float = Field(ge=0.0, le=1.0)
    rationale: str
    contributing_signals: list[ContributingSignal]
    llm_model: str
    llm_tokens_used: int = 0
    llm_latency_ms: int = 0
    explanation_unavailable: bool = False


class RegressionPredictionRecord(BaseModel):
    pr_number: int
    head_sha: str
    regression_probability: float
    rationale: str
    contributing_signals: list[ContributingSignal]
    llm_model: str
    computed_at: datetime
