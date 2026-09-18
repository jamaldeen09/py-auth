import hmac

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from .exceptions import (
    DuplicateEntryError,
    ForeignKeyViolationError,
    RecordNotFoundError,
)
from .utils import generate_token, hash_token, merge_cookie_config, get_logger, get_auth_result
from .schemas import (
    AdapterContainer,
    AuthResult,
    PyAuthCookiesInput,
)

# @app.get("/google")
# def google():
#     code_verifier = google_provider.generate_code_verifier()
#     nonce = google_provider.generate_nonce()
#     client = google_provider.get_client()

#     authorization_url, state = google_provider.create_auth_url(
#         code_verifier=code_verifier,
#         nonce=nonce,
#         client=client,
#     )

#     print("AUTHORIZATION URL:")
#     print(authorization_url)

#     response = RedirectResponse(authorization_url)

#     response.set_cookie(
#         key="state",
#         value=state,
#     )

#     response.set_cookie(
#         key="code_verifier",
#         value=code_verifier,
#     )

#     response.set_cookie(
#         key="nonce",
#         value=nonce,
#     )


#     print("state being stored in cookie:", state)
#     print("code_verifier being stored in cookie:", code_verifier)
#     print("nonce being stored in cookie:", nonce)
#     return response


# @app.get("/api/v1/auth/google/callback")
# async def callback(request: Request):
#     state = request.cookies.get("state")
#     code_verifier = request.cookies.get("code_verifier")

#     print("state extracted from cookie:", state)
#     print("code_verifier extracted from cookie:", code_verifier)

#     result = await google_provider.authenticate(
#         request_url=str(request.url),
#         state=state,
#         code_verifier=code_verifier,
#         nonce="THIS_IS_THE_WRONG_NONCE",
#         adapter="",
#     )

#     return result

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
    
    async def create_session(self, user_data: Dict[str, Any], provider: str | None = None) -> AuthResult:
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        session_token = generate_token(num_bytes=48)
        csrf_token = generate_token(num_bytes=32)

        max_retries = 3
        created_session = None

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
                    "csrf_token": csrf_token,
                    "expires": expires,
                })
                break

            except DuplicateEntryError:
                get_logger().warning(
                    "Session token hash collision occurred during session creation; "
                    "retrying with a new session token."
                )

                session_token = generate_token(num_bytes=48)

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

        return get_auth_result(
            data={
                "session_token": session_token,
                "csrf_token": csrf_token,
                "expires": expires,
                "session": created_session,
            }
        )

    async def verify_session(self, session_token: str, csrf_token: str) -> AuthResult:
        """Verify an active session and ensure CSRF token validity."""
        if not session_token:
            return get_auth_result(
                error={
                    "code": "MissingSessionToken",
                    "status_code": 401,
                    "message": "Session token was not provided.",
                }
            )

        if not csrf_token:
            return get_auth_result(
                error={
                    "code": "MissingCsrfToken",
                    "status_code": 401,
                    "message": "CSRF token was not provided.",
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
                        "message": "An internal error occured."
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
            
            db_csrf_token: str | None = session.get("csrf_token", None)

            if not isinstance(db_csrf_token, str):
                get_logger().error(
                    "Invalid session data returned by the configured adapter: "
                    "'csrf_token' must be a valid string."
                )

                return get_auth_result(
                    error={
                        "code": "InternalServerError",
                        "status_code": 500,
                        "message": "An internal error occured."
                    }
                )
            
            compare_result = hmac.compare_digest(db_csrf_token, csrf_token)
            if not compare_result:
                return get_auth_result(
                    error={
                        "code": "InvalidCsrfToken",
                        "status_code": 403,
                        "message": "CSRF token validation failed."
                    }
                )
            
            return get_auth_result(data={"session":session})
            
        except Exception:
            get_logger().exception("Unexpected error occurred while verifying session.")
            
            return get_auth_result(
                error={
                    "code": "InternalServerError",
                    "status_code": 500,
                    "message": "An internal error occured.",
                }
            )

    async def signout(self, session_id: str) -> AuthResult:
        """Invalidate and delete the session identified by session_id with error handling."""
        try:
            await self.adapter.delete_session(session_id)
            return get_auth_result(data={"signed_out":True})
        except RecordNotFoundError:
            return get_auth_result(data={"signed_out":True})
        except Exception as e:
            get_logger().exception("Unexpected error during signout.")
            return get_auth_result(
                error={
                    "code": "InternalServerError",
                    "status_code": 500,
                    "message": "An internal error occurred.",
                }
            )
        
    async def signin_with_google (self, 
        request_url: str,
        state: str, 
        code_verifier: str, 
        nonce: str
    ) -> AuthResult:
        """Authenticate a user with Google and create an application session."""
        google_provider = self._provider_map.get("google")

        if not google_provider:
            get_logger().error("Attempted to call 'signin_with_google' but 'GoogleProvider' is not configured.")

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

        if result["error"]:
            return result
        
        return await self.create_session(user_data=result["data"], provider="GoogleProvider")
    
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

        if result["error"]:
            return result
    
        return await self.create_session(user_data=result["data"], provider="CredentialsProvider")
