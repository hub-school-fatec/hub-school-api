from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import AuthenticationError, validate_access_token


_bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        return validate_access_token(credentials.credentials)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Não autenticado") from None
