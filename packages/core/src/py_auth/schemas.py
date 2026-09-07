import datetime

from typing import (
    Any,
    Callable,
    Dict,
    Literal,
    Optional,
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
    details: Optional[Dict[str, Any]]

class AuthResult(TypedDict):
    data: Optional[Any]
    error: Optional[AuthError]

class CookieOptions(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    http_only: Optional[bool] = None
    secure: Optional[bool] = None
    same_site: Optional[Literal["lax", "strict", "none"]] = None
    path: Optional[str] = None
    domain: Optional[str] = None
    max_age: Optional[int] = None
    expires: Optional[datetime.datetime] = None
    encode: Optional[Callable[[str], str]] = None

class CookieConfig(BaseModel):
    name: Optional[str] = None
    options: Optional[CookieOptions] = None

class PyAuthCookiesInput(BaseModel):
    session_token: Optional[CookieConfig] = None
    csrf_token: Optional[CookieConfig] = None

@runtime_checkable
class PyAuthAdapterProtocol(Protocol):
    """Defines the strict structural contract that any py-auth adapter must implement."""

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]: ...
    async def get_session_by_session_token_hash(self, session_token_hash: str) -> Optional[Dict[str, Any]]: ...
    async def delete_session_by_session_token_hash(self, session_token_hash: str) -> None: ...
    async def delete_session_by_id(self, session_id: str) -> None: ...

class AdapterContainer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    adapter: Any

    @field_validator("adapter", mode="before")
    @classmethod
    def validate_adapter_interface(cls, v: Any) -> Any:
        if not isinstance(v, PyAuthAdapterProtocol):
            raise ConfigurationError("The provided adapter is missing required methods or attributes defined in 'PyAuthAdapterProtocol'.")
        
        return v

__all__ = [
    "AuthError",
    "AuthResult",
    "CookieOptions",
    "CookieConfig",
    "PyAuthCookiesInput",
    "PyAuthAdapterProtocol",
    "AdapterContainer",
]
