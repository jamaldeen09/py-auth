import httpx2

from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.integrations.base_client import OAuthError
from typing import Literal, Any, Dict, List
from joserfc.jwk import KeySet
from joserfc.jwt import decode, JWTClaimsRegistry
from joserfc.errors import (ClaimError,ExpiredTokenError,JoseError)

from ..base import BaseProvider
from ..utils import get_logger, get_auth_result, generate_token
from ..schemas import AuthResult

class GoogleProvider (BaseProvider):
    """Handle Google OAuth/OIDC authentication and return the authenticated user."""
    def __init__ (self, 
            client_id: str, 
            client_secret: str, 
            redirect_uri: str, 
            access_type: Literal["offline", "online"] = "offline",
            prompt: Literal["consent"] | None = None
        ) -> None:
        super().__init__()

        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_type = access_type
        self.prompt = prompt
    
    @staticmethod
    def generate_code_verifier():
        return generate_token(64)
    
    @staticmethod
    def generate_nonce():
        return generate_token()
    
    @staticmethod
    async def fetch_google_public_keys() -> AuthResult:
        async with httpx2.AsyncClient() as client:
            response = await client.get("https://www.googleapis.com/oauth2/v3/certs")

            try:
                response.raise_for_status()

            except httpx2.HTTPStatusError as e:
                status_code = e.response.status_code
                get_logger().error("Google JWKS endpoint returned HTTP %s.",status_code,)

                if status_code == 429:
                    return get_auth_result(error={
                        "code": "GoogleJWKSRateLimited",
                        "status_code": 503,
                        "message": "Google's authentication service is temporarily busy.",
                    })

                if 500 <= status_code <= 599:
                    return get_auth_result(error={
                        "code": "GoogleJWKSUnavailable",
                        "status_code": 503,
                        "message": "Google's authentication service is temporarily unavailable.",
                    })

                return get_auth_result(error={
                    "code": "GoogleJWKSRequestFailed",
                    "status_code": 502,
                    "message": "Unable to retrieve Google's public keys.",
                })
            
            except httpx2.RequestError:
                get_logger().exception("Request error while fetching Google JWKS.")

                return get_auth_result(error={
                    "code": "GoogleJWKSUnavailable",
                    "status_code": 503,
                    "message": "Google's authentication service is temporarily unavailable.",
                })

            try:
                jwks = response.json()
            except ValueError:
                get_logger().exception("Google returned invalid JWKS JSON.")

                return get_auth_result(error={
                    "code": "InvalidGoogleJWKS",
                    "status_code": 502,
                    "message": "Google returned an invalid public-key response.",
                })

            if (
                not isinstance(jwks, dict) 
                or not isinstance(jwks.get("keys"), list) 
                or not jwks["keys"]
            ):
                get_logger().error("Google returned an invalid JWKS structure")

                return get_auth_result(error={
                    "code": "InvalidGoogleJWKS",
                    "status_code": 502,
                    "message": "Google returned an invalid public-key response.",
                })
            
            return get_auth_result(data={"keys":jwks["keys"]})
        
    def get_client (self, options: Dict[str, Any] | None = None):
        return AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope="openid email profile",
            code_challenge_method="S256",
            **(options or {})
        )
    
    def validate_id_token(
        self,
        id_token: str,
        jwks: dict,
        *,
        nonce: str | None = None,
    ) -> AuthResult:
        
        try:
            key_set = KeySet.import_key_set(jwks)
            token = decode(id_token, key_set)
        
        except JoseError as e:
            get_logger().warning("Google ID-token decoding or signature verification failed: %s", e)
            
            return get_auth_result(error={
                "code": "InvalidIDToken",
                "status_code": 401,
                "message": "The ID token is invalid.",
            })
        
        claims: Dict[str, Any] = token.claims
        claims_registry = JWTClaimsRegistry(
            sub={"essential": True},
            email={"essential": True},
            iss={"essential": True,"value": self.google_issuer},
            aud={"essential": True,"value": self.client_id},
            exp={"essential": True},
            iat={"essential": True},
        )

        try:
            claims_registry.validate(claims)

        except ExpiredTokenError:
            get_logger().warning("Google ID token has expired.")

            return get_auth_result(error={
                "code": "ExpiredIDToken",
                "status_code": 401,
                "message": "The ID token has expired.",
            })
        
        except ClaimError as e:
            get_logger().warning("Google ID token claim validation failed: %s", e)

            return get_auth_result(error={
                "code": "InvalidIDToken",
                "status_code": 401,
                "message": "The ID token claims are invalid.",
            })

        if not isinstance(claims["sub"], str) or not isinstance(claims["email"], str):
            get_logger().warning("Google ID token contained invalid required identity claims.")
            
            return get_auth_result(error={
                "code": "InvalidIDToken",
                "status_code": 401,
                "message": "The identity information provided by Google is invalid.",
            })

        if nonce is not None and claims.get("nonce") != nonce:
            get_logger().warning("Google ID token nonce validation failed.")
           
            return get_auth_result(error={
               "code": "InvalidIDToken",
               "status_code": 401,
               "message": "The ID token is invalid."
            })
        return get_auth_result(data=claims)

    async def authenticate(
        self, 
        request_url: str, 
        state: str,
        code_verifier: str,
        nonce: str, 
        adapter: Any
    ) -> AuthResult:
        
        callback_result: AuthResult = await self.handle_callback(
            request_url=request_url,
            state=state,
            code_verifier=code_verifier,
        )
        
        if callback_result.get("error"):
            return callback_result
        
        callback_result_data: Dict[str, Any] = callback_result.get("data") or {}
        id_token: str | None = callback_result_data["id_token"]

        fetch_result: AuthResult = await GoogleProvider.fetch_google_public_keys()
        if fetch_result.get("error"):
            return fetch_result
        
        fetch_result_data: Dict[str, Any] = fetch_result.get("data") or {}
        keys: List[Dict[str, Any]] = fetch_result_data.get("keys") or []

        validation_result: AuthResult = self.validate_id_token((id_token or ""), jwks={"keys":keys}, nonce=nonce)
        if validation_result.get("error"):
            return validation_result
        
        claims: Dict[str, Any] = validation_result.get("data") or {}

        provider_acc_id: str = claims["sub"]
        user_email: str = claims["email"]
        name: str | None = claims.get("name", None)
        image: str | None = claims.get("picture", None)

        try:
            user_data = {"email":user_email.lower(),"name":name,"image":image}
            account_data = {"provider":"google","provider_account_id":provider_acc_id,**callback_result_data}
            result= await adapter.get_or_create_user_and_link_account(user_email,user_data,account_data)
            user_dict = result["user"]
            return get_auth_result(data=user_dict)
        
        except Exception:
            get_logger().exception("Unexpected error while creating or linking Google account.")
            
            return get_auth_result(error={
                "code": "InternalServerError",
                "status_code": 500,
                "message": "An internal error occurred.",
            })
    
    def create_auth_url(self, code_verifier: str, nonce: str, client: AsyncOAuth2Client):
        return client.create_authorization_url(
            "https://accounts.google.com/o/oauth2/v2/auth",
            access_type=self.access_type,
            prompt=self.prompt,
            nonce=nonce,
            code_verifier=code_verifier,
        )
    
    async def handle_callback (
        self, 
        request_url: str, 
        state: str,
        code_verifier: str,
    ) -> AuthResult:
        try:
            client = self.get_client(options={"state":state})

            fetch_token_res = await client.fetch_token(
                "https://oauth2.googleapis.com/token",
                authorization_response=request_url,
                code_verifier=code_verifier
            )

            token_data = {
                "type": "oidc",
                "access_token": fetch_token_res.get("access_token", None),
                "refresh_token": fetch_token_res.get("refresh_token", None),
                "expires_at": fetch_token_res.get("expires_at", None),
                "token_type": fetch_token_res.get("token_type", None),
                "scope": fetch_token_res.get("scope", None),
                "id_token": fetch_token_res.get("id_token", None),
                "session_state": fetch_token_res.get("session_state", None)
            }

            return get_auth_result(data=token_data)

        except OAuthError as e:
            get_logger().warning("Google OAuth token exchange failed: %s", e)

            return get_auth_result(
                error={
                    "code": "OAuthTokenExchangeFailed",
                    "status_code": 400,
                    "message": "The Google authorization could not be completed."
                }
            )
    
        except Exception as e:
            get_logger().exception("Unexpected error during Google OAuth callback token exchange.")

            return get_auth_result(
                error={
                    "code": "InternalServerError",
                    "status_code": 500,
                    "message": "An internal error occurred."
                }
            )

__all__ = ["GoogleProvider"]