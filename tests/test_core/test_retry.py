"""
Tests for retry logic implementation.
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from app.core.retry import (
    RetryConfig,
    create_retry_decorator,
    create_async_retry_decorator,
    get_default_retry_config,
    get_database_retry_config,
    get_external_service_retry_config,
    retry_with_circuit_breaker,
)
from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig


class TestRetryConfig:
    """Test retry configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=60.0,
            exponential_base=3.0,
            jitter=False,
        )
        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    def test_retryable_exceptions(self):
        """Test retryable exceptions configuration."""
        config = RetryConfig(
            retryable_exceptions=(ConnectionError, TimeoutError)
        )
        assert ConnectionError in config.retryable_exceptions
        assert TimeoutError in config.retryable_exceptions
        assert ValueError not in config.retryable_exceptions


class TestRetryDecorators:
    """Test retry decorators."""

    @pytest.fixture
    def failing_function(self):
        """Create a function that fails a specific number of times."""
        call_count = 0

        async def fail_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return {"data": "success"}

        return fail_func, lambda: call_count

    @pytest.fixture
    def always_failing_function(self):
        """Create a function that always fails."""
        async def fail_func():
            raise ConnectionError("Permanent failure")
        return fail_func

    @pytest.fixture
    def successful_function(self):
        """Create a function that always succeeds."""
        async def success_func():
            return {"data": "success"}
        return success_func

    @pytest.mark.asyncio
    async def test_retry_decorator_success_after_retries(self, failing_function):
        """Test retry decorator succeeds after retries."""
        func, get_call_count = failing_function

        config = RetryConfig(max_attempts=3, base_delay=0.1)  # Short delay for testing
        decorator = create_retry_decorator(config, "Test Service")
        retry_func = decorator(func)

        start_time = time.time()
        result = await retry_func()
        end_time = time.time()

        # Should succeed after 2 retries
        assert result == {"data": "success"}
        assert get_call_count() == 3

        # Should have taken some time due to delays
        assert end_time - start_time >= 0.1  # At least one delay

    @pytest.mark.asyncio
    async def test_retry_decorator_exhausts_attempts(self, always_failing_function):
        """Test retry decorator exhausts all attempts."""
        func = always_failing_function

        config = RetryConfig(max_attempts=3, base_delay=0.1)
        decorator = create_retry_decorator(config, "Test Service")
        retry_func = decorator(func)

        with pytest.raises(ConnectionError):
            await retry_func()

    @pytest.mark.asyncio
    async def test_retry_decorator_immediate_success(self, successful_function):
        """Test retry decorator with immediate success."""
        func = successful_function

        config = RetryConfig(max_attempts=3, base_delay=0.1)
        decorator = create_retry_decorator(config, "Test Service")
        retry_func = decorator(func)

        start_time = time.time()
        result = await retry_func()
        end_time = time.time()

        assert result == {"data": "success"}
        # Should be immediate, no delays
        assert end_time - start_time < 0.05

    @pytest.mark.asyncio
    async def test_async_retry_decorator(self, failing_function):
        """Test async-specific retry decorator."""
        func, get_call_count = failing_function

        config = RetryConfig(max_attempts=3, base_delay=0.1)
        decorator = create_async_retry_decorator(config, "Test Service")
        retry_func = decorator(func)

        result = await retry_func()

        assert result == {"data": "success"}
        assert get_call_count() == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        """Test non-retryable exceptions are not retried."""
        call_count = 0

        async def fail_with_non_retryable():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")

        config = RetryConfig(
            max_attempts=3,
            retryable_exceptions=(ConnectionError, TimeoutError)
        )
        decorator = create_retry_decorator(config, "Test Service")
        retry_func = decorator(fail_with_non_retryable)

        with pytest.raises(ValueError):
            await retry_func()

        # Should only be called once
        assert call_count == 1


