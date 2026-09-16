"""Shared fixtures for the py-auth test suite."""

from __future__ import annotations

from typing import Any, Dict


class FakeAdapter:
    """In-memory adapter implementing the PyAuthAdapterProtocol.

    Sessions are stored keyed by session id in ``self.sessions``.
    """

    def __init__(self) -> None:
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._next_id: int = 1
        self.deleted_by_hash: list[str] = []

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any] | None:
        session_id = str(self._next_id)
        self._next_id += 1
        record = {"id": session_id, **session_data}
        self.sessions[session_id] = record
        return dict(record)

    async def get_session_by_session_token_hash(
        self, session_token_hash: str
    ) -> Dict[str, Any] | None:
        for record in self.sessions.values():
            if record["session_token_hash"] == session_token_hash:
                return dict(record)
        return None

    async def delete_session_by_session_token_hash(self, session_token_hash: str) -> None:
        self.deleted_by_hash.append(session_token_hash)
        for session_id, record in list(self.sessions.items()):
            if record["session_token_hash"] == session_token_hash:
                del self.sessions[session_id]

    async def delete_session(self, session_id: str) -> None:
        if session_id not in self.sessions:
            from py_auth.exceptions import RecordNotFoundError

            raise RecordNotFoundError("Session not found.")
        del self.sessions[session_id]

    async def update_session(
        self, session_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any] | None:
        record = self.sessions.get(session_id)
        if record is None:
            return None
        record.update({k: v for k, v in updates.items() if k != "id"})
        return dict(record)


class CollisionAdapter(FakeAdapter):
    """FakeAdapter that raises DuplicateEntryError on the first N session creates."""

    def __init__(self, num_collisions: int = 1) -> None:
        super().__init__()
        self.num_collisions = num_collisions
        self.create_calls = 0

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any] | None:
        self.create_calls += 1
        if self.create_calls <= self.num_collisions:
            from py_auth.exceptions import DuplicateEntryError

            raise DuplicateEntryError("duplicate key value violates unique constraint")
        return await super().create_session(session_data)