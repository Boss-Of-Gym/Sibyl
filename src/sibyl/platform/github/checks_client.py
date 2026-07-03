from typing import Literal

import httpx

CheckConclusion = Literal[
    "success", "neutral", "failure", "cancelled", "skipped", "timed_out", "action_required"
]


class GitHubChecksClient:
    def __init__(self, http_client: httpx.AsyncClient):
        self._http_client = http_client

    async def create_check_run(
        self,
        *,
        installation_token: str,
        repository: str,
        name: str,
        head_sha: str,
        conclusion: CheckConclusion,
        title: str,
        summary: str,
    ) -> None:
        response = await self._http_client.post(
            f"https://api.github.com/repos/{repository}/check-runs",
            headers={
                "Authorization": f"Bearer {installation_token}",
                "Accept": "application/vnd.github+json",
            },
            json={
                "name": name,
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": conclusion,
                "output": {"title": title, "summary": summary},
            },
        )
        response.raise_for_status()
