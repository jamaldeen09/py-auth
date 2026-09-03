import hmac

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .exceptions import ConfigurationError, DuplicateEntryError
from .utils import generate_token, hash_token, merge_cookie_config
from .schemas import (
    AdapterContainer,
    AuthError,
    AuthResult,
    PyAuthCookiesInput,
)

class PyAuth:
    """Core py-auth authentication manager."""

    def __init__(
        self,
        adapter: Any,
        providers: Optional[List[Any]] = None,
        cookies: Optional[PyAuthCookiesInput] = None,
    ):
        container = AdapterContainer(adapter=adapter)
        self.adapter = container.adapter
        self.providers = providers or []
        self.cookies = merge_cookie_config(user_config=cookies)

    def get_auth_result(
        self,
        data: Optional[Any] = None,
        error: Optional[AuthError] = None,
    ) -> AuthResult:
        """Construct a standardized py-auth response."""
        return {"data": data, "error": error}

    def get_signin_with_credentials_result(
        self,
        session_token: str,
        csrf_token: str,
        user: Dict[str, Any],
    ) -> AuthResult:
        """Construct a standardized credentials sign-in success response."""
        return {
            "data": {
                "session_token": session_token,
                "csrf_token": csrf_token,
                "user": user,
            },
            "error": None,
        }

    async def verify_session(
        self, session_token: str, csrf_token: str
    ) -> AuthResult:
        """Verify an active session and ensure CSRF token validity."""
        session_token_hash = hash_token(session_token)
        session = await self.adapter.get_session_by_session_token_hash(session_token_hash)

        if not session:
            return self.get_auth_result(
                error={"status_code": 401, "message": "Unauthorized."}
            )

        expires = session.get("expires")
        now = datetime.now(timezone.utc)
        if not isinstance(expires, datetime):
            return self.get_auth_result(
                error={"status_code": 401, "message": "Invalid session."}
            )

        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if expires <= now:
            await self.adapter.delete_session_by_session_token_hash(session_token_hash)
            return self.get_auth_result(
                error={
                    "status_code": 401,
                    "message": "Session has expired. Sign in again to continue.",
                },
            )

        db_csrf_token = session.get("csrf_token")
        if not db_csrf_token or not hmac.compare_digest(db_csrf_token, csrf_token):
            return self.get_auth_result(
                error={"status_code": 403, "message": "Invalid CSRF token."}
            )

        return self.get_auth_result(data={"session": session})

    async def signout(self, session: Optional[Dict[str, Any]] = None) -> AuthResult:
      if session_id is None:
        if not session:
            return self.get_auth_result(error={"status_code": 400, "message": "No session provided"})
        session_id = session.get("id")
        if session_id is None:
            return self.get_auth_result(error={"status_code": 400, "message": "Malformed session"})
      await self.adapter.delete_session_by_id(session_id)
      return self.get_auth_result(data={"signed_out": True})

    async def signin_with_credentials(self, data: Dict[str, Any]) -> AuthResult:
        """Authenticate user credentials, create a session, and return session tokens."""
        credentials_provider = next(
            (provider for provider in self.providers if getattr(provider, "id", None) == "credentials"),
            None,
        )

        if not credentials_provider:
            raise ConfigurationError("Credentials provider is not configured.")

        result = await credentials_provider.authenticate(data=data)
        error_default = {"status_code": 401, "message": "Invalid credentials."}
        error = result.get("error", error_default)
        user_data = result.get("data", None)

        if error or not user_data:
            return self.get_auth_result(error=error)

        expires = datetime.now(timezone.utc) + timedelta(days=30)
        session_token = generate_token(num_bytes=48)
        csrf_token = generate_token(num_bytes=32)

        max_retries = 3
        created_session = None
        for _ in range(max_retries):
            session_token_hash = hash_token(session_token)
            try:
                created_session = await self.adapter.create_session(
                    {
                        "session_token_hash": session_token_hash,
                        "user_id": user_data.get("id", None),
                        "csrf_token": csrf_token,
                        "expires": expires,
                    }
                )
                break
            except DuplicateEntryError:
                session_token = generate_token(num_bytes=48)
            except Exception as e:
                print(e)
                status_code = getattr(e, "status_code", 500)
                return self.get_auth_result(
                    error={"status_code": status_code, "message": "Something went wrong."}
                )

        if not created_session:
            return self.get_auth_result(
                error={"status_code": 500, "message": "Failed to create session."}
            )

        return self.get_signin_with_credentials_result(
            session_token=session_token, csrf_token=csrf_token, user=user_data
        )
