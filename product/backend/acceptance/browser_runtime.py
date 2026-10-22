"""Disposable loopback browser fixture. Never copied into production images.

Identity uses the normal OIDC discovery, code/PKCE, signed JWT and cookie paths.
The scanner alone is synthetic; this fixture is not real-provider or malware
qualification. No financial records are seeded or guards overridden.
"""

import argparse
import base64
import hashlib
import html
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.dependencies import resolve_user
from app.auth.oidc import VerifiedIdentity
from app.core.config import Settings
from app.db.models import Organization, OrganizationMembership
from app.main import create_app
from app.modules.scanner import ScanVerdict

ISSUER = "http://127.0.0.1:9001"
APP = "http://127.0.0.1:3000"
AUDIENCE = "synthetic-phase7-api"
CLIENT = "synthetic-phase7-browser"
SUBJECTS = ("owner", "admin", "analyst", "viewer", "unassigned", "other")
DIRECTORY = Path(__file__).resolve().parents[2] / ".local" / "phase7"


def guard():
    url = urlsplit(os.environ.get("FLA_DATABASE_URL", ""))
    if (
        os.environ.get("PHASE7_SYNTHETIC_ACCEPTANCE") != "1"
        or os.environ.get("FLA_ENVIRONMENT") != "test"
        or url.hostname not in {"127.0.0.1", "localhost"}
        or not url.path.endswith("phase7_browser_test")
    ):
        raise RuntimeError("Dedicated disposable loopback acceptance database required")


def seed():
    guard()
    from tests.financial_fixtures import bill, term

    engine = create_engine(os.environ["FLA_DATABASE_URL"], hide_parameters=True)
    try:
        # resolve_user commits identity creation itself; do not wrap that command
        # in a transaction context which it would close underneath the fixture.
        with Session(engine, expire_on_commit=False) as session:
            company = Organization(name="DEMO Synthetic Pilot Workshop")
            other = Organization(name="DEMO Negative Tenant")
            session.add_all([company, other])
            session.flush()
            users = {}
            for subject in SUBJECTS:
                user = resolve_user(
                    session, VerifiedIdentity(ISSUER, subject, None, f"DEMO {subject}")
                )
                users[subject] = str(user.id)
                if subject != "unassigned":
                    session.add(
                        OrganizationMembership(
                            organization_id=other.id if subject == "other" else company.id,
                            user_id=user.id,
                            role="owner" if subject == "other" else subject,
                        )
                    )
            manifest = {
                "synthetic": True,
                "company": str(company.id),
                "other": str(other.id),
                "users": users,
                "term": term().model_dump(mode="json"),
                "billing": bill().model_dump(mode="json"),
            }
            session.commit()
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        (DIRECTORY / "roster.json").write_text(json.dumps(manifest))
    finally:
        engine.dispose()


class SyntheticScanner:
    def scan(self, source, *, max_bytes, deadline):
        # Synthetic protocol response in the guard's pinned wire format, like
        # the source-gate unit fixtures. This is NOT an actual engine result;
        # the separate scanner-conformance job qualifies the real private engine.
        return ScanVerdict("CLEAN", version="clamav/1.4.6;database/28000")


def application():
    guard()
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=os.environ["FLA_DATABASE_URL"],
        scanner_database_url=os.environ["FLA_DATABASE_URL"],
        storage_root=DIRECTORY / "originals",
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        public_app_url=APP,
    )
    app = create_app(settings)
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(instance):
        async with original_lifespan(instance):
            instance.state.scanner = SyntheticScanner()
            yield

    app.router.lifespan_context = lifespan
    return app


def provider():
    guard()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public.update(kid="synthetic-browser-key", use="sig", alg="RS256")
    codes = {}

    @app.get("/.well-known/openid-configuration")
    def discovery():
        return {
            "issuer": ISSUER,
            "authorization_endpoint": ISSUER + "/authorize",
            "token_endpoint": ISSUER + "/token",
            "jwks_uri": ISSUER + "/keys",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic"],
            "code_challenge_methods_supported": ["S256"],
        }

    @app.get("/keys")
    def keys():
        return {"keys": [public]}

    @app.get("/authorize", response_class=HTMLResponse)
    def authorize(request: Request):
        params = dict(request.query_params)
        if (
            params.get("client_id") != CLIENT
            or params.get("redirect_uri") != APP + "/api/auth/callback/oidc"
            or params.get("response_type") != "code"
            or params.get("code_challenge_method") != "S256"
            or not all(params.get(k) for k in ("state", "nonce", "code_challenge"))
        ):
            raise HTTPException(400, "Invalid synthetic authorization request")
        fields = "".join(
            f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">'
            for k, v in params.items()
        )
        options = "".join(f'<option value="{s}">{s}</option>' for s in SUBJECTS)
        return (
            '<h1>DEMO synthetic identity provider</h1><form method="post" action="/choose">'
            + fields
            + '<label>Test account<select name="subject">'
            + options
            + "</select></label><button>Sign in synthetic account</button></form>"
        )

    @app.post("/choose")
    async def choose(request: Request):
        params = dict(await request.form())
        if (
            params.get("subject") not in SUBJECTS
            or params.get("redirect_uri") != APP + "/api/auth/callback/oidc"
            or params.get("client_id") != CLIENT
        ):
            raise HTTPException(400, "Invalid synthetic account")
        code = secrets.token_urlsafe(32)
        codes[code] = params | {"expires": time.monotonic() + 60}
        return RedirectResponse(
            params["redirect_uri"] + "?" + urlencode({"code": code, "state": params["state"]}),
            status_code=303,
        )

    @app.post("/token")
    async def token(request: Request):
        expected = (
            "Basic "
            + base64.b64encode((CLIENT + ":" + os.environ["OIDC_CLIENT_SECRET"]).encode()).decode()
        )
        if not secrets.compare_digest(request.headers.get("authorization", ""), expected):
            raise HTTPException(401, "Invalid synthetic client")
        data = dict(await request.form())
        params = codes.pop(data.get("code", ""), None)
        challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(data.get("code_verifier", "").encode()).digest()
            )
            .decode()
            .rstrip("=")
        )
        if (
            not params
            or params["expires"] < time.monotonic()
            or data.get("grant_type") != "authorization_code"
            or data.get("redirect_uri") != params["redirect_uri"]
            or not secrets.compare_digest(challenge, params["code_challenge"])
        ):
            raise HTTPException(400, "Invalid synthetic code or PKCE")
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "sub": params["subject"],
            "iat": now,
            "exp": now + 3600,
            "name": "DEMO " + params["subject"],
        }
        access = jwt.encode(
            claims | {"aud": AUDIENCE}, key, algorithm="RS256", headers={"kid": public["kid"]}
        )
        at_hash = (
            base64.urlsafe_b64encode(hashlib.sha256(access.encode()).digest()[:16])
            .decode()
            .rstrip("=")
        )
        identity = jwt.encode(
            claims | {"aud": CLIENT, "nonce": params["nonce"], "at_hash": at_hash},
            key,
            algorithm="RS256",
            headers={"kid": public["kid"]},
        )
        return {
            "access_token": access,
            "id_token": identity,
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["seed"])
    parser.parse_args()
    seed()
