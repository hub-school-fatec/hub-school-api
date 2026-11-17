"""Teste manual de isolamento de semestres. Executar somente por decisao do operador."""

from getpass import getpass
from uuid import UUID, uuid4

import httpx
import jwt

from app.core.config import get_settings
from app.core.security import AuthenticationError, validate_access_token
from scripts.test_auth_real import is_public_key


API_URL = "http://127.0.0.1:8000/semestres"
TIMEOUT_SECONDS = 10


class StopTest(Exception):
    pass


def report(label: str, passed: bool, status: int | None = None) -> None:
    code = str(status) if status is not None else "indisponivel"
    print(f"{label}: {'PASSOU' if passed else 'FALHOU'} (HTTP {code})")


def login(client: httpx.Client, project_url: str, key: str, label: str) -> tuple[str, UUID] | None:
    email = getpass(f"E-mail do usuario {label}: ")
    password = getpass(f"Senha do usuario {label}: ")
    if not email or not password:
        report(f"AUTH_{label}", False)
        return None
    try:
        response = client.post(
            f"{project_url}/auth/v1/token", params={"grant_type": "password"},
            headers={"apikey": key}, json={"email": email, "password": password},
        )
        if response.status_code != 200:
            report(f"AUTH_{label}", False, response.status_code)
            return None
        body = response.json()
        token = body.get("access_token") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token:
            report(f"AUTH_{label}", False, response.status_code)
            return None
        user_id = UUID(validate_access_token(token))
        # O papel e examinado apenas depois da verificacao criptografica do JWT.
        claims = jwt.decode(token, options={"verify_signature": False})
        if claims.get("role") != "authenticated":
            report(f"AUTH_{label}", False, response.status_code)
            return None
        report(f"AUTH_{label}", True, response.status_code)
        return token, user_id
    except (httpx.HTTPError, ValueError, TypeError, AuthenticationError, jwt.PyJWTError):
        report(f"AUTH_{label}", False)
        return None


def profile_exists(client: httpx.Client, project_url: str, key: str,
                   token: str, user_id: UUID, label: str) -> bool:
    try:
        response = client.get(
            f"{project_url}/rest/v1/usuario",
            params={"select": "id", "id": f"eq.{user_id}"},
            headers={"apikey": key, "Authorization": f"Bearer {token}"},
        )
        rows = response.json() if response.status_code == 200 else None
        valid = (isinstance(rows, list) and len(rows) == 1
                 and isinstance(rows[0], dict) and UUID(rows[0].get("id", "")) == user_id)
        report(f"PERFIL_{label}", valid, response.status_code)
        return valid
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        report(f"PERFIL_{label}", False)
        return False


def own_record(response: httpx.Response, semester_id: UUID, name: str,
               owner: UUID) -> bool:
    if response.status_code != 200:
        return False
    try:
        body = response.json()
        return (isinstance(body, dict) and UUID(body.get("id", "")) == semester_id
                and UUID(body.get("usuario_id", "")) == owner
                and body.get("nome") == name and body.get("ativo") is False)
    except (ValueError, TypeError, AttributeError):
        return False


