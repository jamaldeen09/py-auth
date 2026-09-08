from enum import Enum
from typing import Any, List, Optional, Union
from fastapi import APIRouter, Request, Response, Depends
from py_auth import PyAuth
from py_auth.schemas import CookieConfig
from .utils import raise_auth_exception

class PyAuthFastAPI(APIRouter):
    def __init__(
        self,
        auth: PyAuth,
        *,
        prefix: str = "/auth",
        tags: Optional[List[Union[str, Enum]]] = None,
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
        options = cookie_config["options"]
        response.set_cookie(
            key=cookie_config["name"],
            value=value,
            httponly=options.get("http_only"),
            secure=options.get("secure"),
            samesite=options.get("same_site"),
            path=options.get("path"),
            domain=options.get("domain"),
            max_age=options.get("max_age"),
            expires=options.get("expires"),
        )

    def _clear_auth_cookie(self, response: Response, cookie_config: CookieConfig):
        """Reusable helper to clear auth cookies with matching attributes."""
        options = cookie_config["options"]
        response.delete_cookie(
            key=cookie_config["name"],
            path=options.get("path", "/"),
            domain=options.get("domain"),
            secure=options.get("secure", True),
            httponly=options.get("http_only", False),
            samesite=options.get("same_site", "lax"),
        )

    def get_current_session(self):
        """Factory method returning a valid FastAPI dependency closure."""

        async def dependency(request: Request):
            session_token = request.cookies.get(
                self.auth.cookies["session_token"]["name"]
            )
            csrf_token = request.cookies.get(self.auth.cookies["csrf_token"]["name"])
            result = await self.auth.verify_session(session_token, csrf_token)

            if result.get("error"):
                raise_auth_exception(result["error"])

            return result["data"]["session"]

        return dependency

    def _register_routes(self):
        @self.post("/signin")
        async def signin(request: Request, response: Response):
            request_body = await request.json()
            result = await self.auth.signin_with_credentials(request_body)

            if result.get("error"):
                raise_auth_exception(result["error"])

            data = result["data"]
            self._set_auth_cookie(
                response, self.auth.cookies["session_token"], data["session_token"]
            )
            self._set_auth_cookie(
                response, self.auth.cookies["csrf_token"], data["csrf_token"]
            )

            return {"success": True, "message": "You have successfully signed in."}

        @self.post("/signout")
        async def signout(
            response: Response, session=Depends(self.get_current_session())
        ):
            session_id = session["id"]
            await self.auth.signout(session_id)
            self._clear_auth_cookie(response, self.auth.cookies["session_token"])
            self._clear_auth_cookie(response, self.auth.cookies["csrf_token"])
            return {"success": True, "message": "You have successfully signed out."}

        @self.get("/session")
        async def get_session(
            response: Response, session=Depends(self.get_current_session())
        ):
            """Refreshes/fetches session data and rotates the CSRF token if needed."""
            result = await self.auth.update_session_csrf_token(session["id"])

            if result.get("error"):
                raise_auth_exception(result["error"])

            csrf_cookie = self.auth.cookies["csrf_token"]
            self._set_auth_cookie(response, csrf_cookie, result["data"]["csrf_token"])

            session_dict = {
                "id": session.get("id", None),
                "user_id": session.get("user_id", None),
                "expires": session.get("expires", None),
            }
            return {
                "success": True,
                "message": "Session is active.",
                "session": session_dict,
            }