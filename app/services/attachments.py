from pathlib import PurePosixPath

from app.core.config import settings
from app.core.errors import DomainError


def validate_attachment(name: str, content: bytes) -> None:
    if not name.strip() or len(name) > 500 or '/' in name or '\\' in name or '\x00' in name:
        raise DomainError(422, 'Nome de arquivo inválido.')
    if not content:
        raise DomainError(422, 'Arquivo vazio.')
    if len(content) > settings.attachment_max_bytes:
        raise DomainError(413, 'Arquivo excede o limite configurado.')
    suffix = PurePosixPath(name).suffix.lower()
    valid = (
        suffix == '.pdf' and content.startswith(b'%PDF-')
        or suffix == '.png' and content.startswith(b'\x89PNG\r\n\x1a\n')
        or suffix in {'.jpg', '.jpeg'} and content.startswith(b'\xff\xd8\xff')
        or suffix == '.gif' and content[:6] in {b'GIF87a', b'GIF89a'}
        or suffix == '.webp' and content.startswith(b'RIFF') and content[8:12] == b'WEBP'
    )
    if not valid:
        raise DomainError(415, 'Formato não aceito: PDF, PNG, JPEG, GIF ou WebP.')
    # Signature checking is an early filter, not malware scanning or full decoding.
