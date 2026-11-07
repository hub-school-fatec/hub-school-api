from typing import BinaryIO, Protocol

from app.core.errors import DomainError
from app.schemas.planning import Attachment, Export, Group, Message, Reminder


class AccountGateway(Protocol):
    """Must cover Auth, database and Storage under an approved user-scoped flow."""
    def export(self, user_id: str) -> Export: ...
    def delete(self, user_id: str) -> None: ...


class AttachmentGateway(Protocol):
    """Validate note ownership, content signature, size and private bucket access.

    No public storage paths or unrestricted signed URLs. Adapter not implemented.
    """
    def list(self, user_id: str, note_id: str) -> list[Attachment]: ...
    def upload(self, user_id: str, note_id: str, name: str, content: BinaryIO) -> Attachment: ...
    def download(self, user_id: str, attachment_id: str) -> BinaryIO: ...


class NotificationGateway(Protocol):
    """Requires approved scheduler identity, recipient lookup and idempotent delivery."""
    def schedule(self, user_id: str, reminders: list[Reminder]) -> None: ...
    def attendance_alert(self, user_id: str, subject_id: str, level: str) -> None: ...


class ChatGateway(Protocol):
    """All operations require verified group membership, including subscriptions.

    Invite expiry/revocation, roles and realtime transport are still undefined.
    """
    def create_group(self, user_id: str, name: str) -> Group: ...
    def join(self, user_id: str, invite_code: str) -> Group: ...
    def messages(self, user_id: str, group_id: str) -> list[Message]: ...
    def send(self, user_id: str, group_id: str, text: str) -> Message: ...


def get_account_gateway() -> AccountGateway:
    raise DomainError(503, 'Integração de conta, exportação e exclusão indisponível.')


def get_attachment_gateway() -> AttachmentGateway:
    raise DomainError(503, 'Integração com Storage indisponível.')
