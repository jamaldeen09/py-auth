from enum import Enum
from typing import Any

class PyAuthStrategy(Enum):
    JWT = "jwt"
    DATABASE = "database"

class ProviderAuthenticateError(dict):
    status_code: int
    message: str

class ProviderAuthenticateResult(dict):
    data: Any
    error: ProviderAuthenticateError

class HandleSignInWithCredentialsResult (dict):
    error: ProviderAuthenticateError
    token: str | None