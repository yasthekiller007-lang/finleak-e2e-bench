import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth.oidc import InvalidIdentityToken
from app.core.config import Settings
from app.main import create_app
from tests.identity_fixtures import IdentityFixture


@pytest.fixture(scope="module")
def identity():
    return IdentityFixture()


def test_real_signature_and_stable_subject(identity):
    result = identity.verifier.verify(identity.token())
    assert result.subject == "user-a"
    assert result.email == "shared@example.test"


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": int(time.time()) - 60},
        {"iss": "https://attacker.example"},
        {"aud": "frontend-client"},
        {"iat": int(time.time()) + 3600},
        {"nbf": int(time.time()) + 3600},
        {"sub": ""},
        {"sub": "non-ascii-☠"},
        {"token_use": "id"},
    ],
)
def test_rejects_invalid_claims(identity, changes):
    with pytest.raises(InvalidIdentityToken):
        identity.verifier.verify(identity.token(changes=changes))


@pytest.mark.parametrize("claim", ["iss", "aud", "sub", "exp", "iat"])
def test_required_claims(identity, claim):
    claims = {
        "iss": identity.verifier.issuer,
        "aud": identity.verifier.audience,
        "sub": "a",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
    }
    del claims[claim]
    token = jwt.encode(claims, identity.key, algorithm="RS256", headers={"kid": "fixture-key"})
    with pytest.raises(InvalidIdentityToken):
        identity.verifier.verify(token)


def test_wrong_signature(identity):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(InvalidIdentityToken):
        identity.verifier.verify(identity.token(key=other))


@pytest.mark.parametrize(
    "token",
    ["not-a-jwt", "a" * 8193, jwt.encode({"sub": "a"}, None, algorithm="none")],
)
def test_malformed_or_unsigned_token(identity, token):
    with pytest.raises(InvalidIdentityToken):
        identity.verifier.verify(token)


def test_unverified_email_does_not_become_identity():
    fixture = IdentityFixture()
    assert fixture.verifier.verify(fixture.token(changes={"email_verified": False})).email is None


@pytest.mark.parametrize("environment", ["development", "production"])
def test_test_verifier_cannot_be_injected_outside_test_mode(identity, environment):
    with pytest.raises(ValueError, match="only in test"):
        create_app(
            Settings(_env_file=None, environment=environment), token_verifier=identity.verifier
        )


def test_no_header_based_authentication_bypass():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get(
            "/api/v1/me", headers={"X-Test-User": "owner", "X-Organization-ID": "anything"}
        )
        assert response.status_code == 401


def test_unconfigured_provider_fails_closed():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert (
            client.get("/api/v1/me", headers={"Authorization": "Bearer something"}).status_code
            == 503
        )


def test_production_rejects_loopback_http_identity_provider():
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(_env_file=None, environment="production", oidc_issuer="http://localhost:9000")


def test_jku_header_never_overrides_configured_key_source(identity):
    token = identity.token(headers={"kid": "fixture-key", "jku": "http://attacker.test/keys"})
    assert identity.verifier.verify(token).subject == "user-a"
    with pytest.raises(InvalidIdentityToken):
        identity.verifier.verify(identity.token(headers={"kid": "unknown-key"}))


@pytest.mark.parametrize(
    "metadata",
    [
        {"issuer": "https://wrong.test", "jwks_uri": "https://identity.example.test/keys"},
        {"issuer": "https://identity.example.test", "jwks_uri": "http://localhost:9000/keys"},
        {"issuer": "https://identity.example.test", "jwks_uri": "file:///etc/passwd"},
        {},
    ],
)
def test_discovery_rejects_mismatched_issuer_and_unsafe_keys(monkeypatch, metadata):
    from app.auth.oidc import DiscoveryJWKClient

    monkeypatch.setattr("app.auth.oidc.provider_json", lambda *args: metadata)
    with pytest.raises(jwt.PyJWKClientConnectionError):
        DiscoveryJWKClient("https://identity.example.test", production=True).fetch_data()


def test_standard_discovery_selects_declared_jwks_without_provider_path_assumptions(monkeypatch):
    from app.auth.oidc import BoundedJWKClient, DiscoveryJWKClient, build_token_verifier

    issuer = "https://identity.example.test"
    monkeypatch.setattr(
        "app.auth.oidc.provider_json",
        lambda *args: {"issuer": issuer, "jwks_uri": issuer + "/custom/provider/keys"},
    )
    monkeypatch.setattr(BoundedJWKClient, "fetch_data", lambda self: {"uri": self.uri})
    settings = Settings(_env_file=None, oidc_issuer=issuer, oidc_audience="api")
    verifier = build_token_verifier(settings)
    assert isinstance(verifier.jwks, DiscoveryJWKClient)
    assert verifier.jwks.fetch_data() == {"uri": issuer + "/custom/provider/keys"}


def test_signing_algorithms_are_configurable_but_never_accept_symmetric_keys():
    import json

    from cryptography.hazmat.primitives.asymmetric import ec

    from app.auth.oidc import OIDCTokenVerifier
    from tests.identity_fixtures import AUDIENCE, ISSUER, StaticJWKS

    key = ec.generate_private_key(ec.SECP256R1())
    public_jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    public_jwk.update(kid="ec-fixture", alg="ES256", use="sig")
    verifier = OIDCTokenVerifier(ISSUER, AUDIENCE, StaticJWKS(public_jwk), ("ES256",))
    now = int(time.time())
    token = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": "ec-user", "iat": now, "exp": now + 300},
        key,
        algorithm="ES256",
        headers={"kid": "ec-fixture"},
    )
    assert verifier.verify(token).subject == "ec-user"
    with pytest.raises(ValueError):
        Settings(_env_file=None, oidc_signing_algorithms=["HS256"])
