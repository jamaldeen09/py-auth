import hmac

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .exceptions import DuplicateEntryError, AdapterError
from .utils import generate_token, hash_token, merge_cookie_config, get_logger
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
        self.cookies = merge_cookie_config(user_config=cookies)
        self._provider_map = {getattr(p, "id", None): p for p in providers}

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
            "data": {"session_token": session_token,"csrf_token": csrf_token,"user": user},
            "error": None,
        }

    async def verify_session(self, session_token: str, csrf_token: str) -> AuthResult:
        """Verify an active session and ensure CSRF token validity."""
        session_token_hash = hash_token(session_token)
        session = await self.adapter.get_session_by_session_token_hash(session_token_hash)

        if not session:
            return self.get_auth_result(
                error={
                    "code": "InvalidSessionToken",
                    "status_code": 401,
                    "message": "Session token not found or invalid.",
                }
            )

        expires = session.get("expires")
        now = datetime.now(timezone.utc)
        if not isinstance(expires, datetime):
            return self.get_auth_result(
                error={
                    "code": "InvalidSessionData",
                    "status_code": 401,
                    "message": "Session expiration format is invalid.",
                }
            )

        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if expires <= now:
            await self.adapter.delete_session_by_session_token_hash(session_token_hash)
            return self.get_auth_result(
                error={
                    "code": "SessionExpired",
                    "status_code": 401,
                    "message": "Session has expired. Sign in again to continue.",
                },
            )

        db_csrf_token = session.get("csrf_token")
        if not db_csrf_token or not hmac.compare_digest(db_csrf_token, csrf_token):
            return self.get_auth_result(
                error={
                    "code": "InvalidCsrfToken",
                    "status_code": 403,
                    "message": "CSRF token validation failed.",
                }
            )

        return self.get_auth_result(data={"session": session})

    async def signout(self, session_id: str) -> AuthResult:
      await self.adapter.delete_session_by_id(session_id)
      return self.get_auth_result(data={"signed_out": True})

    async def signin_with_credentials(self, request_body: Dict[str, Any]) -> AuthResult:
        """Authenticate user credentials, create a session, and return session tokens."""
        credentials_provider = self._provider_map.get("credentials")

        if not credentials_provider:
          return self.get_auth_result(error={
            "code": "ConfigurationError",
            "status_code": 500,
            "message": "Credentials provider is not configured."
          })

        result = await credentials_provider.handle_request(request_body)
        error = result["error"]
        user_data = result["data"]

        if error:
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
            
            except AdapterError as e:
                get_logger().exception("Database adapter error occurred while creating session.")
                status_code = getattr(e, "status_code", 500)
                return self.get_auth_result(
                    error={
                        "code": "AdapterError",
                        "status_code": status_code,
                        "message": str(e) or "A database error occurred while creating your session. Please try again."
                    }
                )

            except Exception as e:
                get_logger().exception("Unexpected error occurred during session creation.")
                status_code = getattr(e, "status_code", 500)
                return self.get_auth_result(
                    error={
                        "code": "InternalServerError",
                        "status_code": status_code,
                        "message": "An internal server error occurred."
                    }
                )

        if not created_session:
            return self.get_auth_result(
                error={
                    "code": "SessionCreationFailed",
                    "status_code": 500,
                    "message": "Failed to create session after multiple attempts. Please try again."
                }
            )

        return self.get_signin_with_credentials_result(
            session_token=session_token, csrf_token=csrf_token, user=user_data
        )
