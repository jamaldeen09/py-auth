import pytest
from datetime import datetime, timezone, timedelta

from py_auth import ForeignKeyViolationError, DuplicateEntryError

@pytest.mark.asyncio
async def test_create_session_foreign_key_violation(session_data, adapter):
    """Verify that creating a session with a non-existent user ID raises ForeignKeyViolationError."""
    with pytest.raises(ForeignKeyViolationError):
        await adapter.create_session(session_data(user_id="does-not-exist"))

@pytest.mark.asyncio
async def test_create_session(user_data, session_data, adapter):
    """Verify that a session is persisted with expiration and token hash."""
    user = await adapter.create_user(user_data())

    session_payload = session_data(user_id=user["id"])
    session = await adapter.create_session(session_payload)

    assert session is not None
    assert session["id"] == session_payload["id"]
    assert session["expires"] == session_payload["expires"]
    assert session["user_id"] == user["id"]
    assert session["session_token_hash"] == session_payload["session_token_hash"]

@pytest.mark.asyncio
async def test_create_session_duplicate_entry_error(user_data, session_data, adapter):
    """Verify that creating a duplicate session record raises DuplicateEntryError."""
    user = await adapter.create_user(user_data())
    session_payload = session_data(user_id=user["id"])
    await adapter.create_session(session_payload)

    with pytest.raises(DuplicateEntryError):
        await adapter.create_session(session_payload)

@pytest.mark.asyncio
async def test_get_session_by_session_token_hash(user_data, session_data, adapter):
    """Verify that a session can be retrieved by its hashed session token."""
    user = await adapter.create_user(user_data())
    session_payload = session_data(user_id=user["id"])
    created_session = await adapter.create_session(session_payload)

    session = await adapter.get_session_by_session_token_hash(created_session["session_token_hash"])

    assert session is not None
    assert session["id"] == created_session["id"]
    assert session["user_id"] == user["id"]
    assert session["session_token_hash"] == created_session["session_token_hash"]

@pytest.mark.asyncio
async def test_get_session_by_session_token_hash_not_found(adapter):
    """Verify that querying a non-existent token hash returns None."""
    session = await adapter.get_session_by_session_token_hash("non-existent-token-hash")
    assert session is None

@pytest.mark.asyncio
async def test_list_sessions_for_user(user_data, session_data, adapter):
    """Verify that all active sessions for a user can be listed."""
    user = await adapter.create_user(user_data())
    await adapter.create_session(session_data(user_id=user["id"]))

    sessions = await adapter.list_sessions_for_user(user["id"])

    assert sessions is not None
    assert len(sessions) == 1
    assert sessions[0]["user_id"] == user["id"]

@pytest.mark.asyncio
async def test_list_sessions_for_user_multiple(user_data, session_data, adapter):
    """Verify that multiple active sessions across different devices are listed for a user."""
    user = await adapter.create_user(user_data())

    await adapter.create_session(session_data(id="sess_1", user_id=user["id"], session_token_hash="hash_device_1"))
    await adapter.create_session(session_data(id="sess_2", user_id=user["id"], session_token_hash="hash_device_2"))

    sessions = await adapter.list_sessions_for_user(user["id"])
    assert len(sessions) == 2

@pytest.mark.asyncio
async def test_list_sessions_for_user_empty(adapter):
    """Verify that querying sessions for a user with no active sessions returns an empty list."""
    sessions = await adapter.list_sessions_for_user("non-existent-user-id")
    assert sessions == []

@pytest.mark.asyncio
async def test_update_session(user_data, session_data, adapter):
    """Verify that session attributes (such as rotated token hashes) can be updated."""
    user = await adapter.create_user(user_data())
    created_session = await adapter.create_session(session_data(user_id=user["id"]))

    updates = {"session_token_hash": "new_refreshed_session_token_hash"}
    updated = await adapter.update_session(created_session["id"], updates)

    assert updated is not None
    assert updated["id"] == created_session["id"]
    assert updated["session_token_hash"] == updates["session_token_hash"]

@pytest.mark.asyncio
async def test_update_session_expires(user_data, session_data, adapter):
    """Verify that session expiration dates can be extended."""
    user = await adapter.create_user(user_data())
    created_session = await adapter.create_session(session_data(user_id=user["id"]))

    new_expires = datetime.now(timezone.utc) + timedelta(days=30)
    updated = await adapter.update_session(created_session["id"], {"expires": new_expires})

    print("UPDATED:", updated)
    print("NEW EXPIRES:", new_expires)
    assert updated is not None
    assert updated["expires"] == new_expires

@pytest.mark.asyncio
async def test_update_session_cannot_modify_id(user_data, session_data, adapter):
    """Verify that the primary key ID of a session cannot be altered via update_session."""
    user = await adapter.create_user(user_data())
    created_session = await adapter.create_session(session_data(user_id=user["id"]))

    updated = await adapter.update_session(
        created_session["id"],
        {"id": "tampered_session_id", "session_token_hash": "valid_new_hash"}
    )
    assert updated["id"] == created_session["id"]

@pytest.mark.asyncio
async def test_update_session_not_found(adapter):
    """Verify that attempting to update a non-existent session returns None."""
    updated = await adapter.update_session("non-existent-id", {"session_token_hash": "abc"})
    assert updated is None

@pytest.mark.asyncio
async def test_delete_session(user_data, session_data, adapter):
    """Verify that delete_session removes the session record by ID."""
    user = await adapter.create_user(user_data())
    created_session = await adapter.create_session(session_data(user_id=user["id"]))

    await adapter.delete_session(created_session["id"])

    fetched = await adapter.get_session_by_session_token_hash(created_session["session_token_hash"])
    assert fetched is None

@pytest.mark.asyncio
async def test_delete_session_not_found(adapter):
    """Verify that deleting a non-existent session ID executes safely without error."""
    await adapter.delete_session("does-not-exist")

@pytest.mark.asyncio
async def test_delete_session_by_session_token_hash(user_data, session_data, adapter):
    """Verify that a session can be deleted using its hashed session token."""
    user = await adapter.create_user(user_data())
    created_session = await adapter.create_session(session_data(user_id=user["id"]))

    await adapter.delete_session_by_session_token_hash(created_session["session_token_hash"])

    fetched = await adapter.get_session_by_session_token_hash(created_session["session_token_hash"])
    assert fetched is None

@pytest.mark.asyncio
async def test_delete_session_by_session_token_hash_not_found(adapter):
    """Verify that deleting by an invalid or non-existent token hash completes safely."""
    await adapter.delete_session_by_session_token_hash("non-existent-token-hash")