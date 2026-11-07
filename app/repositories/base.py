from contextlib import AbstractContextManager
from typing import Any, Protocol

from app.core.errors import DomainError


Record = dict[str, Any]


class Repository(Protocol):
    """Adapter contract; never use a privileged connection to bypass RLS.

    Every private operation MUST be scoped to the validated JWT subject.
    Records returned MUST contain usuario_id, including indirectly owned rows.
    transaction() MUST provide atomicity AND serialize conflicting owner writes,
    including active semester and attendance uniqueness checks. Roll back errors.
    A production adapter must additionally preserve the end user's JWT for RLS.
    """

    def transaction(self, user_id: str) -> AbstractContextManager[None]: ...
    def list(self, entity: str, user_id: str) -> list[Record]: ...
    def get(self, entity: str, record_id: str, user_id: str) -> Record | None: ...
    def create(self, entity: str, values: Record, user_id: str) -> Record: ...
    def update(self, entity: str, record_id: str, values: Record, user_id: str) -> Record: ...
    def delete(self, entity: str, record_id: str, user_id: str) -> None: ...
    def calendar(self) -> list[Record]: ...


def get_repository() -> Repository:
    raise DomainError(503, 'Persistência não integrada. Operação indisponível.')
