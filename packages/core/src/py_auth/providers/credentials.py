import inspect

from pydantic import BaseModel, ConfigDict, RootModel
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypedDict, Union

from ..base import BaseProvider
from ..schemas import AuthResult
from ..utils import clean_value


class ValidationError(TypedDict):
    """Validation failure details for a credential field."""

    field: str
    errors: List[str]


class AuthorizeUserResult(TypedDict):
    """Standardized response structure for user authorization."""

    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]


class ValidateCredentialsResult(TypedDict):
    """Result of credential validation against configured schemas."""

    validation_errors: List[ValidationError]
    sanitized_data: Dict[str, Any]


class CredentialField(BaseModel):
    """Validation and type configuration for a credential input field."""

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    data_type: Union[type, Callable[..., Any]]
    validator: Callable[[Any], List[str]]


class CredentialsConfig(RootModel[Dict[str, CredentialField]]):
    """Configuration mapping credential field names to their field specifications."""

    root: Dict[str, CredentialField]


class CredentialsProvider(BaseProvider):
    """Provider for credential-based authentication.

    Handles credential validation, sanitization, and user-defined authorization callbacks.
    """

    def __init__(
        self,
        credentials: Union[CredentialsConfig, Dict[str, Any]],
        authorize: Union[
            Callable[[Dict[str, Any]], Any],
            Callable[[Dict[str, Any]], Awaitable[Any]],
        ],
    ) -> None:
        super().__init__()
        self.credentials = (
            credentials
            if isinstance(credentials, CredentialsConfig)
            else CredentialsConfig.model_validate(credentials)
        )
        self.authorize = authorize

    def validate_credentials(self, data: Dict[str, Any]) -> ValidateCredentialsResult:
        """Sanitize raw input payload and execute configured field validators."""
        validation_errors: List[ValidationError] = []
        sanitized_data: Dict[str, Any] = {}

        for key, credential in self.credentials.root.items():
            extract = data.get(key, None)
            data_type, validate_func = credential.data_type, credential.validator

            # Sanitize to ensure the validator receives the expected type signature
            cleaned_extract = clean_value(original_value=extract, data_type=data_type)
            sanitized_data[key] = cleaned_extract

            errors = validate_func(cleaned_extract)
            if errors:
                validation_errors.append({"field": key, "errors": errors})

        return {
            "validation_errors": validation_errors,
            "sanitized_data": sanitized_data,
        }

    async def authenticate(self, data: Dict[str, Any]) -> AuthResult:
        """Validate submitted credentials and invoke the user authorize callback."""
        validation_result = self.validate_credentials(data)
        validation_errors = validation_result["validation_errors"]
        sanitized_data = validation_result["sanitized_data"]

        if validation_errors:
            return {
                "data": None,
                "error": {
                    "status_code": 422,
                    "message": "Validation failed.",
                    "validation_errors": validation_errors,
                },
            }

        try:
            if inspect.iscoroutinefunction(self.authorize):
                result = await self.authorize(sanitized_data)
            else:
                result = self.authorize(sanitized_data)

            if not result:
                return {
                    "data": None,
                    "error": {"status_code": 401, "message": "Unauthorized"},
                }

            return {"data": result, "error": None}

        except KeyError as e:
            print(e)
            missing_key = str(e)
            return {
                "data": None,
                "error": {
                    "status_code": 500,
                    "message": f"Missing required credential field: {missing_key}",
                },
            }

        except Exception as e:
            print(e)
            return {
                "data": None,
                "error": {
                    "status_code": 500,
                    "message": str(e) or "Something went wrong.",
                },
            }


__all__ = [
    "ValidationError",
    "AuthorizeUserResult",
    "ValidateCredentialsResult",
    "CredentialField",
    "CredentialsConfig",
    "CredentialsProvider",
]
