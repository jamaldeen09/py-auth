import pytest

from py_auth import DuplicateEntryError

@pytest.mark.asyncio
async def test_get_or_create_user_and_link_account_new_user(user_data, account_data, adapter):
    """Verify that when a user does not exist, a new user is created and the account is linked."""
    user_payload = user_data()
    account_payload = account_data()

    result = await adapter.get_or_create_user_and_link_account(
        user_payload["email"], user_payload, account_payload
    )

    assert result is not None
    user = result["user"]
    account = result["account"]

    assert user is not None
    assert user["id"] == user_payload["id"]
    assert user["email"] == user_payload["email"]
    assert user["name"] == user_payload["name"]

    assert account is not None
    assert account["id"] == account_payload["id"]
    assert account["user_id"] == user["id"]
    assert account["provider"] == account_payload["provider"]
    assert account["provider_account_id"] == account_payload["provider_account_id"]

@pytest.mark.asyncio
async def test_get_or_create_user_and_link_account_existing_user(user_data, account_data, adapter):
    """Verify that when a user already exists, the account is linked to the existing user without duplicating."""
    existing_user = await adapter.create_user(user_data(email="existing@example.com", name="Existing User"))

    oauth_user_payload = user_data(email="existing@example.com", name="OAuth Google Name")
    account_payload = account_data(id="acc_oauth_1", provider="google", provider_account_id="google_user_1")

    result = await adapter.get_or_create_user_and_link_account(
        existing_user["email"], oauth_user_payload, account_payload
    )

    assert result is not None
    user = result["user"]
    account = result["account"]

    assert user["id"] == existing_user["id"]
    assert user["email"] == existing_user["email"]
    assert account["user_id"] == existing_user["id"]
    assert account["provider"] == "google"

@pytest.mark.asyncio
async def test_get_or_create_user_and_link_account_multiple_providers(user_data, account_data, adapter):
    """Verify that an existing user can link multiple OAuth providers using get_or_create."""
    user_payload = user_data()

    google_account = account_data(id="acc_google", provider="google", provider_account_id="google_123")
    res1 = await adapter.get_or_create_user_and_link_account(
        user_payload["email"], user_payload, google_account
    )
    user_id = res1["user"]["id"]

    github_account = account_data(id="acc_github", provider="github", provider_account_id="github_456")
    res2 = await adapter.get_or_create_user_and_link_account(
        user_payload["email"], user_payload, github_account
    )

    assert res2["user"]["id"] == user_id

    linked_accounts = await adapter.list_accounts_for_user(user_id)
    assert len(linked_accounts) == 2
    providers = {acc["provider"] for acc in linked_accounts}
    assert providers == {"google", "github"}
