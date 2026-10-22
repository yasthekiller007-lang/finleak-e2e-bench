"""Actual loopback HTTP and RSA/JWKS tests; no browser login or database claim."""

import hashlib
import json
import re
import socket
import time
from threading import Thread
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx2 as httpx
import jwt
import oidc_provider as provider
import pytest
import uvicorn
from app.auth.oidc import DiscoveryJWKClient, InvalidIdentityToken, OIDCTokenVerifier


@pytest.fixture
def issuer(monkeypatch):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    monkeypatch.setattr(provider, "ISSUER", f"http://127.0.0.1:{port}")
    config = {
        "synthetic": True,
        "client_secret": "client-" + "x" * 40,
        "accounts": {
            role: {
                "password": role + "-" + "x" * 40,
                "subject": "synthetic-" + role,
                "name": "Synthetic " + role,
            }
            for role in ("owner", "analyst")
        },
    }
    app = provider.create_provider(config)
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
    thread = Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 3
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    with httpx.Client(
        base_url=provider.ISSUER, trust_env=False, timeout=3, follow_redirects=False
    ) as client:
        yield client, config
    server.should_exit = True
    thread.join(timeout=3)
    assert not thread.is_alive()


def authorization(client, **changes):
    verifier = "correct-verifier-" + "a" * 40
    parameters = {
        "client_id": provider.CLIENT,
        "redirect_uri": provider.REDIRECT,
        "response_type": "code",
        "scope": "openid profile email",
        "code_challenge_method": "S256",
        "state": "state-" + "s" * 32,
        "nonce": "nonce-" + "n" * 32,
        "code_challenge": provider.b64(hashlib.sha256(verifier.encode()).digest()),
    }
    parameters.update(changes)
    response = client.get("/authorize", params=parameters)
    return response, verifier


def code(client, config):
    response, verifier = authorization(client)
    assert response.status_code == 200
    handle = re.search('name="handle" value="([^"]+)"', response.text)[1]
    login = client.post(
        "/login",
        data={
            "handle": handle,
            "username": "owner",
            "password": config["accounts"]["owner"]["password"],
        },
    )
    assert login.status_code == 303
    location = urlsplit(login.headers["location"])
    assert (
        location.scheme + "://" + location.netloc + location.path == provider.REDIRECT
    )
    query = parse_qs(location.query)
    assert query["state"] == ["state-" + "s" * 32]
    return query["code"][0], verifier


def exchange(client, config, value, verifier, **changes):
    data = {
        "grant_type": "authorization_code",
        "code": value,
        "redirect_uri": provider.REDIRECT,
        "code_verifier": verifier,
    }
    data.update(changes)
    return client.post(
        "/token", data=data, auth=(provider.CLIENT, config["client_secret"])
    )


def test_real_http_discovery_jwks_signature_audience_nonce_and_subject(issuer):
    client, config = issuer
    metadata = client.get("/.well-known/openid-configuration").json()
    assert metadata["issuer"] == provider.ISSUER and metadata[
        "code_challenge_methods_supported"
    ] == ["S256"]
    value, verifier = code(client, config)
    response = exchange(client, config, value, verifier)
    assert response.status_code == 200
    tokens = response.json()
    live_verifier = OIDCTokenVerifier(
        provider.ISSUER, provider.AUDIENCE, DiscoveryJWKClient(provider.ISSUER, False)
    )
    assert live_verifier.verify(tokens["access_token"]).subject == "synthetic-owner"
    public = jwt.PyJWK.from_dict(client.get("/jwks").json()["keys"][0]).key
    claims = jwt.decode(
        tokens["id_token"],
        public,
        algorithms=["RS256"],
        issuer=provider.ISSUER,
        audience=provider.CLIENT,
    )
    assert claims["nonce"] == "nonce-" + "n" * 32
    assert claims["at_hash"] == provider.b64(
        hashlib.sha256(tokens["access_token"].encode()).digest()[:16]
    )
    assert (
        client.get(
            "/userinfo", headers={"Authorization": "Bearer " + tokens["access_token"]}
        ).json()["sub"]
        == "synthetic-owner"
    )
    receipt = client.get("/receipts").json()
    assert (
        receipt["counts"]["authenticated_grants"] == 1 and receipt["counts"]["jwks"] > 0
    )
    assert not receipt["conformance_certification"]
    assert "access_token" not in json.dumps(receipt)


