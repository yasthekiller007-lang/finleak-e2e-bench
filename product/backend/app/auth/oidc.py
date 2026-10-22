import json
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import httpx2 as httpx
import jwt
from jwt import PyJWKClient

from app.core.config import Settings


class InvalidIdentityToken(Exception):
    """Intentionally contains no token or provider details."""


class IdentityProviderUnavailable(Exception):
    pass


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str
    email: str | None = None
    display_name: str = "New user"


class TokenVerifier(Protocol):
    def verify(self, token: str) -> VerifiedIdentity: ...


def provider_json(uri, production):
    url = urlsplit(uri)
    local = (
        not production
        and url.scheme == "http"
        and url.hostname in {"localhost", "127.0.0.1", "::1"}
    )
    if (
        not url.hostname
        or url.username
        or url.password
        or url.fragment
        or (url.scheme != "https" and not local)
    ):
        raise jwt.PyJWKClientConnectionError("Identity endpoint unavailable")
    started, content = time.monotonic(), bytearray()
    try:
        with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", uri) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    content.extend(chunk)
                    if len(content) > 512 * 1024 or time.monotonic() - started >= 5:
                        raise ValueError("Identity response bound")
        if time.monotonic() - started >= 5:
            raise ValueError("Identity response work bound")
        value = json.loads(content)
        if not isinstance(value, dict):
            raise ValueError("Identity response shape")
        return value
    except (httpx.HTTPError, ValueError, RecursionError):
        raise jwt.PyJWKClientConnectionError("Identity response unavailable") from None


class BoundedJWKClient(PyJWKClient):
    def __init__(self, uri, production):
        super().__init__(uri, cache_jwk_set=True, lifespan=300, timeout=5)
        self.production = production

    def fetch_data(self):
        data = provider_json(self.uri, self.production)
        try:
            keys = data.get("keys")
            if not isinstance(keys, list) or not 1 <= len(keys) <= 100:
                raise ValueError("Bounded identity key set required")
            ids = [key.get("kid") for key in keys if isinstance(key, dict)]
            if len(ids) != len(keys) or any(
                not isinstance(kid, str) or not kid or len(kid) > 200 for kid in ids
            ):
                raise ValueError("Invalid identity key identifiers")
            if len(set(ids)) != len(ids):
                raise ValueError("Ambiguous identity key identifiers")
            parsed = jwt.PyJWKSet.from_dict(data)
        except (ValueError, KeyError, TypeError, jwt.PyJWTError):
            raise jwt.PyJWKClientConnectionError("Identity key set unavailable") from None
        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(parsed)
        # Match the locked PyJWT client's successful-fetch/rotation accounting.
        self._last_successful_fetch = time.monotonic()
        return parsed


class DiscoveryJWKClient(BoundedJWKClient):
    """Discover keys from the configured issuer; redirects and token URLs are ignored."""

    def __init__(self, issuer: str, production: bool):
        super().__init__(issuer, production)
        self.issuer = issuer
        self.production = production
        self.discovered = False

    def fetch_data(self):
        if not self.discovered:
            try:
                metadata = provider_json(
                    self.issuer.rstrip("/") + "/.well-known/openid-configuration",
                    self.production,
                )
                uri = metadata["jwks_uri"]
                url = urlsplit(uri)
                local = (
                    not self.production
                    and url.scheme == "http"
                    and url.hostname in {"localhost", "127.0.0.1", "::1"}
                )
                if (
                    metadata["issuer"] != self.issuer
                    or not url.hostname
                    or url.username
                    or url.password
                    or url.fragment
                    or (url.scheme != "https" and not local)
                ):
                    raise ValueError("Invalid discovery metadata")
                self.uri = uri
                self.discovered = True
            except (ValueError, KeyError, TypeError):
                raise jwt.PyJWKClientConnectionError("OIDC discovery unavailable") from None
        return super().fetch_data()


class OIDCTokenVerifier:
    """Asymmetric API access tokens, using configured JWKS (never token jku/x5u)."""

    def __init__(self, issuer: str, audience: str, jwks: PyJWKClient, algorithms=("RS256",)):
        self.issuer = issuer
        self.audience = audience
        self.jwks = jwks
        self.algorithms = algorithms

    def verify(self, token: str) -> VerifiedIdentity:
        if len(token) > 8192:
            raise InvalidIdentityToken()
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in self.algorithms or not isinstance(header.get("kid"), str):
                raise InvalidIdentityToken()
            key = self.jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=list(self.algorithms),
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            subject = claims["sub"]
            if (
                not isinstance(subject, str)
                or not subject
                or len(subject) > 255
                or not subject.isascii()
                or any(ord(char) < 32 for char in subject)
                or claims.get("token_use") == "id"
            ):
                raise InvalidIdentityToken()
            email = claims.get("email") if claims.get("email_verified") is True else None
            if not isinstance(email, str) or len(email) > 320 or "@" not in email:
                email = None
            name = claims.get("name")
            if not isinstance(name, str) or not name.strip():
                name = "New user"
            name = "".join(char for char in name if ord(char) >= 32).strip()[:200]
            return VerifiedIdentity(self.issuer, subject, email, name or "New user")
        except jwt.PyJWKClientConnectionError as exc:
            raise IdentityProviderUnavailable() from exc
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise InvalidIdentityToken() from exc


def build_token_verifier(settings: Settings) -> TokenVerifier | None:
    if not all((settings.oidc_issuer, settings.oidc_audience)):
        return None
    return OIDCTokenVerifier(
        settings.oidc_issuer,
        settings.oidc_audience,
        BoundedJWKClient(settings.oidc_jwks_url, settings.environment == "production")
        if settings.oidc_jwks_url
        else DiscoveryJWKClient(settings.oidc_issuer, settings.environment == "production"),
        tuple(settings.oidc_signing_algorithms),
    )
