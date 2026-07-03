from datetime import UTC, datetime, timedelta

import httpx
import jwt
from redis.asyncio import Redis

TOKEN_CACHE_TTL_SECONDS = 55 * 60
APP_JWT_TTL_SECONDS = 9 * 60
CLOCK_DRIFT_BUFFER_SECONDS = 60


def _build_app_jwt(app_id: str, private_key: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "iat": int((now - timedelta(seconds=CLOCK_DRIFT_BUFFER_SECONDS)).timestamp()),
        "exp": int((now + timedelta(seconds=APP_JWT_TTL_SECONDS)).timestamp()),
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


class GitHubAppAuthenticator:
    def __init__(
        self,
        app_id: str,
        private_key: str,
        redis: Redis,
        http_client: httpx.AsyncClient,
    ):
        self._app_id = app_id
        self._private_key = private_key
        self._redis = redis
        self._http_client = http_client

    async def get_installation_token(self, github_installation_id: int) -> str:
        cache_key = f"gh:token:{github_installation_id}"
        cached = await self._redis.get(cache_key)
        if cached is not None:
            return str(cached.decode("utf-8") if isinstance(cached, bytes) else cached)

        app_jwt = _build_app_jwt(self._app_id, self._private_key)
        response = await self._http_client.post(
            f"https://api.github.com/app/installations/{github_installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        token: str = response.json()["token"]

        await self._redis.set(cache_key, token, ex=TOKEN_CACHE_TTL_SECONDS)
        return token
