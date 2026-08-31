from typing import Callable, Any
from ..utils import clean_value, log
from ..schemas import ProviderAuthenticateResult
from ..base import BaseProvider
from pydantic import BaseModel, RootModel, field_validator, ConfigDict
import sys

class ValidationError(dict):
    field: str
    errors: list[str]

class CredentialField(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())
    data_type: type | Callable
    validator: Callable[[Any], list[str]]

class CredentialsConfig(RootModel):
    root: dict[str, CredentialField]

    @field_validator("root")
    @classmethod
    def validate_credentials_structure(cls, v: dict[str, CredentialField]) -> dict[str, CredentialField]:
        return v

class AuthorizeUserResult (dict):
    success: bool
    data: dict | None
    error: str | None 

class ValidateCredentialsResult(dict):
    validation_errors: list[ValidationError]
    sanitized_data: dict[str, Any]

class CredentialsProvider(BaseProvider):
    def __init__(self, credentials: CredentialsConfig, authorize: Callable[[dict[str, Any]], Any | None]):
        super().__init__()
        self.credentials = CredentialsConfig.model_validate(credentials)
        self.authorize = authorize        
    
    def validate_credentials(self, data: dict[str, Any]) -> ValidateCredentialsResult:
        validation_errors: list[ValidationError] = []
        sanitized_data = {}
            
        for key, credential in self.credentials.root.items():
            extract = data.get(key, None)
            data_type, validate_func = credential.data_type, credential.validator

            # Clean the extracted value so that the validate() function provided
            # by the user receives a value with the expected data type (this avoids unnecessary exceptions)

            # Example:
            # ⬇⬇⬇⬇⬇⬇⬇⬇⬇
            # This is the function that validates the "email" field
            # in the data provided by the client

            # @example
            # ```python
            # def validate_email(email:str):
            #   errors = []
            #   if not email:
            #      errors.append("Invalid email address.")
            #   return email
            # ```

            # Data Provided - {"email":900}
            # Credentials - {"email":{"validate":validate_email, "data_type":str}}
            # After being cleaned - {"email":""}

            # In this situation we explicitly stated that the data type expected for the email
            # is a string, but the data provided is 900 which is an integer. The clean_value
            # function defaults it to an empty string so as to make the validate() function
            # receive the intended data type
            cleaned_extract = clean_value(original_value=extract,data_type=data_type)
            sanitized_data[key] = cleaned_extract
            errors = validate_func(cleaned_extract)

            # Check if there are no validation errors and if not
            # move on to the next field
            if not errors:
                continue

            # Otherwise append the errors and the field into the validation_errors list
            validation_errors.append({"field":key,"errors":errors})

        # At the end of the loop return the validation_errors and original data provided
        # for use across other services/methods
        return {"validation_errors":validation_errors, "sanitized_data":sanitized_data}

    async def authenticate (self, data: dict[str, Any]) -> ProviderAuthenticateResult:
        validation_result = self.validate_credentials(data)
        validation_errors = validation_result["validation_errors"]
        sanitized_data = validation_result["sanitized_data"]

        # Check if there are any validation errors
        if validation_errors:
            return {"success":False,"data":None,"error":{"validation_errors":validation_errors}}
        
        try:
            result = await self.authorize(sanitized_data)

            # Add a fallback to make sure result actually contains
            # some data, because this data is what is included
            # in the token's payload
            if not result:
                return {"data": None, "error": {"status_code":401,"message":"Unauthorized"}}
            
            return {"data":result,"error":None}
        except KeyError as e:
            missing_key = str(e)
            log(
              level="ERROR",
              message=f"A KeyError ({missing_key}) was raised while executing your 'authorize()' function.",
              details="Check your dictionary lookups or database models to ensure the key exists."
            )
            error_message = f"Missing required credential field: {e}"
            return {"data": None, "error": {"status_code":500,"message":error_message}}
        except Exception as e:
            log(
              level="ERROR",
              message=f"An unhandled exception occurred inside your custom 'authorize()' function:",
              details=f"{type(e).__name__}: {e}"
            )
            error_message = str(e) or "Something went wrong."
            return {"data": None, "error": {"status_code":500,"message":error_message}}
