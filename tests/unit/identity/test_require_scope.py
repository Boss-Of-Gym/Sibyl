from datetime import timedelta

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from sibyl.identity.auth import create_access_token, require_scope
from sibyl.platform.config import Settings
from sibyl.platform.errors import ProblemException

SETTINGS = Settings(jwt_signing_key="test-signing-key")


def _credentials_for(scopes: list[str]) -> HTTPAuthorizationCredentials:
    token = create_access_token(
        subject="user-1", scopes=scopes, signing_key=SETTINGS.jwt_signing_key,
        expires_delta=timedelta(minutes=5),
    )
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_missing_credentials_raises_401():
    dependency = require_scope("read:pr-analysis")

    with pytest.raises(ProblemException) as exc_info:
        dependency(None, SETTINGS)

    assert exc_info.value.status_code == 401
    assert exc_info.value.problem["code"] == "SIBYL_TOKEN_INVALID"


def test_insufficient_scope_raises_403():
    dependency = require_scope("admin:installations")
    credentials = _credentials_for(["read:pr-analysis"])

    with pytest.raises(ProblemException) as exc_info:
        dependency(credentials, SETTINGS)

    assert exc_info.value.status_code == 403
    assert exc_info.value.problem["code"] == "SIBYL_SCOPE_INSUFFICIENT"


def test_sufficient_scope_returns_token_payload():
    dependency = require_scope("read:pr-analysis")
    credentials = _credentials_for(["read:pr-analysis", "read:root-cause"])

    payload = dependency(credentials, SETTINGS)

    assert payload.sub == "user-1"
