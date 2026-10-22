import json
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient

from app.auth.oidc import OIDCTokenVerifier

ISSUER = "https://identity.example.test"
AUDIENCE = "financial-leakage-api"


class StaticJWKS(PyJWKClient):
    """Test transport only; real PyJWT key selection and signature verification remain active."""

    def __init__(self, public_jwk):
        super().__init__(ISSUER + "/keys")
        self.public_jwk = public_jwk

    def fetch_data(self):
        return {"keys": [self.public_jwk]}


class IdentityFixture:
    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        self.jwk.update(kid="fixture-key", use="sig", alg="RS256")
        self.verifier = OIDCTokenVerifier(ISSUER, AUDIENCE, StaticJWKS(self.jwk))

    def token(self, subject="user-a", *, changes=None, key=None, headers=None):
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": subject,
            "iat": now,
            "exp": now + 300,
            "email": "shared@example.test",
            "email_verified": True,
            "name": "Test account",
        }
        claims.update(changes or {})
        return jwt.encode(
            claims, key or self.key, algorithm="RS256", headers=headers or {"kid": "fixture-key"}
        )
