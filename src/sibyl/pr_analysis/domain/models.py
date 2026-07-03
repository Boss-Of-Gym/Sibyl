from datetime import datetime

from pydantic import BaseModel, Field


class PrRiskContext(BaseModel):
    repository: str
    pr_number: int
    head_sha: str
    base_sha: str
    author_login: str
    files_changed: int
    additions: int
    deletions: int
    changed_file_paths: list[str]
    known_flaky_areas: list[str] = Field(default_factory=list)


class ContributingFactor(BaseModel):
    factor: str
    weight: float


class RiskAssessment(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    rationale: str
    contributing_factors: list[ContributingFactor]
    llm_model: str
    explanation_unavailable: bool = False


class PrRiskAssessmentRecord(BaseModel):
    pr_number: int
    head_sha: str
    score: float
    rationale: str
    contributing_factors: list[ContributingFactor]
    llm_model: str
    computed_at: datetime
