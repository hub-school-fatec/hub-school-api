"""Teste manual, somente leitura, de semestres via FastAPI local."""

from getpass import getpass

import httpx

from app.core.config import get_settings
from scripts.test_auth_real import is_public_key


API_URL = "http://127.0.0.1:8000/semestres"
TIMEOUT_SECONDS = 10


def main() -> int:
    try:
        settings = get_settings()
        project_url = settings.auth_project_url()
        public_key = settings.supabase_publishable_key or settings.supabase_anon_key
        if not project_url or not is_public_key(public_key):
            print("HTTP: indisponivel | Semestres: indisponivel | FALHOU")
            return 1

        email = getpass("E-mail do usuario de teste: ")
        password = getpass("Senha: ")
        if not email or not password:
            print("HTTP: indisponivel | Semestres: indisponivel | FALHOU")
            return 1

        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            login = client.post(
                f"{project_url}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": public_key},
                json={"email": email, "password": password},
            )
            if login.status_code != 200:
                print(f"HTTP Auth: {login.status_code} | Semestres: indisponivel | FALHOU")
                return 1

            payload = login.json()
            token = payload.get("access_token") if isinstance(payload, dict) else None
            if not isinstance(token, str) or not token:
                print("HTTP Auth: 200 | Semestres: indisponivel | FALHOU")
                return 1

            response = client.get(API_URL, headers={"Authorization": f"Bearer {token}"})
            if response.status_code != 200:
                print(f"HTTP: {response.status_code} | Semestres: indisponivel | FALHOU")
                return 1

            rows = response.json()
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                print("HTTP: 200 | Semestres: indisponivel | FALHOU")
                return 1
            print(f"HTTP: 200 | Semestres: {len(rows)} | PASSOU")
            return 0
    except (httpx.HTTPError, ValueError, TypeError, OSError):
        print("HTTP: indisponivel | Semestres: indisponivel | FALHOU")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
