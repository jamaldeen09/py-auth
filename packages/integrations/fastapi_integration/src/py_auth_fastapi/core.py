

from enum import Enum
from typing import Any, List, Union, Dict
from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import RedirectResponse
from py_auth import PyAuth
from py_auth.schemas import CookieConfig
from py_auth.providers import GoogleProvider
from py_auth._utils import generate_csrf_token, generate_code_verifier, generate_nonce

from .utils import raise_auth_exception, get_logger

class PyAuthFastAPI(APIRouter):
    def __init__(
        self,
        auth: PyAuth,
        *,
        prefix: str = "/auth",
        tags: List[Union[str, Enum]] | None = None,
        **kwargs: Any,
    ):
        if tags is None:
            tags = ["Authentication"]

        super().__init__(prefix=prefix, tags=tags, **kwargs)
        self.auth = auth
        self._register_routes()

    def _set_auth_cookie(
        self, response: Response, cookie_config: CookieConfig, value: str
    ):
        """Reusable helper to apply cookie configurations dynamically."""
        options = cookie_config.options

        response.set_cookie(
            key=cookie_config.name,
            value=value,
            httponly=options.http_only,
            secure=options.secure,
            samesite=options.same_site,
            path=options.path,
            domain=options.domain,
            max_age=options.max_age,
            expires=options.expires,
        )
            
    def _clear_auth_cookie(self, response: Response, cookie_config: CookieConfig):
        """Reusable helper to clear auth cookies with matching attributes."""
        options = cookie_config.options

        response.delete_cookie(
            key=cookie_config.name,
            path=options.path,
            domain=options.domain,
            secure=options.secure,
            httponly=options.http_only,
            samesite=options.same_site,
        )

    def verify_csrf (self):
        async def dependency(request: Request):
            cookie_csrf_token = request.cookies.get(self.auth.cookies.csrf_token.name, "")
            submitted_csrf_token = request.headers.get("x-csrf-token", "")
            
            result = self.auth.verify_csrf_double_submit(cookie_csrf_token, submitted_csrf_token)
            error = result.get("error")

            if error:
                raise_auth_exception(error)

            return True
        return dependency

    def get_current_session(self, add_csrf_verification: bool = False):
        """Factory method returning a valid FastAPI dependency closure."""

        async def dependency(request: Request, _ = Depends(self.verify_csrf()) if add_csrf_verification else None):
            session_token_cookie_name = self.auth.cookies.session_token.name
            session_token = request.cookies.get(session_token_cookie_name, "")
            
            result = await self.auth.verify_session(session_token)
            error = result.get("error", None)
            data = result.get("data", None)    

            if error or not data:
                raise_auth_exception(error or {
                    "code": "InternalServerError",
                    "message": "An internal error occured.",
                    "status_code": 500
                })

            if not isinstance(data, dict):
                get_logger().error("PyAuth returned invalid session data: expected a dictionary.")

                raise_auth_exception({
                    "code": "InternalServerError",
                    "message": "An internal error occured.",
                    "status_code": 500
                })
    
            return data.get("session", None)
        
        return dependency
    
    def _register_routes(self):
        @self.get("/csrf")
        def csrf (request: Request, response: Response):
            csrf_cookie_config = self.auth.cookies.csrf_token
            csrf_token = request.cookies.get(csrf_cookie_config.name)

            if not csrf_token:
                csrf_token = generate_csrf_token()
                self._set_auth_cookie(
                   response=response, 
                   cookie_config=csrf_cookie_config,
                   value=csrf_token
                )

            return {"success":True,"message": "CSRF token generated successfully.", "data": {"csrf_token":csrf_token}}

        @self.post("/signin/credentials")
        async def signin(request: Request, response: Response, _ = Depends(self.verify_csrf())):
            request_body = await request.json()

            result = await self.auth.signin_with_credentials(request_body)
            error = result.get("error")

            if error:
                raise_auth_exception(error)

            data: Dict[str, Any] = result.get("data") or {}
            session_token: str = data.get("session_token", "")

            self._set_auth_cookie(
                response=response,
                cookie_config=self.auth.cookies.session_token,
                value=session_token
            )

            return {"success": True, "message": "You have successfully signed in."}

        @self.post("/signout")
        async def signout(
            response: Response, session=Depends(self.get_current_session(add_csrf_verification=True))
        ):
            session_id = session["id"]
            await self.auth.signout(session_id)

            self._clear_auth_cookie(response, self.auth.cookies.session_token)
            self._clear_auth_cookie(response, self.auth.cookies.csrf_token)
            return {"success": True, "message": "You have successfully signed out."}

        @self.get("/session")
        async def get_session(session=Depends(self.get_current_session())):
            """Fetches session data."""
            session_dict = {
                "id": session.get("id", None),
                "user_id": session.get("user_id", None),
                "expires": session.get("expires", None),
            }
            return {"success": True,"message": "Session is active.","session": session_dict}
        
        @self.get("/signin/google")
        async def signin_with_google(request: Request):
            google_provider = self.auth._provider_map.get("google")

            if not google_provider:
                get_logger().error(
                    "Attempted to call 'signin_with_google' but "
                    "'GoogleProvider' is not configured."
                )
                
                raise_auth_exception(error={
                    "code": "InternalServerError",
                    "status_code": 500,
                    "message": "An internal error occurred."
                })

            
            code_verifier = generate_code_verifier()
            nonce = generate_nonce()
            client = google_provider.get_client()

            authorization_url, state = google_provider.create_auth_url(
                code_verifier=code_verifier,
                nonce=nonce,
                client=client
            )

            response = RedirectResponse(authorization_url)
            state_cookie_config = self.auth.cookies.state
            nonce_cookie_config = self.auth.cookies.nonce
            pkce_code_verifier_cookie_config = self.auth.cookies.pkce_code_verifier

            self._set_auth_cookie(
                response=response,
                cookie_config=state_cookie_config,
                value=state
            )

            self._set_auth_cookie(
                response=response,
                cookie_config=nonce_cookie_config,
                value=nonce
            )

            self._set_auth_cookie(
                response=response,
                cookie_config=pkce_code_verifier_cookie_config,
                value=code_verifier
            )

            return response
    
        @self.get("/google/callback")
        async def google_callback(request: Request, response: Response):
            request_url = str(request.url)
            state = request.cookies.get(self.auth.cookies.state.name, "")
            code_verifier = request.cookies.get(self.auth.cookies.pkce_code_verifier.name, "")
            nonce = request.cookies.get(self.auth.cookies.nonce.name, "")

            result = await self.auth.handle_google_callback(
                request_url=request_url,
                state=state,
                code_verifier=code_verifier,
                nonce=nonce
            )

            error = result.get("error")
            if error:
                raise_auth_exception(error=error)

            self._clear_auth_cookie(
                response=response,
                cookie_config=self.auth.cookies.pkce_code_verifier
            )

            self._clear_auth_cookie(
                response=response,
                cookie_config=self.auth.cookies.nonce
            )

            self._clear_auth_cookie(
                response=response,
                cookie_config=self.auth.cookies.state
            )

            data = result.get("data") or {}
            session_token: str = data.get("session_token", "")
            csrf_token: str = data.get("csrf_token", "")
            
            self._set_auth_cookie(
                response=response,
                cookie_config=self.auth.cookies.session_token,
                value=session_token
            )

            self._set_auth_cookie(
                response=response,
                cookie_config=self.auth.cookies.csrf_token,
                value=csrf_token
            )

            return {"success": True, "message": "You have successfully signed in."}
        