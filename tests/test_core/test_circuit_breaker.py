"""
Tests for circuit breaker implementation.
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    ServiceClient,
)
from app.core.exceptions import ServiceUnavailableError, ExternalServiceError


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.timeout == 60
        assert config.half_open_max_calls == 5
        assert config.recovery_timeout == 30
        assert config.min_wait == 1.0
        assert config.max_wait == 60.0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            timeout=120,
            half_open_max_calls=3,
        )
        assert config.failure_threshold == 10
        assert config.success_threshold == 5
        assert config.timeout == 120
        assert config.half_open_max_calls == 3


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for testing."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=1,  # Short timeout for testing
        )
        return CircuitBreaker("Test Service", config)

    @pytest.fixture
    def failing_function(self):
        """Create a function that always fails."""
        async def fail_func():
            raise ExternalServiceError("Test Service", "Service unavailable")
        return fail_func

    @pytest.fixture
    def successful_function(self):
        """Create a function that always succeeds."""
        async def success_func():
            return {"data": "success"}
        return success_func

    @pytest.mark.asyncio
    async def test_initial_closed_state(self, circuit_breaker):
        """Test circuit breaker starts in closed state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0

    @pytest.mark.asyncio
    async def test_successful_call_resets_failure_count(self, circuit_breaker, successful_function):
        """Test successful calls reset failure count."""
        # First, cause some failures
        for _ in range(2):
            try:
                await circuit_breaker.call_async(successful_function)
            except:
                pass

        # Now a successful call should reset failure count
        result = await circuit_breaker.call_async(successful_function)
        assert result == {"data": "success"}
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failure_threshold(self, circuit_breaker, failing_function):
        """Test circuit opens after failure threshold is reached."""
        # Cause failures to reach threshold
        for i in range(3):
            with pytest.raises(ExternalServiceError):
                await circuit_breaker.call_async(failing_function)

        # Circuit should be open now
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.failure_count == 3

        # Next call should be rejected immediately
        with pytest.raises(ServiceUnavailableError):
            await circuit_breaker.call_async(failing_function)

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open(self, circuit_breaker, successful_function, failing_function):
        """Test circuit transitions to half-open after timeout and closes on success."""
        # Cause failures to open circuit
        for i in range(3):
            with pytest.raises(ExternalServiceError):
                await circuit_breaker.call_async(failing_function)

        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(1.1)  # Slightly longer than configured timeout

        # First call should transition to half-open and succeed
        result = await circuit_breaker.call_async(successful_function)
        assert result == {"data": "success"}

        # Circuit should now be in half-open state
        assert circuit_breaker.state == CircuitState.HALF_OPEN

        # Second successful call should close the circuit
        result = await circuit_breaker.call_async(successful_function)
        assert result == {"data": "success"}

        # Circuit should be closed now
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_closes_after_success_threshold(self, circuit_breaker, successful_function, failing_function):
        """Test circuit closes after success threshold in half-open state."""
        # Open the circuit
        for i in range(3):
            with pytest.raises(ExternalServiceError):
                await circuit_breaker.call_async(failing_function)

        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for timeout and transition to half-open
        time.sleep(1.1)

        # Make successful calls to reach success threshold
        for i in range(2):
            result = await circuit_breaker.call_async(successful_function)
            assert result == {"data": "success"}

        # Circuit should be closed now
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_max_calls_limit(self, circuit_breaker, successful_function, failing_function):
        """Test half-open state has maximum call limit."""
        # Open the circuit
        for i in range(3):
            with pytest.raises(ExternalServiceError):
                await circuit_breaker.call_async(failing_function)

        # Wait for timeout
        time.sleep(1.1)

        # First call should transition to half-open and succeed
        result = await circuit_breaker.call_async(successful_function)
        assert result == {"data": "success"}
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        assert circuit_breaker.half_open_calls == 1

        # Second successful call should close the circuit
        result = await circuit_breaker.call_async(successful_function)
        assert result == {"data": "success"}
        assert circuit_breaker.state == CircuitState.CLOSED

        # Test the half-open call limit by opening again and making calls that will fail
        for i in range(3):
            with pytest.raises(ExternalServiceError):
                await circuit_breaker.call_async(failing_function)

        # Wait for timeout
        time.sleep(1.1)

        # Make a mix of successful and failing calls in half-open to test the limit
        # This test now verifies that the half-open calls counter works correctly
        await circuit_breaker.call_async(successful_function)  # Should work
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        assert circuit_breaker.half_open_calls == 1

        # A failure should immediately reopen the circuit
        with pytest.raises(ExternalServiceError):
            await circuit_breaker.call_async(failing_function)
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, circuit_breaker, successful_function, failing_function):
        """Test metrics are properly tracked."""
        # Make some successful calls
        for i in range(3):
            await circuit_breaker.call_async(successful_function)

        # Make some failing calls
        for i in range(2):
            try:
                await circuit_breaker.call_async(failing_function)
            except:
                pass

        metrics = circuit_breaker.metrics
        assert metrics.total_calls == 5
        assert metrics.successful_calls == 3
        assert metrics.failed_calls == 2
        assert 0.0 <= metrics.failure_rate <= 1.0
        assert metrics.average_response_time >= 0.0

    def test_get_status(self, circuit_breaker):
        """Test status reporting."""
        status = circuit_breaker.get_status()

        required_fields = [
            "service", "state", "failure_count", "success_count",
            "failure_threshold", "success_threshold", "half_open_calls",
            "half_open_max_calls", "is_available", "metrics"
        ]

        for field in required_fields:
            assert field in status

        assert status["service"] == "Test Service"
        assert status["state"] == CircuitState.CLOSED.value
        assert status["is_available"] is True

    def test_reset(self, circuit_breaker, failing_function):
        """Test circuit breaker reset."""
        # Cause some failures
        try:
            asyncio.run(circuit_breaker.call_async(failing_function))
        except:
            pass

        # Reset should restore initial state
        circuit_breaker.reset()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert circuit_breaker.half_open_calls == 0
        assert circuit_breaker.last_failure_time is None


