from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TestStatus = Literal["passed", "failed", "skipped"]


class TestResultItem(BaseModel):
    test_identifier: str
    status: TestStatus


class CiRunCompletedReport(BaseModel):
    repository: str
    commit_sha: str
    ci_run_id: int
    tests: list[TestResultItem]


class RootCauseContext(BaseModel):
    repository: str
    test_identifier: str
    commit_sha: str
    pr_number: int
    head_sha: str
    risk_score: float | None
    affected_tests: list[str]
    flakiness_score: float | None


class RootCauseExplanation(BaseModel):
    hypothesis_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    suspected_commit_sha: str | None = None
    suspected_file_path: str | None = None
    llm_model: str
    llm_tokens_used: int = 0
    llm_latency_ms: int = 0
    explanation_unavailable: bool = False


class RootCauseHypothesisRecord(BaseModel):
    failure_event_id: str
    hypothesis_text: str
    confidence: float
    suspected_commit_sha: str | None
    suspected_file_path: str | None
    llm_model: str
    computed_at: datetime
