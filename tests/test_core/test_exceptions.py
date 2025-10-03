"""
Tests for custom exception hierarchy.
"""
import pytest
from fastapi import HTTPException, status

from app.core.exceptions import (
    BaseAPIException,
    ValidationError,
    BusinessRuleError,
    WorkflowError,
    ServiceUnavailableError,
    DegradedServiceError,
    CircuitBreakerOpenError,
    ExternalServiceError,
    ExternalServiceTimeoutError,
    ExternalServiceRateLimitError,
    ExternalServiceAuthenticationError,
    DatabaseError,
    DatabaseConnectionError,
    DatabaseTimeoutError,
    ValidationException,
    BusinessRuleException,
    WorkflowException,
    map_external_service_error,
    get_user_friendly_error_message,
)


class TestBaseAPIException:
    """Test base API exception."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = BaseAPIException(
            status_code=400,
            detail="Test error",
            error_code="TEST_ERROR"
        )

        assert exc.status_code == 400
        assert exc.detail == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.correlation_id is not None  # Auto-generated
        assert exc.context == {}

    def test_with_correlation_id(self):
        """Test exception with provided correlation ID."""
        correlation_id = "test-correlation-123"
        exc = BaseAPIException(
            status_code=400,
            detail="Test error",
            correlation_id=correlation_id
        )

        assert exc.correlation_id == correlation_id

    def test_with_context(self):
        """Test exception with context."""
        context = {"field": "test_field", "value": "invalid"}
        exc = BaseAPIException(
            status_code=400,
            detail="Test error",
            context=context
        )

        assert exc.context == context

    def test_to_dict(self):
        """Test conversion to dictionary."""
        exc = BaseAPIException(
            status_code=400,
            detail="Test error",
            error_code="TEST_ERROR",
            correlation_id="test-123",
            context={"field": "test"}
        )

        result = exc.to_dict()
        expected = {
            "error": True,
            "error_code": "TEST_ERROR",
            "message": "Test error",
            "correlation_id": "test-123",
            "context": {"field": "test"},
        }

        assert result == expected


class TestValidationError:
    """Test validation error."""

    def test_basic_validation_error(self):
        """Test basic validation error."""
        exc = ValidationError("Invalid input")

        assert exc.status_code == 422
        assert exc.error_code == "ORC_001"
        assert exc.detail == "Invalid input"
        assert exc.context["field"] is None
        assert exc.context["value"] is None

    def test_validation_error_with_field(self):
        """Test validation error with field name."""
        exc = ValidationError("Invalid email", field="email")

        assert exc.error_code == "ORC_001_EMAIL"
        assert "email" in exc.detail
        assert exc.context["field"] == "email"
        assert exc.context["value"] is None

    def test_validation_error_with_value(self):
        """Test validation error with field value."""
        exc = ValidationError("Invalid email", field="email", value="invalid-email")

        assert exc.context["field"] == "email"
        assert exc.context["value"] == "invalid-email"


class TestBusinessRuleError:
    """Test business rule error."""

    def test_basic_business_rule_error(self):
        """Test basic business rule error."""
        exc = BusinessRuleError("Rule violated")

        assert exc.status_code == 422
        assert exc.error_code == "ORC_002"
        assert exc.detail == "Rule violated"
        assert exc.context["rule_name"] is None
        assert exc.context["entity_id"] is None

    def test_business_rule_error_with_rule_name(self):
        """Test business rule error with rule name."""
        exc = BusinessRuleError("Maximum exceeded", rule_name="MAXIMUM_LIMIT")

        assert exc.error_code == "ORC_002_MAXIMUM_LIMIT"
        assert "MAXIMUM_LIMIT" in exc.detail
        assert exc.context["rule_name"] == "MAXIMUM_LIMIT"

    def test_business_rule_error_with_entity_id(self):
        """Test business rule error with entity ID."""
        exc = BusinessRuleError("Limit exceeded", entity_id="entity-123")

        assert exc.context["entity_id"] == "entity-123"


class TestWorkflowError:
    """Test workflow error."""

    def test_basic_workflow_error(self):
        """Test basic workflow error."""
        exc = WorkflowError("Workflow failed")

        assert exc.status_code == 400
        assert exc.error_code == "ORC_003"
        assert exc.context["workflow_id"] is None
        assert exc.context["workflow_step"] is None
        assert exc.context["tenant_id"] is None

    def test_workflow_error_with_details(self):
        """Test workflow error with details."""
        exc = WorkflowError(
            "Step failed",
            workflow_id="wf-123",
            workflow_step="validation",
            tenant_id="tenant-456"
        )

        assert exc.error_code == "ORC_003_VALIDATION"
        assert exc.context["workflow_id"] == "wf-123"
        assert exc.context["workflow_step"] == "validation"
        assert exc.context["tenant_id"] == "tenant-456"


class TestServiceUnavailableError:
    """Test service unavailable error."""

    def test_basic_service_unavailable(self):
        """Test basic service unavailable error."""
        exc = ServiceUnavailableError("Test Service")

        assert exc.status_code == 503
        assert exc.error_code == "ORC_004"
        assert "Test Service" in exc.detail
        assert exc.context["service_name"] == "Test Service"
        assert exc.context["retry_after"] is None

    def test_service_unavailable_with_retry_after(self):
        """Test service unavailable error with retry after."""
        exc = ServiceUnavailableError("Test Service", retry_after=60)

        assert exc.context["retry_after"] == 60
        assert exc.headers["Retry-After"] == "60"

    def test_service_unavailable_custom_detail(self):
        """Test service unavailable error with custom detail."""
        exc = ServiceUnavailableError(
            "Test Service",
            detail="Custom message"
        )

        assert exc.detail == "Custom message"


class TestDegradedServiceError:
    """Test degraded service error."""

    def test_degraded_service_error(self):
        """Test degraded service error."""
        exc = DegradedServiceError(
            "Test Service",
            "Service operating with limited functionality",
            fallback_used="cached_data"
        )

        assert exc.status_code == 200  # Success status
        assert exc.error_code == "ORC_005"
        assert exc.context["service_name"] == "Test Service"
        assert exc.context["fallback_used"] == "cached_data"


class TestCircuitBreakerOpenError:
    """Test circuit breaker open error."""

    def test_circuit_breaker_open_error(self):
        """Test circuit breaker open error."""
        circuit_status = {"state": "OPEN", "failure_count": 5}
        exc = CircuitBreakerOpenError(
            "Test Service",
            circuit_status=circuit_status
        )

        assert exc.status_code == 503
        assert exc.error_code == "ORC_006"
        assert exc.context["service_name"] == "Test Service"
        assert exc.context["circuit_status"] == circuit_status


class TestExternalServiceErrors:
    """Test external service errors."""

    def test_external_service_error(self):
        """Test basic external service error."""
        exc = ExternalServiceError(
            "Test Service",
            "Service failed",
            status_code=500,
            retry_after=60
        )

        assert exc.service_name == "Test Service"
        assert str(exc) == "[Test Service] Service failed"
        assert exc.status_code == 500
        assert exc.retry_after == 60

    def test_external_service_timeout_error(self):
        """Test external service timeout error."""
        exc = ExternalServiceTimeoutError("Test Service", 30.0)

        assert exc.service_name == "Test Service"
        assert "timed out after 30.0 seconds" in str(exc)
        assert exc.timeout_seconds == 30.0

    def test_external_service_rate_limit_error(self):
        """Test external service rate limit error."""
        exc = ExternalServiceRateLimitError("Test Service", retry_after=120)

        assert exc.service_name == "Test Service"
        assert "Service rate limit exceeded" in str(exc)
        assert exc.retry_after == 120

    def test_external_service_authentication_error(self):
        """Test external service authentication error."""
        exc = ExternalServiceAuthenticationError("Test Service")

        assert exc.service_name == "Test Service"
        assert "Service authentication failed" in str(exc)


class TestDatabaseErrors:
    """Test database errors."""

    def test_database_error(self):
        """Test basic database error."""
        exc = DatabaseError("Connection failed", operation="connect")

        assert "Connection failed" in str(exc)
        assert exc.operation == "connect"
        assert exc.context["operation"] == "connect"

    def test_database_connection_error(self):
        """Test database connection error."""
        exc = DatabaseConnectionError("Cannot connect", retry_after=30)

        assert exc.operation == "connection"
        assert exc.retry_after == 30

    def test_database_timeout_error(self):
        """Test database timeout error."""
        exc = DatabaseTimeoutError("Query timeout", 45.0)

        assert exc.operation == "query"
        assert exc.timeout_seconds == 45.0


class TestNonAPIExceptions:
    """Test non-API context exceptions."""

    def test_validation_exception(self):
        """Test validation exception."""
        exc = ValidationException("Invalid input", field="email", value="bad")

        assert "Validation failed" in str(exc)
        assert exc.field == "email"
        assert exc.value == "bad"

    def test_business_rule_exception(self):
        """Test business rule exception."""
        exc = BusinessRuleException("Rule violated", "MAX_LIMIT")

        assert "Business rule" in str(exc)
        assert exc.rule_name == "MAX_LIMIT"

    def test_workflow_exception(self):
        """Test workflow exception."""
        exc = WorkflowException("Workflow failed", "wf-123")

        assert "wf-123" in str(exc)
        assert exc.workflow_id == "wf-123"


class TestErrorMapping:
    """Test error mapping utilities."""

    def test_map_external_service_timeout_error(self):
        """Test mapping external service timeout error."""
        external_error = ExternalServiceTimeoutError("Test Service", 30.0)
        api_error = map_external_service_error(external_error)

        assert isinstance(api_error, ServiceUnavailableError)
        assert api_error.service_name == "Test Service"
        assert "timeout" in api_error.detail.lower()

    def test_map_external_service_rate_limit_error(self):
        """Test mapping external service rate limit error."""
        external_error = ExternalServiceRateLimitError("Test Service", 60)
        api_error = map_external_service_error(external_error)

        assert isinstance(api_error, ServiceUnavailableError)
        assert api_error.service_name == "Test Service"
        assert "rate limit" in api_error.detail.lower()
        assert api_error.retry_after == 60

    def test_map_external_service_authentication_error(self):
        """Test mapping external service authentication error."""
        external_error = ExternalServiceAuthenticationError("Test Service")
        api_error = map_external_service_error(external_error)

        assert isinstance(api_error, ServiceUnavailableError)
        assert api_error.service_name == "Test Service"
        assert "authentication" in api_error.detail.lower()

    def test_map_generic_external_service_error(self):
        """Test mapping generic external service error."""
        external_error = ExternalServiceError("Test Service", "Generic failure")
        api_error = map_external_service_error(external_error)

        assert isinstance(api_error, ServiceUnavailableError)
        assert api_error.service_name == "Test Service"
        assert "Generic failure" in api_error.detail


class TestUserFriendlyMessages:
    """Test user-friendly error messages."""

    def test_get_user_friendly_error_message(self):
        """Test getting user-friendly error messages."""
        # Test known error codes
        msg = get_user_friendly_error_message("ORC_001")
        assert "validation" in msg.lower()

        msg = get_user_friendly_error_message("ORC_002")
        assert "business rule" in msg.lower()

        msg = get_user_friendly_error_message("ORC_003")
        assert "workflow" in msg.lower()

        msg = get_user_friendly_error_message("ORC_004")
        assert "unavailable" in msg.lower()

        # Test unknown error code
        msg = get_user_friendly_error_message("UNKNOWN_CODE")
        assert "error occurred" in msg.lower()

        # Test empty error code
        msg = get_user_friendly_error_message("")
        assert "error occurred" in msg.lower()


class TestExceptionInheritance:
    """Test exception inheritance and HTTPException compatibility."""

    def test_api_exceptions_inherit_from_http_exception(self):
        """Test API exceptions inherit from HTTPException."""
        exc = ValidationError("Test error")
        assert isinstance(exc, HTTPException)

    def test_non_api_exceptions_do_not_inherit_from_http_exception(self):
        """Test non-API exceptions don't inherit from HTTPException."""
        exc = ValidationException("Test error")
        assert not isinstance(exc, HTTPException)

    def test_error_code_consistency(self):
        """Test error code patterns are consistent."""
        errors = [
            ValidationError("test"),
            BusinessRuleError("test"),
            WorkflowError("test"),
            ServiceUnavailableError("test"),
            DegradedServiceError("test", "test"),
            CircuitBreakerOpenError("test"),
        ]

        for error in errors:
            assert error.error_code.startswith("ORC_")
            assert len(error.error_code) == 7  # ORC_XXX format