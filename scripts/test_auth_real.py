"""Teste manual de Supabase Auth contra o FastAPI local. Nunca importa com efeito de rede."""

from getpass import getpass

import httpx
import jwt

from app.core.config import Settings


API_URL = "http://127.0.0.1:8000/auth/me"
TIMEOUT_SECONDS = 10


class LoginSettings(Settings):
    supabase_publishable_key: str = ""


def is_public_key(key: str) -> bool:
    if key.startswith("sb_publishable_"):
        return True
    try:
        claims = jwt.decode(key, options={"verify_signature": False})
        return claims.get("role") == "anon"
    except (jwt.PyJWTError, ValueError, TypeError):
        return False


def main() -> int:
    try:
        settings = LoginSettings()
        project_url = settings.auth_project_url()
        public_key = settings.supabase_publishable_key or settings.supabase_anon_key
        if not project_url or not is_public_key(public_key):
            print("HTTP: indisponível | Teste: FALHOU")
            return 1

        email = getpass("E-mail do usuário de teste: ")
        password = getpass("Senha: ")
        if not email or not password:
            print("HTTP: indisponível | Teste: FALHOU")
            return 1

        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            login = client.post(
                f"{project_url}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": public_key},
                json={"email": email, "password": password},
            )
            if login.status_code != 200:
                print(f"HTTP: {login.status_code} | Teste: FALHOU")
                return 1
            payload = login.json()
            token = payload.get("access_token") if isinstance(payload, dict) else None
            if not isinstance(token, str) or not token:
                print("HTTP: 200 | Teste: FALHOU")
                return 1

            result = client.get(API_URL, headers={"Authorization": f"Bearer {token}"})
            valid = result.status_code == 200
            if valid:
                body = result.json()
                valid = isinstance(body, dict) and isinstance(body.get("user_id"), str) and bool(body["user_id"])
            print(f"HTTP: {result.status_code} | Teste: {'PASSOU' if valid else 'FALHOU'}")
            return 0 if valid else 1
    except (httpx.HTTPError, ValueError, TypeError, OSError):
        print("HTTP: indisponível | Teste: FALHOU")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
