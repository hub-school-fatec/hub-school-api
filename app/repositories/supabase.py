import logging
import os
import re

import httpx
import jwt
from fastapi import HTTPException

from app.core.config import get_settings


_diagnostic_logger = logging.getLogger("uvicorn.error")


def _log_local_frequency_rejection(method: str, table: str, status: int, code: object) -> None:
    # Opt-in for a local diagnostic session; never include response text or request data.
    if (os.environ.get("HUB_SCHOOL_LOCAL_POSTGREST_DIAGNOSTICS") != "1"
            or table != "frequencia" or method != "POST"):
        return
    safe_code = code if isinstance(code, str) and re.fullmatch(r"(?:[A-Z0-9]{5}|PGRST[0-9]{3})", code) else "unknown"
    _diagnostic_logger.warning(
        "postgrest_diagnostic table=frequencia method=POST http_status=%d db_code=%s",
        status, safe_code,
    )


def _public_key(key: str) -> bool:
    if key.startswith("sb_publishable_"):
        return True
    try:
        return jwt.decode(key, options={"verify_signature": False}).get("role") == "anon"
    except (jwt.PyJWTError, ValueError, TypeError):
        return False


class PostgrestClient:
    def __init__(self, client: httpx.Client, table: str = "semestre"):
        if table not in ("semestre", "docente", "disciplina", "horario_aula", "avaliacao", "frequencia", "evento", "anotacao", "anexo", "calendario_academico"):
            raise ValueError("Tabela não permitida")
        settings = get_settings()
        url = settings.auth_project_url()
        key = settings.supabase_publishable_key or settings.supabase_anon_key
        if not url or not _public_key(key):
            raise HTTPException(503, "Serviço indisponível")
        self.client = client
        self.table = table
        self.url = f"{url}/rest/v1/{table}"
        self.key = key
        self.not_found = {
            "semestre": "Semestre não encontrado",
            "docente": "Docente não encontrado",
            "disciplina": "Disciplina não encontrada",
            "horario_aula": "Horário de aula não encontrado",
            "avaliacao": "Avaliação não encontrada",
            "frequencia": "Frequência não encontrada",
            "evento": "Evento não encontrado",
            "anotacao": "Anotação não encontrada",
            "anexo": "Anexo não encontrado",
            "calendario_academico": "Calendário acadêmico não encontrado",
        }[table]

    def request(self, method: str, token: str, params: dict, data: dict | None = None) -> list[dict]:
        try:
            response = self.client.request(
                method, self.url, params=params,
                headers={"apikey": self.key, "Authorization": f"Bearer {token}",
                         "Prefer": "return=representation"},
                json=data, timeout=5,
            )
        except httpx.HTTPError:
            raise HTTPException(503, "Serviço indisponível") from None
        if response.status_code in (401, 403):
            raise HTTPException(response.status_code, "Acesso negado")
        if response.status_code == 409:
            raise HTTPException(409, "Conflito")
        if response.status_code == 404:
            raise HTTPException(404, self.not_found)
        if response.status_code >= 400:
            try:
                body = response.json()
                code = body.get("code") if isinstance(body, dict) else None
            except ValueError:
                code = None
            _log_local_frequency_rejection(method, self.table, response.status_code, code)
            if code in ("23505", "23P01"):
                raise HTTPException(409, "Conflito")
            if code in ("23514", "23502", "23503", "22007", "22008", "22P02"):
                raise HTTPException(422, "Dados inválidos")
            raise HTTPException(503, "Serviço indisponível")
        try:
            rows = response.json()
        except ValueError:
            raise HTTPException(503, "Serviço indisponível") from None
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise HTTPException(503, "Serviço indisponível")
        return rows