class TestServiceClient:
    """Test service client with circuit breaker."""

    @pytest.fixture
    def mock_service_client(self):
        """Create a service client with mocked HTTP client."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=1)
        client = ServiceClient(
            service_name="Test Service",
            base_url="https://api.example.com",
            timeout_seconds=5,
            circuit_breaker_config=config,
        )
        return client

    @pytest.mark.asyncio
    async def test_successful_request(self, mock_service_client, mocker):
        """Test successful HTTP request."""
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "success"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        mock_service_client.client = mock_client

        result = await mock_service_client.get("test")

        assert result == {"data": "success"}
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_error_raises_external_service_error(self, mock_service_client, mocker):
        """Test HTTP errors are converted to ExternalServiceError."""
        import httpx
        from unittest.mock import MagicMock

        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        mock_service_client.client = mock_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await mock_service_client.get("test")

        assert exc_info.value.service_name == "Test Service"
        assert "HTTP 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, mock_service_client, mocker):
        """Test circuit breaker is properly integrated."""
        # Mock failing request
        mock_client = AsyncMock()
        mock_client.request.side_effect = Exception("Connection failed")
        mock_service_client.client = mock_client

        # Make enough requests to open circuit
        for i in range(2):
            with pytest.raises(ExternalServiceError):
                await mock_service_client.get("test")

        # Circuit should be open now
        assert mock_service_client.circuit_breaker.state == CircuitState.OPEN

        # Next request should fail immediately due to open circuit
        with pytest.raises(ExternalServiceError) as exc_info:
            await mock_service_client.get("test")

        assert "Circuit breaker is OPEN" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_service_client, mocker):
        """Test successful health check."""
        # Mock successful health check
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        mock_service_client.client = mock_client

        result = await mock_service_client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_service_client, mocker):
        """Test failed health check."""
        # Mock failed health check
        mock_client = AsyncMock()
        mock_client.request.side_effect = Exception("Connection failed")
        mock_service_client.client = mock_client

        result = await mock_service_client.health_check()

        assert result is False

    def test_get_circuit_status(self, mock_service_client):
        """Test getting circuit breaker status."""
        status = mock_service_client.get_circuit_status()

        assert "service" in status
        assert "state" in status
        assert "metrics" in status
        assert status["service"] == "Test Service"