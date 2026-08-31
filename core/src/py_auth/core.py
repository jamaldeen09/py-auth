from typing import Any, Union
from .schemas import PyAuthStrategy, HandleSignInWithCredentialsResult
from .utils import create_token,log
from .providers.credentials import CredentialsProvider
import os

class PyAuth:
    def __init__(self, adapter: Any = None, providers: (list[Union[CredentialsProvider]]) = [], strategy: PyAuthStrategy = PyAuthStrategy.JWT):
        # If the strategy is set to 'database' but an adapter
        # was not provided raise an exception
        if strategy == PyAuthStrategy.DATABASE and not adapter:
           raise ValueError(
            "Configuration Error: A database adapter must be provided when using PyAuthStrategy.DATABASE. "
            "Pass an adapter instance to PyAuth(adapter=your_adapter, strategy=PyAuthStrategy.DATABASE)."
           )
            
        self.strategy = strategy
        self.providers = providers

    async def handle_signin_with_credentials (self, data: dict[str, Any]) -> HandleSignInWithCredentialsResult:
        providers = self.providers
        credentials_provider = next((provider for provider in providers if provider.id == "credentials"), None)

        # Make sure providers includes "CredentialsProvider", if not throw an error
        # if this function is called
        if not credentials_provider:
          log(
            level="ERROR",
            message="Attempted to process a credential sign-in, but no CredentialsProvider was registered.",
            details="Make sure you add a CredentialsProvider to your providers configuration before handling sign-in requests."
          )
          return {"token":None,"error":{"status_code":500,"message":"Credentials provider is not configured."}}

        strategy = self.strategy
        if strategy == PyAuthStrategy.JWT:
            # Make sure the "PYAUTH_SECRET" environment variable has been set
            secret = os.getenv("PYAUTH_SECRET")
            if not secret:
               log(
                 level="ERROR",
                 message="The 'PYAUTH_SECRET' environment variable is missing.",
                 details="Set the PYAUTH_SECRET key in your environment or .env file to sign tokens securely."
                )
               return {"token":None,"error": "Server configuration error: Authentication secret is not set."} 
            
            # Authenticate the user using thier custom credentials provider
            result = await credentials_provider.authenticate(data=data)

            if result["error"] or not result["data"]:
                return {"token":None,"error":result.get("error",{"status_code":401,"message":"Unauthorized."})}
            
            # Create a new token with the data provided by the authorize function
            token: str = create_token(payload=result["data"], secret=secret)

            # Return the token
            return {"error":None,"token":token}
        else:
            pass