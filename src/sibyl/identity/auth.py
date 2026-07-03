from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from sibyl.platform.config import Settings, get_request_settings
from sibyl.platform.errors import ProblemException

ALGORITHM = "HS256"

_bearer_scheme = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    sub: str
    scopes: list[str]
    exp: datetime
    installation_id: str | None = None


def create_access_token(
    subject: str,
    scopes: list[str],
    signing_key: str,
    expires_delta: timedelta,
    installation_id: str | None = None,
) -> str:
    expire = datetime.now(UTC) + expires_delta
    payload = {
        "sub": subject,
        "scopes": scopes,
        "exp": expire,
        "installation_id": installation_id,
    }
    return jwt.encode(payload, signing_key, algorithm=ALGORITHM)


def decode_access_token(token: str, signing_key: str) -> TokenPayload:
    try:
        raw = jwt.decode(token, signing_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise ProblemException(
            status_code=401,
            title="Token expired",
            code="SIBYL_TOKEN_INVALID",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise ProblemException(
            status_code=401,
            title="Invalid token",
            code="SIBYL_TOKEN_INVALID",
        ) from exc
    return TokenPayload.model_validate(raw)


def require_scope(
    required_scope: str,
) -> Callable[[HTTPAuthorizationCredentials | None, Settings], TokenPayload]:
    def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
        settings: Settings = Depends(get_request_settings),
    ) -> TokenPayload:
        if credentials is None:
            raise ProblemException(
                status_code=401,
                title="Missing bearer token",
                code="SIBYL_TOKEN_INVALID",
            )
        token = decode_access_token(credentials.credentials, settings.jwt_signing_key)
        if required_scope not in token.scopes:
            raise ProblemException(
                status_code=403,
                title="Insufficient scope",
                code="SIBYL_SCOPE_INSUFFICIENT",
                detail=f"Requires scope '{required_scope}'",
            )
        return token

    return dependency
