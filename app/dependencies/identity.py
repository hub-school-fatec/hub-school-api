from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import AuthenticationError, validate_access_token
from app.dependencies.auth import _bearer


@dataclass(frozen=True)
class AuthenticatedIdentity:
    user_id: UUID
    access_token: str


def get_authenticated_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        user_id = UUID(validate_access_token(credentials.credentials))
        claims = jwt.decode(credentials.credentials, options={"verify_signature": False})
        if claims.get("role") != "authenticated":
            raise ValueError
        return AuthenticatedIdentity(user_id, credentials.credentials)
    except (AuthenticationError, ValueError, jwt.PyJWTError):
        raise HTTPException(status_code=401, detail="Não autenticado") from None
