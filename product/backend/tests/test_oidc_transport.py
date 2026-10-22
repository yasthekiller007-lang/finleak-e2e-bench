"""Real HTTP discovery/JWKS and cryptographic verification, synthetic issuer only."""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.oidc import (
    BoundedJWKClient,
    DiscoveryJWKClient,
    IdentityProviderUnavailable,
    InvalidIdentityToken,
    OIDCTokenVerifier,
    provider_json,
)


def signing_key(kid):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    return key, public | {"kid": kid, "alg": "RS256", "use": "sig"}


@pytest.fixture
def issuer():
    state = SimpleNamespace(mode="healthy", counts={}, key=None, jwk=None)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # no request/profile/body diagnostics from the synthetic issuer

        def do_GET(self):
            state.counts[self.path] = state.counts.get(self.path, 0) + 1
            status = 200
            if state.mode == "outage":
                status, payload = 503, b"private provider failure sentinel"
            elif state.mode == "redirect":
                self.send_response(302)
                self.send_header("Location", state.url + "/forbidden")
                self.end_headers()
                return
            elif state.mode == "oversized":
                payload = b'{"private":"' + b"x" * (513 * 1024) + b'"}'
            elif state.mode == "invalid":
                payload = b"private provider secret: invalid JSON"
            elif self.path == "/.well-known/openid-configuration":
                payload = json.dumps(
                    {"issuer": state.url, "jwks_uri": state.url + "/custom/keys"}
                ).encode()
            elif self.path == "/custom/keys":
                values = [state.jwk, state.jwk] if state.mode == "duplicate" else [state.jwk]
                payload = json.dumps({"keys": values}).encode()
            else:
                status, payload = 404, b"not found"
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass  # client correctly stopped after its actual-byte limit

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.url = f"http://127.0.0.1:{server.server_port}"
    state.key, state.jwk = signing_key("initial-key")
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def token(issuer, **changes):
    now = int(time.time())
    claims = {
        "iss": issuer.url,
        "aud": "synthetic-api",
        "sub": "verified-subject",
        "iat": now,
        "exp": now + 300,
    } | changes
    return jwt.encode(claims, issuer.key, algorithm="RS256", headers={"kid": issuer.jwk["kid"]})


def verifier(issuer, discovery=True):
    client = (
        DiscoveryJWKClient(issuer.url, False)
        if discovery
        else BoundedJWKClient(issuer.url + "/custom/keys", False)
    )
    return OIDCTokenVerifier(issuer.url, "synthetic-api", client)


@pytest.mark.parametrize("discovery", [True, False])
def test_real_http_keys_verify_tokens_without_identity_injection(issuer, discovery):
    verification = verifier(issuer, discovery)
    assert verification.verify(token(issuer)).subject == "verified-subject"
    assert issuer.counts["/custom/keys"] == 1
    assert issuer.counts.get("/.well-known/openid-configuration", 0) == int(discovery)
    assert verification.jwks.jwk_set_cache.lifespan == 300
    for invalid in (
        token(issuer, aud="other-client"),
        token(issuer, exp=int(time.time()) - 1),
        token(issuer, token_use="id"),
    ):
        with pytest.raises(InvalidIdentityToken):
            verification.verify(invalid)


def test_rotation_refreshes_after_bounded_unknown_key_cooldown(issuer, monkeypatch):
    verification = verifier(issuer)
    old = token(issuer)
    assert verification.verify(old).subject == "verified-subject"
    issuer.key, issuer.jwk = signing_key("rotated-key")
    new = token(issuer)
    with pytest.raises(InvalidIdentityToken):
        verification.verify(new)
    assert issuer.counts["/custom/keys"] == 1
    actual = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: actual() + 31)
    assert verification.verify(new).subject == "verified-subject"
    assert issuer.counts["/custom/keys"] == 2
    with pytest.raises(InvalidIdentityToken):
        verification.verify(old)


def test_provider_outage_preserves_bounded_cache_and_expiry_fails_closed(issuer, monkeypatch):
    verification = verifier(issuer)
    valid = token(issuer)
    verification.verify(valid)
    issuer.mode = "outage"
    assert verification.verify(valid).subject == "verified-subject"
    assert issuer.counts["/custom/keys"] == 1
    actual = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: actual() + 301)
    with pytest.raises(IdentityProviderUnavailable) as error:
        verification.verify(valid)
    assert "private" not in str(error.value) and issuer.counts["/custom/keys"] == 2


@pytest.mark.parametrize("mode", ["outage", "redirect", "oversized", "invalid", "duplicate"])
@pytest.mark.parametrize("discovery", [True, False])
def test_issuer_failures_are_bounded_safe_and_never_fallback(issuer, mode, discovery):
    issuer.mode = mode
    with pytest.raises(IdentityProviderUnavailable) as error:
        verifier(issuer, discovery).verify(token(issuer))
    assert not str(error.value)
    assert issuer.counts.get("/forbidden", 0) == 0


def test_repeated_unknown_kid_does_not_multiply_provider_requests(issuer):
    verification = verifier(issuer)
    valid = token(issuer)
    verification.verify(valid)
    claims = jwt.decode(valid, options={"verify_signature": False})
    unknown = jwt.encode(claims, issuer.key, algorithm="RS256", headers={"kid": "unknown"})
    for _ in range(10):
        with pytest.raises(InvalidIdentityToken):
            verification.verify(unknown)
    assert issuer.counts["/custom/keys"] == 1


def test_production_cannot_use_loopback_plain_http_issuer(issuer):
    with pytest.raises(jwt.PyJWKClientConnectionError, match="endpoint unavailable"):
        provider_json(issuer.url + "/custom/keys", True)
    assert issuer.counts == {}


@pytest.mark.parametrize(
    "payload",
    [
        {"keys": []},
        {"keys": [{"kid": "a"}] * 101},
        {"keys": [{"kid": 1}]},
        {"keys": "private"},
        {"keys": [{"kid": "a", "kty": {"private": "invalid"}}]},
    ],
)
def test_key_count_and_shape_fail_before_cache_authority(monkeypatch, payload):
    monkeypatch.setattr("app.auth.oidc.provider_json", lambda *args: payload)
    client = BoundedJWKClient("https://identity.example.test/keys", True)
    with pytest.raises(jwt.PyJWKClientConnectionError, match="key set unavailable"):
        client.fetch_data()
    assert client.jwk_set_cache.get() is None
