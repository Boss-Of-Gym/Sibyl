import hashlib
import hmac

from sibyl.ingestion.adapters.signature import verify_github_signature


def test_valid_signature_is_accepted():
    secret = "top-secret"
    body = b'{"hello":"world"}'
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    header = f"sha256={digest}"

    assert verify_github_signature(body, header, secret) is True


def test_tampered_body_is_rejected():
    secret = "top-secret"
    digest = hmac.new(secret.encode(), b'{"hello":"world"}', hashlib.sha256).hexdigest()
    header = f"sha256={digest}"

    assert verify_github_signature(b'{"hello":"tampered"}', header, secret) is False


def test_missing_header_is_rejected():
    assert verify_github_signature(b"body", None, "secret") is False


def test_wrong_prefix_is_rejected():
    assert verify_github_signature(b"body", "sha1=deadbeef", "secret") is False
