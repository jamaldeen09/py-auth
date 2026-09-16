from enum import Enum
from typing import Any, List, Union
from fastapi import APIRouter, Request, Response, Depends
from py_auth import PyAuth
from py_auth.schemas import CookieConfig
from py_auth.utils import get_logger
from .utils import raise_auth_exception

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

    def get_current_session(self):
        """Factory method returning a valid FastAPI dependency closure."""

        async def dependency(request: Request):
            session_token_cookie_name = self.auth.cookies.session_token.name
            session_token = request.cookies.get(session_token_cookie_name, "")

            csrf_cookie_name = self.auth.cookies.csrf_token.name
            csrf_token = request.cookies.get(csrf_cookie_name, "")

            result = await self.auth.verify_session(session_token, csrf_token)
            error = result.get("error", None)
            data = result.get("data", None)

            if error or not data:
                raise_auth_exception(error or {
                    "code": "InternalServerError",
                    "message": "An internal error occurred.",
                    "status_code": 500
                })

            if not isinstance(data, dict):
                get_logger().error("PyAuth returned invalid session data: expected a dictionary.")

                raise_auth_exception({
                    "code": "InternalServerError",
                    "message": "An internal error occurred.",
                    "status_code": 500
                })

            return data.get("session", None)
        
        return dependency

    def _register_routes(self):
        @self.post("/signin")
        async def signin(request: Request, response: Response):
            request_body = await request.json()

            result = await self.auth.signin_with_credentials(request_body)
            error = result.get("error", None)
            data = result.get("data", None)

            if error or not data:
                raise_auth_exception(error or {
                    "code": "InternalServerError",
                    "message": "An internal error occurred.",
                    "status_code": 500
                })

            if not isinstance(data, dict):
                get_logger().error("PyAuth returned invalid session data: expected a dictionary.")

                raise_auth_exception({
                    "code": "InternalServerError",
                    "message": "An internal error occurred.",
                    "status_code": 500
                })

            session_token = data["session_token"]
            csrf_token = data["csrf_token"]

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

        @self.post("/signout")
        async def signout(
            response: Response, session=Depends(self.get_current_session())
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

        @self.post("/rotate-csrf")
        async def rotate_csrf(
            response: Response, session=Depends(self.get_current_session())
        ):
            """Rotates the CSRF token for the current session.

            Returns a fresh CSRF token and sets it as an updated cookie.
            """
            result = await self.auth.rotate_csrf(session_id=session["id"])
            error = result.get("error", None)
            data = result.get("data", None)

            if error or not data:
                raise_auth_exception(error or {
                    "code": "InternalServerError",
                    "message": "An internal error occurred.",
                    "status_code": 500
                })

            new_csrf_token = data.get("csrf_token", None)

            self._set_auth_cookie(
                response=response,
                cookie_config=self.auth.cookies.csrf_token,
                value=new_csrf_token,
            )

            return {"success": True, "message": "CSRF token rotated successfully."}