import re
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile

from app.dependencies.identity import AuthenticatedIdentity
from app.repositories.anexos import AnexoRepository
from app.repositories.storage import MAX_BYTES, StorageClient
from app.schemas.anexo import AnexoOut


_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\Z")


def _safe_name(name: str | None) -> str:
    if not name or not _NAME.fullmatch(name) or ".." in name:
        raise HTTPException(422, "Nome de arquivo inválido")
    return name


def _valid_content(mime: str, data: bytes) -> bool:
    signatures = {
        "application/pdf": data.startswith(b"%PDF-"),
        "image/jpeg": data.startswith(b"\xff\xd8\xff"),
        "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/gif": data.startswith((b"GIF87a", b"GIF89a")),
        "image/webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP",
        "image/avif": data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis"),
    }
    return signatures.get(mime, False)


class AnexoService:
    def __init__(self, repository: AnexoRepository, storage: StorageClient,
                 identity: AuthenticatedIdentity):
        self.repository = repository
        self.storage = storage
        self.identity = identity

    def _check_path(self, record: AnexoOut) -> str:
        try:
            name = _safe_name(record.nome_arquivo)
        except HTTPException:
            raise HTTPException(503, "Metadados do anexo inválidos") from None
        expected = f"{self.identity.user_id}/{record.anotacao_id}/{record.id}/{name}"
        if record.caminho_storage != expected:
            raise HTTPException(503, "Metadados do anexo inválidos")
        return expected

    def list(self, note_id: UUID | None) -> list[AnexoOut]:
        records = self.repository.list(note_id)
        for record in records:
            self._check_path(record)
        return records

    def get(self, attachment_id: UUID) -> AnexoOut:
        record = self.repository.get(attachment_id)
        self._check_path(record)
        return record

    def upload(self, note_id: UUID, file: UploadFile) -> AnexoOut:
        self.repository.note_exists(note_id)
        name = _safe_name(file.filename)
        mime = file.content_type or ""
        data = bytearray()
        while chunk := file.file.read(65536):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise HTTPException(422, "Arquivo acima do limite")
        if not data:
            raise HTTPException(422, "Arquivo vazio")
        if not _valid_content(mime, data):
            raise HTTPException(422, "Tipo de arquivo inválido")
        attachment_id = uuid4()
        path = f"{self.identity.user_id}/{note_id}/{attachment_id}/{name}"
        self.storage.upload(path, bytes(data), mime, self.identity.access_token)
        try:
            record = self.repository.create({
                "id": str(attachment_id), "anotacao_id": str(note_id),
                "nome_arquivo": name, "caminho_storage": path,
                "tamanho_bytes": len(data), "tipo_mime": mime,
            })
        except HTTPException:
            try:
                self.storage.delete(path, self.identity.access_token)
            except HTTPException:
                raise HTTPException(503, "Falha nos metadados e na compensação") from None
            raise
        if record.id != attachment_id or record.caminho_storage != path:
            raise HTTPException(503, "Metadados do anexo inválidos")
        return record

    def download(self, attachment_id: UUID) -> tuple[AnexoOut, bytes]:
        record = self.get(attachment_id)
        data = self.storage.download(record.caminho_storage, self.identity.access_token)
        if len(data) != record.tamanho_bytes:
            raise HTTPException(503, "Arquivo inconsistente")
        return record, data

    def delete(self, attachment_id: UUID) -> None:
        record = self.get(attachment_id)
        self.storage.delete(record.caminho_storage, self.identity.access_token)
        try:
            self.repository.delete(attachment_id)
        except HTTPException:
            raise HTTPException(503, "Exclusão parcial; metadados podem permanecer") from None
