

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from .exceptions import (
    DuplicateEntryError,
    ForeignKeyViolationError,
    RecordNotFoundError,
)
from ._utils import generate_session_token, hash_token, get_logger, get_auth_result, merge_cookie_config
from .schemas import (
    AdapterContainer,
    AuthResult,
    PyAuthCookiesInput,
)

class PyAuth:
    """Core py-auth authentication manager."""

    def __init__(
        self,
        adapter: Any,
        providers: List[Any] | None = None,
        cookies: PyAuthCookiesInput | None = None,
    ):
        container = AdapterContainer(adapter=adapter)

        self.adapter = container.adapter
        self._provider_map = {getattr(p, "id", None): p for p in (providers or [])}
        self.cookies = merge_cookie_config(user_config=cookies)
    
    async def handle_create_session (self, user_data: Dict[str, Any], provider: str) -> AuthResult:
        max_retries = 3
        created_session = None
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        session_token = generate_session_token()

        for _ in range(max_retries):
            session_token_hash = hash_token(session_token)
            try:
                user_id = user_data.get("id")

                if not isinstance(user_id, str):
                    get_logger().error(
                        f"{provider or "Provider"} returned invalid user data: "
                        "expected 'id' to be a string."
                    )

                    return get_auth_result(
                        error={
                            "code": "InternalServerError",
                            "status_code": 500,
                            "message": "An internal error occurred.",
                        }
                    )

                created_session = await self.adapter.create_session({
                    "session_token_hash": session_token_hash,
                    "user_id": user_id,
                    "expires": expires,
                })

                break

            except DuplicateEntryError:
                get_logger().warning(
                    "Session token hash collision occurred during session creation; "
                    "retrying with a new session token."
                )

                session_token = generate_session_token()

            except ForeignKeyViolationError as e:
                get_logger().exception(
                    "Foreign key violation occurred while creating session: "
                    "referenced user record not found."
                )

                status_code = getattr(e, "status_code", 500)

                return get_auth_result(
                    error={
                        "code": "ForeignKeyViolation",
                        "status_code": status_code,
                        "message": "The user associated with this login no longer exists.",
                    }
                )

            except Exception as e:
                get_logger().exception("Unexpected error occurred during session creation.")
                status_code = getattr(e, "status_code", 500)

                return get_auth_result(
                    error={
                        "code": "InternalServerError",
                        "status_code": status_code,
                        "message": "An internal error occurred.",
                    }
                )
            
        if not created_session:
            return get_auth_result(
                error={
                    "code": "SessionCreationFailed",
                    "status_code": 500,
                    "message": "Failed to create session. Please try again.",
                }
            )
        
        return get_auth_result(data={
            "session_token": session_token,
            "expires": created_session["expires"]
        })
    
    async def verify_session(self, session_token: str) -> AuthResult:
        """Verify an active session."""
        if not session_token:
            return get_auth_result(
                error={
                    "code": "MissingSessionToken",
                    "status_code": 401,
                    "message": "Session token was not provided.",
                }
            )
        
        try:
            session_token_hash = hash_token(session_token)
            session = await self.adapter.get_session_by_session_token_hash(session_token_hash)

            if not session:
                return get_auth_result(
                    error={
                        "code": "InvalidSession",
                        "status_code": 401,
                        "message": "Session not found or is invalid."
                    }
                )
            
            if not isinstance(session, dict):
                get_logger().error("Configured adapter returned invalid session data: expected a dictionary.")

                return get_auth_result(
                    error={
                      "code": "InternalServerError",
                      "status_code": 500,
                      "message": "An internal error occurred.",
                    }
                )
              
            expires: datetime | None = session.get("expires", None)
            now = datetime.now(timezone.utc)

            if not isinstance(expires, datetime):
                get_logger().error(
                    "Invalid session data returned by the configured adapter: "
                    "'expires' must be a datetime instance."
                )

                return get_auth_result(
                    error={
                        "code": "InternalServerError",
                        "status_code": 500,
                        "message": "An internal error occurred."
                    }
                )
            
            if expires <= now:
                await self.adapter.delete_session_by_session_token_hash(session_token_hash)
                
                return get_auth_result(
                    error={
                        "code": "SessionExpired",
                        "status_code": 401,
                        "message": "Session has expired. Sign in again to continue."
                    }
                )
            
            return get_auth_result(data={"session":session})
            
        except Exception:
            get_logger().exception("Unexpected error occurred while verifying session.")
            
            return get_auth_result(
                error={
                    "code": "InternalServerError",
                    "status_code": 500,
                    "message": "An internal error occurred.",
                }
            )

    async def signout(self, session_id: str) -> AuthResult:
        """Invalidate and delete the session identified by session_id with error handling."""

        try:
            await self.adapter.delete_session(session_id)
            return get_auth_result(data={"signed_out":True})
        except RecordNotFoundError:
            return get_auth_result(data={"signed_out":True})
        except Exception:
            get_logger().exception("Unexpected error during signout.")
            return get_auth_result(
                error={
                    "code": "InternalServerError",
                    "status_code": 500,
                    "message": "An internal error occurred.",
                }
            )
        
    async def handle_google_callback (self, 
        request_url: str,
        state: str, 
        code_verifier: str, 
        nonce: str
    ) -> AuthResult:
        """Authenticate a user with Google and create an application session."""
        google_provider = self._provider_map.get("google")

        if not google_provider:
            get_logger().error("Attempted to call 'handle_google_callback' but 'GoogleProvider' is not configured.")

            return get_auth_result(
                error={
                    "code": "InternalServerError",
                    "status_code": 500,
                    "message": "An internal error occurred."
                }
            )
        
        result: AuthResult = await google_provider.authenticate(
            request_url,
            state,
            code_verifier,
            nonce,
            self.adapter,
        )

        if result.get("error"):
            return result
        
        user_data: Dict[str, Any] = result.get("data") or {}
        return await self.handle_create_session(user_data=user_data, provider="GoogleProvider")
    
    def verify_csrf_double_submit (self, cookie_csrf_token: str, submitted_csrf_token: str) -> AuthResult:
        if not cookie_csrf_token:
            return get_auth_result(
                error={
                    "code": "MissingCsrfToken",
                    "status_code": 401,
                    "message": "CSRF token was not provided.",
                }
            )
        
        if submitted_csrf_token != cookie_csrf_token:
            return get_auth_result(
                error={
                    "code": "InvalidCsrfToken",
                    "status_code": 403,
                    "message": "The provided CSRF token is invalid."
                }
            )
        
        return get_auth_result(data={"validated":True})        

    async def signin_with_credentials(self, request_body: Dict[str, Any]) -> AuthResult:
        """Authenticate user credentials, create a session, and return session tokens."""
        credentials_provider = self._provider_map.get("credentials")

        if not credentials_provider:
            get_logger().error("Attempted to call 'signin_with_credentials' but 'CredentialsProvider' is not configured.")

            return get_auth_result(
                error={
                    "code": "InternalServerError",
                    "status_code": 500,
                    "message": "An internal error occurred."
                }
            )
        
        result: AuthResult = await credentials_provider.authenticate(request_body)

        if result.get("error"):
            return result
        
        user_data: Dict[str, Any]= result.get("data") or {}
        return await self.handle_create_session(user_data=user_data, provider="CredentialsProvider")
