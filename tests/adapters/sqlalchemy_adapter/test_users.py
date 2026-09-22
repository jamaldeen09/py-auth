import pytest

from py_auth import DuplicateEntryError

@pytest.mark.asyncio
async def test_create_user(user_data, adapter):
    """Verify that a user record is persisted with all provided fields."""
    user_data_dict = user_data()
    user = await adapter.create_user(user_data_dict)

    assert user is not None
    assert user["id"] == user_data_dict["id"]
    assert user["email"] == user_data_dict["email"]
    assert user["name"] == user_data_dict["name"]    

@pytest.mark.asyncio
async def test_get_user(user_data, adapter):
    """Verify that an existing user can be retrieved by their primary key ID."""
    created_user = await adapter.create_user(user_data())
    user = await adapter.get_user(created_user["id"])

    assert user is not None
    assert user["id"] == created_user["id"]
    assert user["email"] == created_user["email"]
    assert user["name"] == created_user["name"]

@pytest.mark.asyncio
async def test_get_user_not_found(adapter):
    """Verify that querying a non-existent user ID returns None instead of raising an error."""
    user = await adapter.get_user("does-not-exist")
    assert user is None

@pytest.mark.asyncio
async def test_get_user_by_email(user_data, adapter):
    """Verify that an existing user can be looked up by their email address."""
    created_user = await adapter.create_user(user_data())
    user = await adapter.get_user_by_email(created_user["email"])
    
    assert user is not None
    assert user["id"] == created_user["id"]
    assert user["email"] == created_user["email"]

@pytest.mark.asyncio
async def test_get_user_by_email_not_found(adapter):
    """Verify that querying a non-existent email returns None gracefully."""
    user = await adapter.get_user_by_email("doesnotexist@example.com")
    assert user is None

@pytest.mark.asyncio
async def test_create_user_duplicate_email(user_data, adapter):
    """Verify that attempting to create a user with an existing email raises DuplicateEntryError."""
    created_user = await adapter.create_user(user_data())

    with pytest.raises(DuplicateEntryError):
        await adapter.create_user(created_user)

@pytest.mark.asyncio
async def test_update_user(user_data, adapter):
    """Verify that mutable user fields can be updated successfully."""
    created_user = await adapter.create_user(user_data())

    updates = {"name": "Update Test User", "image": "https://new-image"}
    user = await adapter.update_user(created_user["id"], updates)

    assert user is not None
    assert user["name"] == updates["name"]
    assert user["image"] == updates["image"]

@pytest.mark.asyncio
async def test_update_user_not_found(adapter):
    """Verify that attempting to update a non-existent user returns None."""
    user = await adapter.update_user("does-not-exist", {"name": "Nobody"})
    assert user is None

@pytest.mark.asyncio
async def test_update_user_cannot_modify_id(user_data, adapter):
    """Verify that the primary key ID cannot be modified via update_user."""
    created_user = await adapter.create_user(user_data())
    user = await adapter.update_user(created_user["id"], {"id": "hacked_id", "name": "New Name"})
    
    assert user is not None
    assert user["id"] == created_user["id"] 
    assert user["name"] == "New Name"

@pytest.mark.asyncio
async def test_update_user_duplicate_email(user_data, adapter):
    """Verify that updating a user's email to one already registered raises DuplicateEntryError."""
    user1 = await adapter.create_user(user_data(email="user1@example.com", id="usr_1"))
    user2 = await adapter.create_user(user_data(email="user2@example.com", id="usr_2"))

    with pytest.raises(DuplicateEntryError):
        await adapter.update_user(user2["id"], {"email": user1["email"]})

@pytest.mark.asyncio
async def test_delete_user(user_data, adapter):
    """Verify that delete_user removes the record from the database."""
    created_user = await adapter.create_user(user_data())
    await adapter.delete_user(created_user["id"])

    deleted = await adapter.get_user(created_user["id"])
    assert deleted is None

@pytest.mark.asyncio
async def test_delete_user_not_found(adapter):
    """Verify that attempting to delete a non-existent user completes safely without raising an error."""
    await adapter.delete_user("does-not-exist")

@pytest.mark.asyncio
async def test_delete_user_cascades_to_sessions_and_accounts(user_data, session_data, account_data, adapter):
    """Verify that deleting a user cascades and deletes all associated sessions and accounts."""
    user = await adapter.create_user(user_data())
    await adapter.create_session(session_data(user_id=user["id"]))
    await adapter.link_account(account_data(user_id=user["id"]))

    await adapter.delete_user(user["id"])

    sessions = await adapter.list_sessions_for_user(user["id"])
    accounts = await adapter.list_accounts_for_user(user["id"])
    assert sessions == []
    assert accounts == []
