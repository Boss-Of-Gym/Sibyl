from datetime import timedelta

import pytest

from sibyl.identity.auth import create_access_token, decode_access_token
from sibyl.platform.errors import ProblemException

SIGNING_KEY = "test-signing-key"


def test_round_trip_preserves_subject_and_scopes():
    token = create_access_token(
        subject="user-123",
        scopes=["read:pr-analysis"],
        signing_key=SIGNING_KEY,
        expires_delta=timedelta(minutes=5),
    )

    payload = decode_access_token(token, SIGNING_KEY)

    assert payload.sub == "user-123"
    assert payload.scopes == ["read:pr-analysis"]


def test_expired_token_is_rejected():
    token = create_access_token(
        subject="user-123",
        scopes=[],
        signing_key=SIGNING_KEY,
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(ProblemException) as exc_info:
        decode_access_token(token, SIGNING_KEY)

    assert exc_info.value.status_code == 401
    assert exc_info.value.problem["code"] == "SIBYL_TOKEN_INVALID"


def test_token_signed_with_wrong_key_is_rejected():
    token = create_access_token(
        subject="user-123",
        scopes=[],
        signing_key="a-different-key",
        expires_delta=timedelta(minutes=5),
    )

    with pytest.raises(ProblemException) as exc_info:
        decode_access_token(token, SIGNING_KEY)

    assert exc_info.value.status_code == 401
