import pytest

from datetime import datetime

@pytest.fixture
def user_data():
    def make_user_data(**overrides):
        data = {
            "id": "usr_test_1",
            "email": "testuser@example.com",
            "name": "Test User",
        }
        data.update(overrides)
        return data
    return make_user_data

@pytest.fixture
def account_data():
    def make_account(user_id: str | None = None, **overrides):
        data = {
            "id": "acc_test_1",
            "type": "oauth",
            "provider": "google",
            "provider_account_id": "google_user_1",
            "access_token": "access_token_1",
            "refresh_token": "refresh_token_1",
            "expires_at": 1893456000,
            "token_type": "Bearer",
            "scope": "openid email profile",
            "id_token": "id_token_1",
            "session_state": "session_1",
        }
        if user_id:
            data["user_id"] = user_id
        data.update(overrides)
        return data
    return make_account

@pytest.fixture
def session_data():
    def make_session(user_id: str | None = None, **overrides):
        data = {
            "id": "session_test_1",
            "session_token_hash": "session_token_hash_1",
            "expires": datetime.fromisoformat("2026-09-22T15:30:00+02:00"),
        }
        if user_id:
            data["user_id"] = user_id
        data.update(overrides)
        return data
    return make_session