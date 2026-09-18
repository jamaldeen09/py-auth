import datetime

from typing import (
    Any,
    Dict,
    Literal,
    Protocol,
    TypedDict,
    runtime_checkable,
)
from pydantic import BaseModel, ConfigDict, field_validator
from .exceptions import ConfigurationError

class AuthError(TypedDict, total=False):
    code: str
    status_code: int
    message: str
    details: Dict[str, Any]

class AuthResult(TypedDict, total=False):
    data: Any | None
    error: AuthError | None

class CookieOptionsInput(BaseModel):
    http_only: bool | None = None
    secure: bool | None = None
    same_site: Literal["lax", "strict", "none"] | None = None
    path: str | None = None
    domain: str | None = None
    max_age: int | None = None
    expires: datetime.datetime | None = None

class CookieOptions(BaseModel):
    http_only: bool
    secure: bool
    same_site: Literal["lax", "strict", "none"]
    path: str
    domain: str | None = None
    max_age: int
    expires: datetime.datetime | None = None

class CookieConfigInput(BaseModel):
    name: str | None = None
    options: CookieOptionsInput | None = None

class CookieConfig(BaseModel):
    name: str
    options: CookieOptions

class PyAuthCookiesInput(BaseModel):
    session_token: CookieConfigInput | None = None
    csrf_token: CookieConfigInput | None  = None
    state: CookieConfigInput | None  = None
    pkce_code_verifier: CookieConfigInput | None = None
    nonce: CookieConfigInput | None  = None

class PyAuthCookies(BaseModel):
    session_token: CookieConfig
    csrf_token: CookieConfig
    state: CookieConfig
    pkce_code_verifier: CookieConfig
    nonce: CookieConfig

@runtime_checkable
class PyAuthAdapterProtocol(Protocol):
    """Defines the strict structural contract that any py-auth adapter must implement."""

    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any] | None:...
    async def get_user_by_emai(self, email: str) -> Dict[str, Any] | None:...
    async def get_or_create_user_and_link_account (
        self, 
        email: str, 
        user_data: Dict[str, Any],
        account_data: Dict[str, Any]
    ) -> Dict[str, Any] | None:...

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any] | None: ...
    async def get_session_by_session_token_hash(self, session_token_hash: str) -> Dict[str, Any] | None: ...
    async def delete_session_by_session_token_hash(self, session_token_hash: str) -> None: ...
    async def delete_session(self, session_id: str) -> None: ...
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any] | None: ...


class AdapterContainer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    adapter: Any

    @field_validator("adapter", mode="before")
    @classmethod
    def validate_adapter_interface(cls, v: Any) -> Any:
        if not isinstance(v, PyAuthAdapterProtocol):
            raise ConfigurationError(
                "The provided adapter is missing required methods or attributes defined in 'PyAuthAdapterProtocol'."
            )

        return v


__all__ = [
    "AuthError",
    "AuthResult",
    "CookieOptions",
    "CookieConfig",
    "CookieConfigInput",
    "CookieOptionsInput",
    "PyAuthCookiesInput",
    "PyAuthAdapterProtocol",
    "AdapterContainer",
    "PyAuthCookies"
]