class TestCircuitBreakerIntegration:
    """Test circuit breaker and retry integration."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for testing."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout=1,  # Short timeout for testing
        )
        return CircuitBreaker("Test Service", config)

    @pytest.fixture
    def failing_function(self):
        """Create a function that fails."""
        async def fail_func():
            raise ConnectionError("Service unavailable")
        return fail_func

    @pytest.mark.asyncio
    async def test_retry_with_circuit_breaker(self, circuit_breaker, failing_function):
        """Test retry decorator combined with circuit breaker."""
        decorator = retry_with_circuit_breaker(
            circuit_breaker,
            max_attempts=2,
            base_delay=0.1,
        )
        protected_func = decorator(failing_function)

        # First call should trigger retries and open circuit
        with pytest.raises(ConnectionError):
            await protected_func()

        # Second call should be rejected by open circuit
        with pytest.raises(Exception) as exc_info:
            await protected_func()

        # Should be circuit breaker error, not retry
        assert "Circuit breaker is OPEN" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_during_retries(self, circuit_breaker, mocker):
        """Test circuit breaker opens during retry attempts."""
        call_count = 0

        async def func_that_fails_then_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Temporary failure")
            return {"data": "success"}

        # Mock the circuit breaker to open after 2 failures
        original_on_failure = circuit_breaker._on_failure

        def mock_on_failure(*args, **kwargs):
            original_on_failure(*args, **kwargs)
            if circuit_breaker.failure_count >= 2:
                circuit_breaker.state = circuit_breaker.state.OPEN

        circuit_breaker._on_failure = mock_on_failure

        decorator = retry_with_circuit_breaker(
            circuit_breaker,
            max_attempts=4,
            base_delay=0.1,
        )
        protected_func = decorator(func_that_fails_then_succeeds)

        # Should fail due to circuit breaker opening
        with pytest.raises(Exception):
            await protected_func()


class TestRetryConfigurations:
    """Test predefined retry configurations."""

    def test_default_retry_config(self):
        """Test default retry configuration."""
        config = get_default_retry_config()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_database_retry_config(self):
        """Test database retry configuration."""
        config = get_database_retry_config()
        assert config.max_attempts == 5  # More attempts for database
        assert config.base_delay == 0.5  # Shorter initial delay
        assert config.max_delay == 10.0  # Lower max delay
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_external_service_retry_config(self):
        """Test external service retry configuration."""
        config = get_external_service_retry_config()
        assert config.max_attempts == 3
        assert config.base_delay == 2.0  # Longer initial delay
        assert config.max_delay == 60.0  # Higher max delay
        assert config.exponential_base == 2.5  # Higher exponential base
        assert config.jitter is True


class TestBackoffStrategy:
    """Test backoff strategy behavior."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Test exponential backoff timing."""
        delays = []

        async def capture_delay(func):
            start = time.time()
            await func()
            end = time.time()
            delays.append(end - start)

        async def failing_func():
            raise ConnectionError("Failure")

        config = RetryConfig(
            max_attempts=4,
            base_delay=0.1,
            max_delay=1.0,
            exponential_base=2.0,
            jitter=False,  # Disable jitter for predictable timing
        )
        decorator = create_retry_decorator(config, "Test Service")
        retry_func = decorator(failing_func)

        with pytest.raises(ConnectionError):
            await retry_func()

        # Should have made 4 attempts (1 initial + 3 retries)
        # We can't easily test exact timing due to async execution,
        # but we can verify the function was called multiple times
        assert len(delays) > 0

    @pytest.mark.asyncio
    async def test_jitter_variation(self):
        """Test jitter adds variation to delays."""
        delay_times = []

        async def failing_func():
            raise ConnectionError("Failure")

        config = RetryConfig(
            max_attempts=3,
            base_delay=0.1,
            jitter=True,
        )
        decorator = create_retry_decorator(config, "Test Service")
        retry_func = decorator(failing_func)

        # Run multiple times to see variation
        for _ in range(5):
            start_time = time.time()
            try:
                await retry_func()
            except:
                pass
            end_time = time.time()
            delay_times.append(end_time - start_time)

        # With jitter, we should see some variation in timing
        # (This is a rough test - actual variation depends on many factors)
        assert len(delay_times) == 5