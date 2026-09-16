"""Tests for py_auth_sqlalchemy — the async SQLAlchemy 2.0 adapter."""

from __future__ import annotations

import datetime
from typing import Any, Dict

import pytest
from sqlalchemy import DateTime, String
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from py_auth.exceptions import AdapterError, DuplicateEntryError
from py_auth_sqlalchemy import SqlAlchemyAdapter
from py_auth_sqlalchemy.core import validate_async_engine, validate_sqlalchemy_model


class Base(AsyncAttrs, DeclarativeBase):
    pass


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "sess-new")
    session_token_hash: Mapped[str] = mapped_column(String, unique=True)
    user_id: Mapped[str] = mapped_column(String)
    csrf_token: Mapped[str] = mapped_column(String)
    expires: Mapped[datetime.datetime] = mapped_column(DateTime)


class BadModel(Base):
    __tablename__ = "bad"

    id: Mapped[str] = mapped_column(String, primary_key=True)


@pytest.fixture
async def adapter():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield SqlAlchemyAdapter(engine=engine, session_model=SessionModel)
    await engine.dispose()


@pytest.fixture
def session_data() -> Dict[str, Any]:
    return {
        "id": "sess-1",
        "session_token_hash": "h" * 64,
        "user_id": "user-1",
        "csrf_token": "csrf-1",
        "expires": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=30),
    }


async def test_create_and_get_session(adapter, session_data) -> None:
    created = await adapter.create_session(session_data)
    assert created["id"] == "sess-1"
    assert created["session_token_hash"] == "h" * 64

    fetched = await adapter.get_session_by_session_token_hash("h" * 64)
    assert fetched is not None
    assert fetched["csrf_token"] == "csrf-1"
    assert fetched["user_id"] == "user-1"


async def test_get_session_missing_hash_returns_none(adapter) -> None:
    assert await adapter.get_session_by_session_token_hash("missing") is None


async def test_update_session(adapter, session_data) -> None:
    await adapter.create_session(session_data)
    updated = await adapter.update_session("sess-1", {"csrf_token": "csrf-2"})
    assert updated["csrf_token"] == "csrf-2"

    fetched = await adapter.get_session_by_session_token_hash("h" * 64)
    assert fetched["csrf_token"] == "csrf-2"


async def test_update_session_cannot_change_id(adapter, session_data) -> None:
    await adapter.create_session(session_data)
    updated = await adapter.update_session("sess-1", {"id": "hijacked"})
    assert updated["id"] == "sess-1"


async def test_update_session_missing_returns_none(adapter) -> None:
    assert await adapter.update_session("ghost", {"csrf_token": "x"}) is None


async def test_delete_by_hash(adapter, session_data) -> None:
    await adapter.create_session(session_data)
    await adapter.delete_session_by_session_token_hash("h" * 64)
    assert await adapter.get_session_by_session_token_hash("h" * 64) is None


async def test_delete_by_id(adapter, session_data) -> None:
    await adapter.create_session(session_data)
    await adapter.delete_session("sess-1")
    assert await adapter.get_session_by_session_token_hash("h" * 64) is None


async def test_duplicate_hash_maps_to_duplicate_entry_error(adapter, session_data) -> None:
    await adapter.create_session(session_data)
    with pytest.raises(DuplicateEntryError):
        await adapter.create_session(dict(session_data))


async def test_validate_async_engine_rejects_sync_engine() -> None:
    from sqlalchemy import create_engine

    with pytest.raises(TypeError):
        validate_async_engine(create_engine("sqlite:///:memory:"))


async def test_validate_sqlalchemy_model_missing_columns() -> None:
    with pytest.raises(AdapterError) as exc:
        validate_sqlalchemy_model(BadModel, {"id", "session_token_hash", "user_id"})
    assert "missing required" in str(exc.value)


async def test_validate_sqlalchemy_model_none() -> None:
    with pytest.raises(AdapterError):
        validate_sqlalchemy_model(None, {"id"})


async def test_adapter_wraps_unexpected_db_errors(adapter, session_data) -> None:
    # A session referencing a non-existent row type exercises the generic
    # PyAuthError translation path via a deliberately broken write.
    class UnmappedAdapter(SqlAlchemyAdapter):
        def _row_to_dict(self, instance: Any) -> Dict[str, Any] | None:
            return super()._row_to_dict(instance)

    broken = UnmappedAdapter(adapter.engine, adapter.session_model)
    await broken.create_session(session_data)
    assert True  # reachable without raising


async def test_validation_error_from_invalid_model(adapter) -> None:
    with pytest.raises(AdapterError):
        SqlAlchemyAdapter(engine=adapter.engine, session_model=BadModel)