def run_isolation(client: httpx.Client, token_a: str, token_b: str, user_a: UUID) -> bool:
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    name = f"TESTE_RLS_{uuid4().hex}"
    semester_id: UUID | None = None
    delete_attempted = False
    deleted = False
    passed = False
    post_status: int | None = None

    try:
        try:
            response = client.post(
                API_URL, headers=headers_a,
                json={"nome": name, "data_inicio": "2026-01-01",
                      "data_fim": "2026-06-30", "ativo": False},
            )
            post_status = response.status_code
            if response.status_code == 201:
                body = response.json()
                if (isinstance(body, dict) and body.get("nome") == name
                        and body.get("ativo") is False
                        and UUID(body.get("usuario_id", "")) == user_a):
                    semester_id = UUID(body.get("id", ""))
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            pass
        report("POST_A", semester_id is not None, post_status)
        if semester_id is None:
            print("Limpeza: nao confirmada; um semestre temporario pode permanecer no banco")
            return False

        url = f"{API_URL}/{semester_id}"

        try:
            response = client.get(url, headers=headers_a)
            own = own_record(response, semester_id, name, user_a)
            report("GET_PROPRIO_A", own, response.status_code)
        except httpx.HTTPError:
            own = False
            report("GET_PROPRIO_A", False)
        if not own:
            raise StopTest

        # Se B enxergar o registro, interromper antes de qualquer escrita com B.
        try:
            response = client.get(url, headers=headers_b)
            isolated = response.status_code == 404
            report("GET_CRUZADO_B", isolated, response.status_code)
        except httpx.HTTPError:
            isolated = False
            report("GET_CRUZADO_B", False)
        if not isolated:
            print("ISOLAMENTO: FALHA CRITICA")
            raise StopTest

        try:
            response = client.patch(url, headers=headers_b, json={"nome": f"{name}_B"})
            isolated = response.status_code == 404
            report("PATCH_CRUZADO_B", isolated, response.status_code)
        except httpx.HTTPError:
            isolated = False
            report("PATCH_CRUZADO_B", False)
        if not isolated:
            raise StopTest

        try:
            response = client.delete(url, headers=headers_b)
            isolated = response.status_code == 404
            report("DELETE_CRUZADO_B", isolated, response.status_code)
        except httpx.HTTPError:
            isolated = False
            report("DELETE_CRUZADO_B", False)
        if not isolated:
            raise StopTest

        try:
            response = client.get(url, headers=headers_a)
            intact = own_record(response, semester_id, name, user_a)
            report("GET_INTACTO_A", intact, response.status_code)
        except httpx.HTTPError:
            intact = False
            report("GET_INTACTO_A", False)
        if not intact:
            raise StopTest

        delete_attempted = True
        try:
            response = client.delete(url, headers=headers_a)
            deleted = response.status_code == 204
            report("DELETE_A", deleted, response.status_code)
        except httpx.HTTPError:
            report("DELETE_A", False)
        if not deleted:
            raise StopTest

        try:
            response = client.get(url, headers=headers_a)
            passed = response.status_code == 404
            report("GET_EXCLUIDO_A", passed, response.status_code)
        except httpx.HTTPError:
            report("GET_EXCLUIDO_A", False)
    except StopTest:
        pass
    finally:
        if semester_id is not None:
            if not delete_attempted:
                # Somente o ID recebido no POST desta execucao; uma tentativa de DELETE.
                try:
                    response = client.delete(f"{API_URL}/{semester_id}", headers=headers_a)
                    deleted = response.status_code == 204
                    report("LIMPEZA_DELETE_A", deleted, response.status_code)
                except httpx.HTTPError:
                    report("LIMPEZA_DELETE_A", False)
            if deleted:
                try:
                    response = client.get(f"{API_URL}/{semester_id}", headers=headers_a)
                    confirmed = response.status_code == 404
                except httpx.HTTPError:
                    confirmed = False
                if confirmed:
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
    key = settings.supabase_publishable_key or settings.supabase_anon_key
    if not project_url or not is_public_key(key):
        print("CONFIGURACAO: FALHOU")
        return 1

    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        a = login(client, project_url, key, "A")
        if a is None:
            return 1
        b = login(client, project_url, key, "B")
        if b is None:
            return 1
        distinct = a[1] != b[1]
        report("IDENTIDADES_DISTINTAS", distinct)
        if not distinct:
            return 1
        if not profile_exists(client, project_url, key, a[0], a[1], "A"):
            return 1
        if not profile_exists(client, project_url, key, b[0], b[1], "B"):
            return 1
        if input("Digite SIM para iniciar o teste com escrita temporaria: ").strip() != "SIM":
            print("CONFIRMACAO: FALHOU; nenhuma escrita iniciada")
            return 1
        return 0 if run_isolation(client, a[0], b[0], a[1]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
