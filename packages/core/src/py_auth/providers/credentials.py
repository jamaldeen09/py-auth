import inspect

from pydantic import BaseModel, ValidationError as PydanticValidationError
from typing import Any, Awaitable, Callable, Dict, List, TypedDict, Type, Union

from ..base import BaseProvider
from ..schemas import AuthResult
from ..utils import get_logger, get_auth_result


class ValidationError(TypedDict):
    """Represents structured field validation errors for request bodies."""

    field: str
    errors: List[str]

class CredentialsProvider(BaseProvider):
    """Provider for credential-based authentication.

    Handles credential validation, sanitization, and user-defined authorization callbacks.
    """

    def __init__(
        self,
        model: Type[BaseModel],
        authorize: Union[Callable[[Dict[str, Any]], Any], Callable[[Dict[str, Any]], Awaitable[Any]]],
    ) -> None:
        super().__init__()
        self.model = model
        self.authorize = authorize

    async def handle_request(self, request_body: Dict[str, Any]) -> AuthResult:
        """Validate request data using the Pydantic model and execute the authorization callback."""
        try:
            validated_data = self.model.model_validate(request_body)
            payload = validated_data.model_dump()

        except PydanticValidationError as e:
            formatted_errors: list[ValidationError] = [
                {"field": ".".join(str(loc) for loc in err["loc"]), "errors": [err["msg"]]}
                for err in e.errors()
            ]

            return get_auth_result(
                error={
                    "code": "ValidationError",
                    "status_code": 422,
                    "message": "Validation failed.",
                    "details": {"validation_errors":formatted_errors}
                }
            )

        try:
            is_coroutine_func = inspect.iscoroutinefunction(self.authorize)

            if is_coroutine_func:
                result = await self.authorize(payload)
            else:
                result = self.authorize(payload)

            if not result:
                return get_auth_result(
                    error={
                        "code": "CredentialsSignIn",
                        "status_code": 401,
                        "message": "Invalid email or password."
                    }
                )
            
            return get_auth_result(data=result)
        
        except Exception as e:
            get_logger().exception(
                "Unexpected error occurred inside the authorization callback.",
                exc_info=e,
            )

            return get_auth_result(
                error={
                    "code": "InternalServerError",
                    "status_code": 500,
                    "message": "An internal error occurred."
                }
            )

__all__ = ["ValidationError","CredentialsProvider"]
