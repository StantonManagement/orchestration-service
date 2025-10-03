"""
Custom exception classes for the System Orchestrator Service.
"""
from typing import Optional, Any, Dict
import uuid
from fastapi import HTTPException, status


class BaseAPIException(HTTPException):
    """Base exception for API errors."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.context = context or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.detail,
            "correlation_id": self.correlation_id,
            "context": self.context,
        }


class ValidationError(BaseAPIException):
    """Exception for validation errors."""

    def __init__(
        self,
        detail: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **context
    ):
        error_code = "ORC_001"  # Validation error code
        if field:
            error_code = f"ORC_001_{field.upper()}"
            detail = f"Validation failed for field '{field}': {detail}"

        context_dict = {"field": field, "value": value, **context}

        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code,
            context=context_dict,
        )


class BusinessRuleError(BaseAPIException):
    """Exception for business rule violations."""

    def __init__(
        self,
        detail: str,
        rule_name: Optional[str] = None,
        entity_id: Optional[str] = None,
        **context
    ):
        error_code = "ORC_002"  # Business rule error code
        if rule_name:
            error_code = f"ORC_002_{rule_name.upper()}"
            detail = f"Business rule '{rule_name}' violated: {detail}"

        context_dict = {"rule_name": rule_name, "entity_id": entity_id, **context}

        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code,
            context=context_dict,
        )


class WorkflowError(BaseAPIException):
    """Exception for workflow-related errors."""

    def __init__(
        self,
        detail: str,
        workflow_id: Optional[str] = None,
        workflow_step: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **context
    ):
        error_code = "ORC_003"  # Workflow error code
        if workflow_step:
            error_code = f"ORC_003_{workflow_step.upper()}"

        context_dict = {
            "workflow_id": workflow_id,
            "workflow_step": workflow_step,
            "tenant_id": tenant_id,
            **context
        }

        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=error_code,
            context=context_dict,
        )


class ServiceUnavailableError(BaseAPIException):
    """Exception for external service unavailability."""

    def __init__(
        self,
        service_name: str,
        detail: Optional[str] = None,
        retry_after: Optional[int] = None,
        **context
    ):
        self.service_name = service_name
        self.retry_after = retry_after
        error_code = "ORC_004"  # Service unavailable error code
        if not detail:
            detail = f"External service '{service_name}' is currently unavailable"

        context_dict = {
            "service_name": service_name,
            "retry_after": retry_after,
            **context
        }

        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)

        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code=error_code,
            headers=headers,
            context=context_dict,
        )


class DegradedServiceError(BaseAPIException):
    """Exception for degraded service operations."""

    def __init__(
        self,
        service_name: str,
        detail: str,
        fallback_used: Optional[str] = None,
        **context
    ):
        error_code = "ORC_005"  # Degraded service error code

        context_dict = {
            "service_name": service_name,
            "fallback_used": fallback_used,
            **context
        }

        super().__init__(
            status_code=status.HTTP_200_OK,  # Operation succeeded but with degraded functionality
            detail=detail,
            error_code=error_code,
            context=context_dict,
        )


class CircuitBreakerOpenError(BaseAPIException):
    """Exception for circuit breaker being open."""

    def __init__(
        self,
        service_name: str,
        detail: Optional[str] = None,
        circuit_status: Optional[Dict[str, Any]] = None,
        **context
    ):
        error_code = "ORC_006"  # Circuit breaker error code
        if not detail:
            detail = f"Circuit breaker is OPEN for service '{service_name}'"

        context_dict = {
            "service_name": service_name,
            "circuit_status": circuit_status,
            **context
        }

        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code=error_code,
            context=context_dict,
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


# External Service Exceptions
class ExternalServiceError(Exception):
    """Exception for external service call errors."""

    def __init__(
        self,
        service_name: str,
        message: str,
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
        **context
    ):
        self.service_name = service_name
        self.status_code = status_code
        self.retry_after = retry_after
        self.context = context
        super().__init__(f"[{service_name}] {message}")


class ExternalServiceTimeoutError(ExternalServiceError):
    """Exception for external service timeout errors."""

    def __init__(self, service_name: str, timeout_seconds: float, **context):
        super().__init__(
            service_name=service_name,
            message=f"Service timed out after {timeout_seconds} seconds",
            **context
        )
        self.timeout_seconds = timeout_seconds


class ExternalServiceRateLimitError(ExternalServiceError):
    """Exception for external service rate limiting errors."""

    def __init__(self, service_name: str, retry_after: Optional[int] = None, **context):
        super().__init__(
            service_name=service_name,
            message="Service rate limit exceeded",
            retry_after=retry_after,
            **context
        )


class ExternalServiceAuthenticationError(ExternalServiceError):
    """Exception for external service authentication errors."""

    def __init__(self, service_name: str, **context):
        super().__init__(
            service_name=service_name,
            message="Service authentication failed",
            **context
        )


# Escalation Exceptions (Story 2.2)
class EscalationError(Exception):
    """Exception for escalation-related errors."""

    def __init__(self, detail: str, escalation_id: Optional[str] = None, **context):
        self.escalation_id = escalation_id
        self.context = context
        super().__init__(detail)


# Database Exceptions
class DatabaseError(Exception):
    """Exception for database-related errors."""

    def __init__(self, detail: str, operation: Optional[str] = None, **context):
        self.operation = operation
        if operation:
            context["operation"] = operation
        self.context = context
        super().__init__(detail)


class DatabaseConnectionError(DatabaseError):
    """Exception for database connection errors."""

    def __init__(self, detail: str, retry_after: Optional[int] = None, **context):
        super().__init__(
            detail=detail,
            operation="connection",
            retry_after=retry_after,
            **context
        )
        self.retry_after = retry_after


class DatabaseTimeoutError(DatabaseError):
    """Exception for database timeout errors."""

    def __init__(self, detail: str, timeout_seconds: float, **context):
        super().__init__(
            detail=detail,
            operation="query",
            timeout_seconds=timeout_seconds,
            **context
        )
        self.timeout_seconds = timeout_seconds


class DatabaseException(DatabaseError):
    """Alias for DatabaseError for backward compatibility."""
    pass


# Non-API context exceptions
class ValidationException(Exception):
    """Exception for validation errors outside API context."""

    def __init__(self, detail: str, field: Optional[str] = None, value: Optional[Any] = None):
        self.field = field
        self.value = value
        message = f"Validation failed: {detail}"
        if field:
            message = f"Validation failed for field '{field}': {detail}"
        super().__init__(message)


class BusinessRuleException(Exception):
    """Exception for business rule violations outside API context."""

    def __init__(self, detail: str, rule_name: Optional[str] = None):
        self.rule_name = rule_name
        message = detail
        if rule_name:
            message = f"Business rule '{rule_name}' violated: {detail}"
        super().__init__(message)


class WorkflowException(Exception):
    """Exception for workflow errors outside API context."""

    def __init__(self, detail: str, workflow_id: Optional[str] = None):
        self.workflow_id = workflow_id
        message = detail
        if workflow_id:
            message = f"Workflow '{workflow_id}' error: {detail}"
        super().__init__(message)


# Error mapping utilities
def map_external_service_error(external_error: ExternalServiceError) -> BaseAPIException:
    """Map external service error to API exception."""
    if isinstance(external_error, ExternalServiceTimeoutError):
        return ServiceUnavailableError(
            service_name=external_error.service_name,
            detail=f"Service timeout: {external_error}",
            retry_after=int(external_error.timeout_seconds) if external_error.timeout_seconds else None,
        )
    elif isinstance(external_error, ExternalServiceRateLimitError):
        return ServiceUnavailableError(
            service_name=external_error.service_name,
            detail=f"Rate limit exceeded: {external_error}",
            retry_after=external_error.retry_after,
        )
    elif isinstance(external_error, ExternalServiceAuthenticationError):
        return ServiceUnavailableError(
            service_name=external_error.service_name,
            detail=f"Authentication failed: {external_error}",
        )
    else:
        return ServiceUnavailableError(
            service_name=external_error.service_name,
            detail=str(external_error),
        )


def get_user_friendly_error_message(error_code: str) -> str:
    """Get user-friendly error message for error code."""
    error_messages = {
        "ORC_001": "Validation failed. Please check your input.",
        "ORC_002": "Business rule violation. Please contact support.",
        "ORC_003": "Workflow error. Please try again or contact support.",
        "ORC_004": "Service temporarily unavailable. Please try again later.",
        "ORC_005": "Service operating with limited functionality.",
        "ORC_006": "Service currently unavailable due to technical issues.",
    }
    return error_messages.get(error_code, "An error occurred. Please try again.")
