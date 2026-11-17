import threading
import time

import httpx
import jwt
from jwt import PyJWK

from app.core.config import get_settings


class AuthenticationError(Exception):
    pass


_lock = threading.Lock()
_jwks_cache: dict[str, tuple[float, dict]] = {}
_JWKS_TTL_SECONDS = 300
_JWKS_TIMEOUT_SECONDS = 5


def _get_jwks(project_url: str) -> dict:
    now = time.monotonic()
    with _lock:
        cached = _jwks_cache.get(project_url)
        if cached and cached[0] > now:
            return cached[1]
        try:
            response = httpx.get(
                f"{project_url}/auth/v1/.well-known/jwks.json",
                timeout=_JWKS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            jwks = response.json()
            if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
                raise ValueError("Invalid JWKS")
        except (httpx.HTTPError, ValueError):
            raise AuthenticationError from None
        _jwks_cache.clear()
        _jwks_cache[project_url] = (time.monotonic() + _JWKS_TTL_SECONDS, jwks)
        return jwks


def validate_access_token(token: str) -> str:
    settings = get_settings()
    project_url = settings.auth_project_url()
    if not project_url:
        raise AuthenticationError
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if header.get("alg") != "ES256" or not isinstance(kid, str) or not kid:
            raise AuthenticationError
        keys = [key for key in _get_jwks(project_url)["keys"]
                if isinstance(key, dict) and key.get("kid") == kid
                and key.get("kty") == "EC" and key.get("crv") == "P-256"
                and key.get("alg", "ES256") == "ES256"]
        if len(keys) != 1:
            raise AuthenticationError
        public_key = PyJWK.from_dict(keys[0], algorithm="ES256").key
        claims = jwt.decode(
            token, public_key, algorithms=["ES256"],
            issuer=settings.supabase_jwt_issuer, audience="authenticated",
            options={"require": ["exp", "iss", "aud", "sub"]}, leeway=5,
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError
        return subject
    except (jwt.PyJWTError, ValueError, TypeError, KeyError, AuthenticationError):
        raise AuthenticationError from None
