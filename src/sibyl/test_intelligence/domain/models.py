from datetime import datetime
from typing import Literal

from pydantic import BaseModel

TestStatus = Literal["passed", "failed", "skipped"]


class TestResultItem(BaseModel):
    test_identifier: str
    status: TestStatus
    duration_ms: int = 0
    failure_message: str | None = None


class TestResultReport(BaseModel):
    repository: str
    commit_sha: str
    ci_run_id: int
    started_at: datetime
    completed_at: datetime
    tests: list[TestResultItem]


class CoverageFileReport(BaseModel):
    file_path: str
    lines_covered: int
    lines_total: int


class CoverageReport(BaseModel):
    repository: str
    commit_sha: str
    files: list[CoverageFileReport]
