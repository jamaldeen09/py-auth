"""Base provider class for authentication providers."""

from abc import ABC, abstractmethod
from typing import Any

from .schemas import AuthResult


class BaseProvider(ABC):
    """Abstract base class for all authentication providers."""

    id: str

    def __init__(self) -> None:
        self.id = self.__class__.__name__.lower().replace("provider", "")

    @abstractmethod
    async def authenticate(self, *args: Any, **kwargs: Any) -> AuthResult:
        """Authenticate a user using provider-specific authentication flow."""
        pass
