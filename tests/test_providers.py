"""Tests for py_auth.providers.credentials — CredentialsProvider."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import BaseModel, Field

from py_auth.providers.credentials import CredentialsProvider


class LoginBody(BaseModel):
    email: str
    password: str = Field(min_length=3)


async def async_authorize(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    if payload["password"] == "secret":
        return {"id": "user-1", "email": payload["email"]}
    return None


def sync_authorize(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    return async_authorize.__wrapped__(payload) if False else (
        {"id": "user-1", "email": payload["email"]}
        if payload["password"] == "secret"
        else None
    )


async def test_provider_id_derived_from_class_name() -> None:
    provider = CredentialsProvider(model=LoginBody, authorize=async_authorize)
    assert provider.id == "credentials"


async def test_async_authorize_success() -> None:
    provider = CredentialsProvider(model=LoginBody, authorize=async_authorize)
    result = await provider.handle_request({"email": "a@b.io", "password": "secret"})
    assert result["error"] is None
    assert result["data"] == {"id": "user-1", "email": "a@b.io"}


async def test_sync_authorize_success() -> None:
    provider = CredentialsProvider(model=LoginBody, authorize=sync_authorize)
    result = await provider.handle_request({"email": "a@b.io", "password": "secret"})
    assert result["error"] is None
    assert result["data"]["id"] == "user-1"


async def test_authorize_rejection_returns_credentials_error() -> None:
    provider = CredentialsProvider(model=LoginBody, authorize=async_authorize)
    result = await provider.handle_request({"email": "a@b.io", "password": "wrong"})
    assert result["data"] is None
    assert result["error"]["code"] == "CredentialsSignIn"
    assert result["error"]["status_code"] == 401
    assert result["error"]["message"] == "Invalid email or password."


async def test_validation_error_shape() -> None:
    provider = CredentialsProvider(model=LoginBody, authorize=async_authorize)
    result = await provider.handle_request({"email": "a@b.io"})
    error = result["error"]
    assert error["code"] == "ValidationError"
    assert error["status_code"] == 422
    details = error["details"]["validation_errors"]
    fields = {entry["field"] for entry in details}
    assert "password" in fields
    for entry in details:
        assert isinstance(entry["errors"], list) and entry["errors"]


async def test_authorize_exception_maps_to_internal_error(caplog: pytest.LogCaptureFixture) -> None:
    async def exploding(payload: Dict[str, Any]) -> Dict[str, Any] | None:
        raise RuntimeError("boom")

    provider = CredentialsProvider(model=LoginBody, authorize=exploding)
    result = await provider.handle_request({"email": "a@b.io", "password": "secret"})
    assert result["data"] is None
    assert result["error"]["code"] == "InternalServerError"
    assert result["error"]["status_code"] == 500


async def test_extra_fields_are_ignored() -> None:
    # pydantic v2 ignores unknown fields unless model_config forbids them;
    # the request still succeeds.
    provider = CredentialsProvider(model=LoginBody, authorize=async_authorize)
    result = await provider.handle_request(
        {"email": "a@b.io", "password": "secret", "admin": True}
    )
    assert result["error"] is None
    assert result["data"]["id"] == "user-1"