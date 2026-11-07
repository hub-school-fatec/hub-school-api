from functools import lru_cache

from fastapi import HTTPException, status
from jwt import PyJWKClient
import jwt

from app.core.config import settings


JWT_ALGORITHM = "ES256"
JWT_AUDIENCE = "authenticated"


@lru_cache(maxsize=8)
def get_jwks_client(url: str, lifespan: int, timeout: int) -> PyJWKClient:
    # Cache the set, not individual keys indefinitely; unknown kid triggers refresh.
    return PyJWKClient(url, cache_jwk_set=True, lifespan=lifespan, timeout=timeout)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def validate_access_token(token: str) -> str:
    if not settings.supabase_url or not settings.supabase_jwt_issuer:
        raise _unauthorized()

    jwks_url = (
        f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    )

    try:
        header = jwt.get_unverified_header(token)
        if header.get('alg') != JWT_ALGORITHM or not isinstance(header.get('kid'), str) or not header['kid'].strip():
            raise _unauthorized()
        jwks_client = get_jwks_client(jwks_url, settings.jwks_cache_seconds, settings.jwks_timeout_seconds)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=settings.supabase_jwt_issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except (jwt.PyJWTError, ValueError):
        raise _unauthorized() from None

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise _unauthorized()

    return subject
