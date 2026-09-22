import pytest

from py_auth import ForeignKeyViolationError, DuplicateEntryError

@pytest.mark.asyncio
async def test_link_account_foreign_key_violation(account_data, adapter):
    """Verify that linking an account to a non-existent user ID raises ForeignKeyViolationError."""
    with pytest.raises(ForeignKeyViolationError):
        await adapter.link_account(account_data(user_id="does-not-exist"))

@pytest.mark.asyncio
async def test_link_account(user_data, account_data, adapter):
    """Verify that an OAuth provider account is linked and persisted with all attributes."""
    created_user = await adapter.create_user(user_data())

    account_data_dict = account_data(user_id=created_user["id"])
    account = await adapter.link_account(account_data_dict)

    assert account is not None
    assert account["id"] == account_data_dict["id"]
    assert account["user_id"] == created_user["id"]
    assert account["type"] == account_data_dict["type"]
    assert account["provider"] == account_data_dict["provider"]
    assert account["provider_account_id"] == account_data_dict["provider_account_id"]
    assert account["access_token"] == account_data_dict["access_token"]
    assert account["refresh_token"] == account_data_dict["refresh_token"]
    assert account["expires_at"] == account_data_dict["expires_at"]
    assert account["token_type"] == account_data_dict["token_type"]
    assert account["scope"] == account_data_dict["scope"]
    assert account["id_token"] == account_data_dict["id_token"]
    assert account["session_state"] == account_data_dict["session_state"]

@pytest.mark.asyncio
async def test_link_account_duplicate_entry_error(user_data, account_data, adapter):
    """Verify that linking the exact same account twice raises DuplicateEntryError."""
    user = await adapter.create_user(user_data())
    account_payload = account_data(user_id=user["id"])
    await adapter.link_account(account_payload)

    with pytest.raises(DuplicateEntryError):
        await adapter.link_account(account_payload)

@pytest.mark.asyncio
async def test_link_same_provider_account_to_different_user_duplicate_error(user_data, account_data, adapter):
    """Verify that an OAuth account cannot be simultaneously linked to two different user accounts."""
    user1 = await adapter.create_user(user_data(id="usr_1", email="user1@example.com"))
    user2 = await adapter.create_user(user_data(id="usr_2", email="user2@example.com"))

    await adapter.link_account(
        account_data(id="acc_1", user_id=user1["id"], provider="google", provider_account_id="google_123")
    )

    with pytest.raises(DuplicateEntryError):
        await adapter.link_account(
            account_data(id="acc_2", user_id=user2["id"], provider="google", provider_account_id="google_123")
        )

@pytest.mark.asyncio
async def test_list_accounts_for_user(user_data, account_data, adapter):
    """Verify that all linked accounts for a specific user ID are retrieved."""
    user = await adapter.create_user(user_data())
    await adapter.link_account(account_data(user_id=user["id"]))

    accounts = await adapter.list_accounts_for_user(user["id"])

    assert accounts is not None
    assert len(accounts) == 1
    assert accounts[0]["user_id"] == user["id"]

@pytest.mark.asyncio
async def test_list_accounts_for_user_multiple(user_data, account_data, adapter):
    """Verify that multiple linked OAuth accounts (e.g. Google and GitHub) are returned for a user."""
    user = await adapter.create_user(user_data())

    await adapter.link_account(account_data(id="acc_google", user_id=user["id"], provider="google", provider_account_id="google_1"))
    await adapter.link_account(account_data(id="acc_github", user_id=user["id"], provider="github", provider_account_id="github_1"))

    accounts = await adapter.list_accounts_for_user(user["id"])
    assert accounts is not None
    assert len(accounts) == 2
    providers = {acc["provider"] for acc in accounts}
    assert providers == {"google", "github"}

@pytest.mark.asyncio
async def test_list_accounts_for_user_empty(adapter):
    """Verify that querying accounts for a user with no linked providers returns an empty list."""
    accounts = await adapter.list_accounts_for_user("non-existent-user-id")
    assert accounts == []

@pytest.mark.asyncio
async def test_unlink_account(user_data, account_data, adapter):
    """Verify that unlinking an account deletes it from the database."""
    user = await adapter.create_user(user_data())
    account = await adapter.link_account(account_data(user_id=user["id"]))

    await adapter.unlink_account(
        provider=account["provider"],
        provider_account_id=account["provider_account_id"],
    )

    remaining_accounts = await adapter.list_accounts_for_user(user["id"])
    assert remaining_accounts == []

@pytest.mark.asyncio
async def test_unlink_account_when_multiple_linked(user_data, account_data, adapter):
    """Verify that unlinking one provider leaves other linked providers intact for that user."""
    user = await adapter.create_user(user_data())
    await adapter.link_account(account_data(id="acc_google", user_id=user["id"], provider="google", provider_account_id="google_1"))
    await adapter.link_account(account_data(id="acc_github", user_id=user["id"], provider="github", provider_account_id="github_1"))

    await adapter.unlink_account(provider="google", provider_account_id="google_1")

    accounts = await adapter.list_accounts_for_user(user["id"])
    assert len(accounts) == 1
    assert accounts[0]["provider"] == "github"

@pytest.mark.asyncio
async def test_unlink_account_not_found(adapter):
    """Verify that unlinking an account that does not exist completes safely without error."""
    await adapter.unlink_account(provider="nonexistent", provider_account_id="nobody")