@pytest.mark.parametrize(
    "changes",
    [
        {"redirect_uri": "https://external.invalid/callback"},
        {"client_id": "wrong-client"},
        {"response_type": "token"},
        {"scope": "profile"},
        {"code_challenge_method": "plain"},
        {"code_challenge": "bad"},
        {"nonce": ""},
        {"state": ""},
    ],
)
def test_authorization_rejects_unsafe_protocol_parameters(issuer, changes):
    assert authorization(issuer[0], **changes)[0].status_code == 400


def test_code_one_use_and_no_second_token_grant(issuer):
    client, config = issuer
    value, verifier = code(client, config)
    assert exchange(client, config, value, verifier).status_code == 200
    assert exchange(client, config, value, verifier).status_code == 400
    assert client.get("/receipts").json()["counts"]["authenticated_grants"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"code_verifier": "b" * 60},
        {"code_verifier": "💰" * 50},
        {"redirect_uri": "https://external.invalid"},
        {"grant_type": "password"},
    ],
)
def test_failed_exchange_consumes_code_without_issuing_tokens(issuer, changes):
    client, config = issuer
    value, verifier = code(client, config)
    assert exchange(client, config, value, verifier, **changes).status_code == 400
    assert exchange(client, config, value, verifier).status_code == 400


def test_wrong_client_secret_cannot_exchange_code(issuer):
    client, config = issuer
    value, verifier = code(client, config)
    bad = {**config, "client_secret": "wrong"}
    assert exchange(client, bad, value, verifier).status_code == 401
    assert exchange(client, config, value, verifier).status_code == 200


def test_wrong_password_and_replayed_login_handle_rejected(issuer):
    client, _config = issuer
    response, _ = authorization(client)
    handle = re.search('name="handle" value="([^"]+)"', response.text)[1]
    for _ in range(2):
        assert (
            client.post(
                "/login",
                data={"handle": handle, "username": "owner", "password": "wrong"},
            ).status_code
            == 400
        )


def test_unknown_and_expired_codes_rejected(issuer, monkeypatch):
    client, config = issuer
    assert exchange(client, config, "unknown", "a" * 64).status_code == 400
    value, verifier = code(client, config)
    real_time = time.time()
    monkeypatch.setattr(provider, "time", SimpleNamespace(time=lambda: real_time + 61))
    assert exchange(client, config, value, verifier).status_code == 400


def test_expired_signed_access_token_and_id_token_rejected_by_backend(
    issuer, monkeypatch
):
    client, config = issuer
    real_time = time.time()
    monkeypatch.setattr(
        provider, "time", SimpleNamespace(time=lambda: real_time - 1200)
    )
    value, verifier = code(client, config)
    tokens = exchange(client, config, value, verifier).json()
    live = OIDCTokenVerifier(
        provider.ISSUER, provider.AUDIENCE, DiscoveryJWKClient(provider.ISSUER, False)
    )
    for token in (tokens["access_token"], tokens["id_token"]):
        with pytest.raises(InvalidIdentityToken):
            live.verify(token)


def test_wrong_audience_and_modified_signature_rejected(issuer):
    client, config = issuer
    value, verifier = code(client, config)
    token = exchange(client, config, value, verifier).json()["access_token"]
    live = OIDCTokenVerifier(
        provider.ISSUER, "another-api", DiscoveryJWKClient(provider.ISSUER, False)
    )
    with pytest.raises(InvalidIdentityToken):
        live.verify(token)
    live.audience = provider.AUDIENCE
    parts = token.split(".")
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    with pytest.raises(InvalidIdentityToken):
        live.verify(".".join(parts))


def test_host_boundary_and_missing_configuration(issuer):
    assert (
        issuer[0].get("/jwks", headers={"Host": "external.invalid"}).status_code == 400
    )
    with pytest.raises(ValueError):
        provider.create_provider({"synthetic": False})


def test_unexchanged_authorization_codes_cannot_accumulate_without_bound(issuer):
    client, config = issuer
    for _ in range(20):
        code(client, config)
    assert authorization(client)[0].status_code == 400
    assert client.get("/receipts").json()["counts"]["authenticated_grants"] == 0
