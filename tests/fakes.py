from contextlib import contextmanager
from copy import deepcopy
from threading import RLock
from uuid import uuid4


class MemoryRepository:
    """Test-only repository. Never imported by app code."""
    def __init__(self):
        self.rows = {}
        self.calendar_rows = []
        self.lock = RLock()

    @contextmanager
    def transaction(self, user_id):
        with self.lock:
            before = deepcopy(self.rows)
            try:
                yield
            except Exception:
                self.rows = before
                raise

    def list(self, entity, user_id):
        return deepcopy([r for r in self.rows.get(entity, {}).values() if r['usuario_id'] == user_id])

    def get(self, entity, record_id, user_id):
        row = self.rows.get(entity, {}).get(record_id)
        return deepcopy(row) if row and row['usuario_id'] == user_id else None

    def create(self, entity, values, user_id):
        row = dict(deepcopy(values), id=str(uuid4()), usuario_id=user_id)
        self.rows.setdefault(entity, {})[row['id']] = row
        return deepcopy(row)

    def update(self, entity, record_id, values, user_id):
        assert self.get(entity, record_id, user_id)
        row = dict(deepcopy(values), id=record_id, usuario_id=user_id)
        self.rows[entity][record_id] = row
        return deepcopy(row)

    def delete(self, entity, record_id, user_id):
        assert self.get(entity, record_id, user_id)
        del self.rows[entity][record_id]

    def calendar(self):
        return deepcopy(self.calendar_rows)
