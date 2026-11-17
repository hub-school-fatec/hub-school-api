from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.repositories.supabase import _public_key


BUCKET = "hub-school-anexos"
MAX_BYTES = 10_485_760


class StorageClient:
    def __init__(self, client: httpx.Client):
        settings = get_settings()
        project_url = settings.auth_project_url()
        key = settings.supabase_publishable_key or settings.supabase_anon_key
        if not project_url or not _public_key(key):
            raise HTTPException(503, "Serviço indisponível")
        self.client = client
        self.base_url = f"{project_url}/storage/v1/object"
        self.key = key

    def _headers(self, token: str) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {token}"}

    @staticmethod
    def _encoded_path(path: str) -> str:
        return "/".join(quote(part, safe="") for part in path.split("/"))

    def upload(self, path: str, data: bytes, mime: str, token: str) -> None:
        try:
            response = self.client.post(
                f"{self.base_url}/{BUCKET}/{self._encoded_path(path)}",
                content=data, headers={**self._headers(token), "Content-Type": mime,
                                       "x-upsert": "false"}, timeout=20,
            )
        except httpx.HTTPError:
            raise HTTPException(503, "Estado do upload não confirmado") from None
        if response.status_code in (200, 201):
            return
        if response.status_code in (401, 403):
            raise HTTPException(response.status_code, "Acesso negado")
        if response.status_code == 409:
            raise HTTPException(409, "Conflito")
        raise HTTPException(503, "Falha no Storage")

    def download(self, path: str, token: str) -> bytes:
        try:
            with self.client.stream(
                "GET", f"{self.base_url}/authenticated/{BUCKET}/{self._encoded_path(path)}",
                headers=self._headers(token), timeout=20,
            ) as response:
                if response.status_code in (401, 403, 404):
                    raise HTTPException(404, "Anexo não encontrado")
                if response.status_code != 200:
                    raise HTTPException(503, "Falha no Storage")
                result = bytearray()
                for chunk in response.iter_bytes():
                    result.extend(chunk)
                    if len(result) > MAX_BYTES:
                        raise HTTPException(503, "Falha no Storage")
                return bytes(result)
        except httpx.HTTPError:
            raise HTTPException(503, "Falha no Storage") from None

    def delete(self, path: str, token: str) -> None:
        try:
            response = self.client.delete(
                f"{self.base_url}/{BUCKET}/{self._encoded_path(path)}",
                headers=self._headers(token), timeout=20,
            )
        except httpx.HTTPError:
            raise HTTPException(503, "Exclusão não confirmada") from None
        if response.status_code in (200, 204):
            return
        if response.status_code in (401, 403, 404):
            raise HTTPException(503, "Exclusão não confirmada")
        raise HTTPException(503, "Exclusão não confirmada")
