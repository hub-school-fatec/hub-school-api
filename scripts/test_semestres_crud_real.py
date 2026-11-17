"""Teste manual de CRUD de um semestre temporario. Nao executa ao importar."""

from getpass import getpass
from uuid import UUID, uuid4

import httpx

from app.core.config import get_settings
from scripts.test_auth_real import is_public_key


API_URL = "http://127.0.0.1:8000/semestres"
TIMEOUT_SECONDS = 10


class TestFailed(Exception):
    pass


def _result(operation: str, passed: bool) -> None:
    print(f"{operation}: {'PASSOU' if passed else 'FALHOU'}")


def _matches(response: httpx.Response, semester_id: UUID, name: str) -> bool:
    if response.status_code != 200:
        return False
    try:
        body = response.json()
        return (isinstance(body, dict) and UUID(body.get("id", "")) == semester_id
                and body.get("nome") == name and body.get("ativo") is False)
    except (ValueError, TypeError, AttributeError):
        return False


def _login(client: httpx.Client, project_url: str, public_key: str) -> str | None:
    email = getpass("E-mail do usuario de teste: ")
    password = getpass("Senha: ")
    if not email or not password:
        return None
    try:
        response = client.post(
            f"{project_url}/auth/v1/token", params={"grant_type": "password"},
            headers={"apikey": public_key}, json={"email": email, "password": password},
        )
        if response.status_code != 200:
            return None
        body = response.json()
        token = body.get("access_token") if isinstance(body, dict) else None
        return token if isinstance(token, str) and token else None
    except (httpx.HTTPError, ValueError, TypeError):
        return None


def _run_crud(client: httpx.Client, token: str) -> bool:
    headers = {"Authorization": f"Bearer {token}"}
    name = f"TESTE_API_{uuid4().hex}"
    updated_name = f"{name}_ALTERADO"
    semester_id: UUID | None = None
    delete_attempted = False
    deleted = False
    passed = False

    try:
        try:
            response = client.post(
                API_URL, headers=headers,
                json={"nome": name, "data_inicio": "2026-01-01",
                      "data_fim": "2026-06-30", "ativo": False},
            )
            if response.status_code == 201:
                body = response.json()
                if isinstance(body, dict) and body.get("nome") == name and body.get("ativo") is False:
                    semester_id = UUID(body.get("id", ""))
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            pass
        _result("POST", semester_id is not None)
        if semester_id is None:
            print("Limpeza: nao confirmada; o semestre temporario pode permanecer no banco")
            return False

        url = f"{API_URL}/{semester_id}"
        try:
            own = _matches(client.get(url, headers=headers), semester_id, name)
        except httpx.HTTPError:
            own = False
        _result("GET por ID", own)
        if not own:
            raise TestFailed

        try:
            patch_response = client.patch(url, headers=headers, json={"nome": updated_name})
            patched = _matches(patch_response, semester_id, updated_name)
        except httpx.HTTPError:
            patched = False
        _result("PATCH", patched)
        if not patched:
            raise TestFailed

        try:
            persisted = _matches(client.get(url, headers=headers), semester_id, updated_name)
        except httpx.HTTPError:
            persisted = False
        _result("GET apos PATCH", persisted)
        if not persisted:
            raise TestFailed

        delete_attempted = True
        try:
            deleted = client.delete(url, headers=headers).status_code == 204
        except httpx.HTTPError:
            deleted = False
        _result("DELETE", deleted)
        if not deleted:
            raise TestFailed

        try:
            absent = client.get(url, headers=headers).status_code == 404
        except httpx.HTTPError:
            absent = False
        _result("GET apos DELETE", absent)
        passed = absent
    except TestFailed:
        pass
    finally:
        if semester_id is not None:
            if not delete_attempted:
                # Uma unica tentativa de limpeza; nenhuma escrita recebe retry apos timeout.
                try:
                    deleted = client.delete(f"{API_URL}/{semester_id}", headers=headers).status_code == 204
                except httpx.HTTPError:
                    deleted = False
            if deleted:
                try:
                    absent = client.get(f"{API_URL}/{semester_id}", headers=headers).status_code == 404
                except httpx.HTTPError:
                    absent = False
                if absent:
                    print("Limpeza: confirmada")
                else:
                    print("Limpeza: nao confirmada; o semestre temporario pode permanecer no banco")
                    passed = False
            else:
                print("Limpeza: nao confirmada; o semestre temporario pode permanecer no banco")
                passed = False
    return passed


def main() -> int:
    settings = get_settings()
    project_url = settings.auth_project_url()
    public_key = settings.supabase_publishable_key or settings.supabase_anon_key
    if not project_url or not is_public_key(public_key):
        print("Configuracao: FALHOU")
        return 1

    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        token = _login(client, project_url, public_key)
        if token is None:
            print("Autenticacao: FALHOU")
            return 1
        print("Autenticacao: PASSOU")
        if input("Digite SIM para criar e remover um semestre temporario: ").strip() != "SIM":
            print("Confirmacao: FALHOU; nenhuma escrita iniciada")
            return 1
        return 0 if _run_crud(client, token) else 1


if __name__ == "__main__":
    raise SystemExit(main())
