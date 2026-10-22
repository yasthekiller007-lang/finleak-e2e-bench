"""Disposable loopback OIDC authorization-code issuer. Test-only, never product auth.

PKCE S256, nonce, exact redirect URI, confidential client authentication, one-use
codes, RS256 ID/access tokens and a real discovery/JWKS HTTP surface are required.
This implements the narrow protocol used by FINLEAK, not an OIDC certification.
"""

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

ISSUER = "http://127.0.0.1:9100"
CLIENT = "finleak-p0-browser"
AUDIENCE = "finleak-p0-api"
REDIRECT = "http://127.0.0.1:3000/api/auth/callback/oidc"


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def create_provider(config):
    if config.get("synthetic") is not True or len(config.get("client_secret", "")) < 32:
        raise ValueError("Explicit synthetic ephemeral configuration required")
    accounts = config["accounts"]
    if set(accounts) != {"owner", "analyst"}:
        raise ValueError("Exactly two synthetic accounts required")
    if any(len(a["password"]) < 32 for a in accounts.values()):
        raise ValueError("Ephemeral synthetic credentials required")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    kid = secrets.token_hex(16)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid=kid, use="sig", alg="RS256")
    pending, codes = {}, {}
    counts = {"discovery": 0, "jwks": 0, "authorization": 0, "authenticated_grants": 0}
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def boundary(request, next_):
        if request.headers.get("host") != ISSUER.removeprefix("http://"):
            return JSONResponse({"error": "invalid_host"}, status_code=400)
        response = await next_(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; form-action 'self'; frame-ancestors 'none'",
            }
        )
        return response

    @app.get("/.well-known/openid-configuration")
    def discovery():
        counts["discovery"] += 1
        return {
            "issuer": ISSUER,
            "authorization_endpoint": ISSUER + "/authorize",
            "token_endpoint": ISSUER + "/token",
            "userinfo_endpoint": ISSUER + "/userinfo",
            "jwks_uri": ISSUER + "/jwks",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic"],
            "scopes_supported": ["openid", "profile", "email"],
            "code_challenge_methods_supported": ["S256"],
        }

    @app.get("/jwks")
    def jwks():
        counts["jwks"] += 1
        return {"keys": [jwk]}

    def expire():
        now = time.time()
        for bucket in (pending, codes):
            for identity in list(bucket):
                if bucket[identity]["deadline"] < now:
                    del bucket[identity]

    @app.get("/authorize", response_class=HTMLResponse)
    def authorize(request: Request):
        expire()
        q = request.query_params
        if (
            len(q.multi_items()) != len(q)
            or len(str(request.url)) > 8192
            or q.get("client_id") != CLIENT
            or q.get("redirect_uri") != REDIRECT
            or q.get("response_type") != "code"
            or "openid" not in q.get("scope", "").split()
            or q.get("code_challenge_method") != "S256"
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", q.get("code_challenge", ""))
            or not 16 <= len(q.get("state", "")) <= 512
            or not 16 <= len(q.get("nonce", "")) <= 512
            or len(pending) + len(codes) >= 20
        ):
            raise HTTPException(400, "Invalid synthetic authorization request")
        handle = secrets.token_urlsafe(32)
        pending[handle] = {
            "nonce": q["nonce"],
            "state": q["state"],
            "challenge": q["code_challenge"],
            "deadline": time.time() + 90,
        }
        counts["authorization"] += 1
        return (
            '<!doctype html><html lang="en"><title>Synthetic FINLEAK identity</title>'
            "<h1>Synthetic FINLEAK identity provider</h1><p>Disposable development accounts only.</p>"
            '<form method="post" action="/login">'
            f'<input type="hidden" name="handle" value="{html.escape(handle)}">'
            '<label>Username<input name="username" autocomplete="username" required></label>'
            '<label>Password<input name="password" type="password" autocomplete="current-password" required></label>'
            '<button type="submit">Sign In</button></form></html>'
        )

    @app.post("/login")
    def login(handle: str = Form(), username: str = Form(), password: str = Form()):
        expire()
        grant = pending.pop(handle, None)
        account = accounts.get(username)
        if (
            grant is None
            or account is None
            or not hmac.compare_digest(password, account["password"])
        ):
            raise HTTPException(
                400, "Synthetic sign-in rejected; restart authorization"
            )
        code = secrets.token_urlsafe(40)
        codes[code] = {
            **grant,
            "subject": account["subject"],
            "name": account["name"],
            "email": username + "@example.invalid",
            "deadline": time.time() + 60,
        }
        return RedirectResponse(
            REDIRECT + "?" + urlencode({"code": code, "state": grant["state"]}), 303
        )

    @app.post("/token")
    async def token(request: Request):
        expire()
        try:
            scheme, encoded = request.headers.get("authorization", "").split(" ", 1)
            client, secret = (
                base64.b64decode(encoded, validate=True).decode().split(":", 1)
            )
            assert scheme == "Basic" and client == CLIENT
            assert hmac.compare_digest(secret, config["client_secret"])
        except (ValueError, AssertionError, UnicodeError):
            raise HTTPException(401, "Invalid synthetic client") from None
        body = await request.form()
        grant = codes.pop(str(body.get("code", "")), None)
        verifier = str(body.get("code_verifier", ""))
        if (
            grant is None
            or body.get("grant_type") != "authorization_code"
            or body.get("redirect_uri") != REDIRECT
            or not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier)
            or b64(hashlib.sha256(verifier.encode()).digest()) != grant["challenge"]
        ):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        now = int(time.time())
        common = {
            "iss": ISSUER,
            "sub": grant["subject"],
            "iat": now,
            "exp": now + 600,
            "name": grant["name"],
            "email": grant["email"],
            "email_verified": True,
        }
        access = jwt.encode(
            {
                **common,
                "aud": AUDIENCE,
                "scope": "openid profile email",
                "token_use": "access",
            },
            key,
            algorithm="RS256",
            headers={"kid": kid},
        )
        identity = jwt.encode(
            {
                **common,
                "aud": CLIENT,
                "nonce": grant["nonce"],
                "auth_time": now,
                "at_hash": b64(hashlib.sha256(access.encode()).digest()[:16]),
            },
            key,
            algorithm="RS256",
            headers={"kid": kid},
        )
        counts["authenticated_grants"] += 1
        return {
            "access_token": access,
            "id_token": identity,
            "token_type": "Bearer",
            "expires_in": 600,
            "scope": "openid profile email",
        }

    @app.get("/userinfo")
    def userinfo(request: Request):
        try:
            scheme, value = request.headers.get("authorization", "").split(" ", 1)
            assert scheme == "Bearer"
            claims = jwt.decode(
                value,
                key.public_key(),
                algorithms=["RS256"],
                issuer=ISSUER,
                audience=AUDIENCE,
                options={"require": ["exp", "iat", "sub"]},
            )
            assert claims.get("token_use") == "access"
            return {k: claims[k] for k in ("sub", "name", "email", "email_verified")}
        except (ValueError, AssertionError, jwt.PyJWTError):
            raise HTTPException(401, "Invalid access token") from None

    @app.get("/receipts")
    def receipts():
        return {
            "synthetic": True,
            "protocol": "authorization_code_S256_nonce_RS256",
            "counts": dict(counts),
            "conformance_certification": False,
        }

    return app


if __name__ == "__main__":
    import uvicorn

    if (
        os.environ.get("P0_EXECUTION") != "1"
        or os.environ.get("GITHUB_ACTIONS") != "true"
    ):
        raise SystemExit(
            "Issuer service is limited to the separately authorized synthetic job"
        )
    config = json.loads(Path(os.environ["P0_OIDC_CONFIG_FILE"]).read_text())
    uvicorn.run(
        create_provider(config),
        host="127.0.0.1",
        port=9100,
        access_log=False,
        log_level="warning",
    )
