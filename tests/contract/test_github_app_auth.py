import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from sibyl.platform.github.app_auth import GitHubAppAuthenticator

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_KEY_PEM = _PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")
PUBLIC_KEY = _PRIVATE_KEY.public_key()


def _make_transport(call_counter: list[int]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        call_counter.append(1)
        auth_header = request.headers["Authorization"]
        assert auth_header.startswith("Bearer ")
        token = auth_header.removeprefix("Bearer ")
        decoded = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"], issuer="app-123")
        assert decoded["iss"] == "app-123"
        assert "/app/installations/999/access_tokens" in str(request.url)
        return httpx.Response(
            201, json={"token": "ghs_fake_token", "expires_at": "2099-01-01T00:00:00Z"}
        )

    return httpx.MockTransport(handler)


async def test_fetches_and_returns_installation_token(redis_client):
    call_counter: list[int] = []
    http_client = httpx.AsyncClient(transport=_make_transport(call_counter))
    authenticator = GitHubAppAuthenticator("app-123", PRIVATE_KEY_PEM, redis_client, http_client)

    token = await authenticator.get_installation_token(999)

    assert token == "ghs_fake_token"
    assert len(call_counter) == 1


async def test_second_call_uses_cache_not_a_second_http_request(redis_client):
    call_counter: list[int] = []
    http_client = httpx.AsyncClient(transport=_make_transport(call_counter))
    authenticator = GitHubAppAuthenticator("app-123", PRIVATE_KEY_PEM, redis_client, http_client)

    first = await authenticator.get_installation_token(999)
    second = await authenticator.get_installation_token(999)

    assert first == second == "ghs_fake_token"
    assert len(call_counter) == 1
