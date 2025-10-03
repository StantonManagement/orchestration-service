"""
Custom exception classes for the System Orchestrator Service.
"""
from typing import Optional, Any
from fastapi import HTTPException, status


class BaseAPIException(HTTPException):
    """Base exception for API errors."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code


class ValidationError(BaseAPIException):
    """Exception for validation errors."""

    def __init__(self, detail: str, field: Optional[str] = None):
        error_code = "VALIDATION_ERROR"
        if field:
            error_code = f"VALIDATION_ERROR_{field.upper()}"
            detail = f"Validation failed for field '{field}': {detail}"
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code,
        )


class BusinessRuleError(BaseAPIException):
    """Exception for business rule violations."""

    def __init__(self, detail: str, rule_name: Optional[str] = None):
        error_code = "BUSINESS_RULE_ERROR"
        if rule_name:
            error_code = f"BUSINESS_RULE_{rule_name.upper()}"
            detail = f"Business rule '{rule_name}' violated: {detail}"
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code,
        )


class ServiceUnavailableError(BaseAPIException):
    """Exception for external service unavailability."""

    def __init__(self, service_name: str, detail: Optional[str] = None):
        error_code = f"SERVICE_UNAVAILABLE_{service_name.upper().replace(' ', '_')}"
        if not detail:
            detail = f"External service '{service_name}' is currently unavailable"
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code=error_code,
        )


class InternalServerError(BaseAPIException):
    """Exception for unexpected internal errors."""

    def __init__(self, detail: str = "An unexpected internal error occurred"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="INTERNAL_SERVER_ERROR",
        )


# AI Service Exceptions
class AIServiceError(Exception):
    """Base exception for AI service errors."""

    pass


class AIServiceTimeoutError(AIServiceError):
    """Exception for AI service timeout errors."""

    pass


class AIServiceRateLimitError(AIServiceError):
    """Exception for AI service rate limit errors."""

    pass


class AIServiceAuthenticationError(AIServiceError):
    """Exception for AI service authentication errors."""

    pass
