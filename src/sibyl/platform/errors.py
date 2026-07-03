from typing import Any

from fastapi import HTTPException


class ProblemException(HTTPException):
    def __init__(self, status_code: int, title: str, code: str, detail: str | None = None):
        super().__init__(status_code=status_code, detail=detail or title)
        self.problem: dict[str, Any] = {
            "type": f"https://sibyl.dev/problems/{code.lower()}",
            "title": title,
            "status": status_code,
            "detail": detail or title,
            "code": code,
        }
