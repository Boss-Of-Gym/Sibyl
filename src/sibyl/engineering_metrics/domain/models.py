from datetime import datetime
from typing import Literal

from pydantic import BaseModel

TestStatus = Literal["passed", "failed", "skipped"]


class TestResultItem(BaseModel):
    test_identifier: str
    status: TestStatus


class CiRunCompletedReport(BaseModel):
    repository: str
    commit_sha: str
    ci_run_id: int
    started_at: datetime
    completed_at: datetime
    tests: list[TestResultItem]
