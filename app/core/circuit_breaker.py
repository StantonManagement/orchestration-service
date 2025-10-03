"""
Circuit breaker implementation for external service calls.
"""
import time
import random
from enum import Enum
from typing import Callable, Any, Dict, Optional, List
from dataclasses import dataclass, field
import structlog
import httpx
from app.core.exceptions import ServiceUnavailableError, ExternalServiceError

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: int = 60
    half_open_max_calls: int = 5
    recovery_timeout: int = 30
    min_wait: float = 1.0
    max_wait: float = 60.0


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics for monitoring."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    circuit_open_count: int = 0
    last_state_change: Optional[float] = None
    failure_rate: float = 0.0
    average_response_time: float = 0.0
    response_times: List[float] = field(default_factory=list)

    def update_metrics(self, success: bool, response_time: float) -> None:
        """Update metrics after a call."""
        self.total_calls += 1

        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1

        # Track response times for average calculation
        self.response_times.append(response_time)
        if len(self.response_times) > 100:  # Keep last 100 response times
            self.response_times.pop(0)

        # Calculate failure rate
        if self.total_calls > 0:
            self.failure_rate = self.failed_calls / self.total_calls

        # Calculate average response time
        if self.response_times:
            self.average_response_time = sum(self.response_times) / len(self.response_times)


class CircuitBreaker:
    """Circuit breaker for external service calls."""

    def __init__(
        self,
        service_name: str = "Unknown Service",
        config: Optional[CircuitBreakerConfig] = None,
    ):
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()

        # State tracking
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.half_open_calls = 0

        # Metrics
        self.metrics = CircuitBreakerMetrics()

    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap functions with circuit breaker."""

        async def wrapper(*args, **kwargs) -> Any:
            return await self.call_async(func, *args, **kwargs)

        return wrapper

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""
        start_time = time.time()

        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                logger.warning(
                    "Circuit breaker rejecting call - OPEN state",
                    service=self.service_name,
                    failure_count=self.failure_count,
                    last_failure_time=self.last_failure_time,
                )
                raise ServiceUnavailableError(
                    self.service_name,
                    f"Circuit breaker is OPEN for {self.service_name}",
                )

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                logger.warning(
                    "Circuit breaker rejecting call - half-open limit reached",
                    service=self.service_name,
                    half_open_calls=self.half_open_calls,
                )
                raise ServiceUnavailableError(
                    self.service_name,
                    f"Circuit breaker half-open limit reached for {self.service_name}",
                )

        self.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            response_time = time.time() - start_time
            self._on_success(response_time)
            return result
        except Exception as e:
            response_time = time.time() - start_time
            self._on_failure(response_time)
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt circuit reset."""
        return (
            self.last_failure_time
            and time.time() - self.last_failure_time >= self.config.timeout
        )

    def _transition_to_half_open(self) -> None:
        """Transition circuit breaker to half-open state."""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.metrics.last_state_change = time.time()
        logger.info(
            "Circuit breaker transitioning to half-open",
            service=self.service_name,
        )

    def _on_success(self, response_time: float) -> None:
        """Handle successful call."""
        self.metrics.update_metrics(True, response_time)

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
                self.failure_count = 0  # Reset failure count when closing circuit
                self.half_open_calls = 0
                self.metrics.last_state_change = time.time()
                logger.info(
                    "Circuit breaker reset to closed",
                    service=self.service_name,
                    success_count=self.success_count,
                )
        else:
            # In CLOSED state, reset failure count on success
            self.failure_count = 0
            self.success_count = 0

    def _on_failure(self, response_time: float) -> None:
        """Handle failed call."""
        self.metrics.update_metrics(False, response_time)
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # In half-open state, any failure immediately reopens the circuit
            self.state = CircuitState.OPEN
            self.metrics.circuit_open_count += 1
            self.metrics.last_state_change = time.time()
            logger.warning(
                "Circuit breaker reopened from half-open",
                service=self.service_name,
                failure_count=self.failure_count,
            )
        elif self.failure_count >= self.config.failure_threshold:
            # In closed state, open circuit if threshold reached
            self.state = CircuitState.OPEN
            self.metrics.circuit_open_count += 1
            self.metrics.last_state_change = time.time()
            logger.warning(
                "Circuit breaker opened",
                service=self.service_name,
                failure_count=self.failure_count,
                threshold=self.config.failure_threshold,
            )

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "service": self.service_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.config.failure_threshold,
            "success_threshold": self.config.success_threshold,
            "half_open_calls": self.half_open_calls,
            "half_open_max_calls": self.config.half_open_max_calls,
            "is_available": self.state != CircuitState.OPEN,
            "last_failure_time": self.last_failure_time,
            "metrics": {
                "total_calls": self.metrics.total_calls,
                "successful_calls": self.metrics.successful_calls,
                "failed_calls": self.metrics.failed_calls,
                "failure_rate": round(self.metrics.failure_rate, 4),
                "average_response_time": round(self.metrics.average_response_time, 3),
                "circuit_open_count": self.metrics.circuit_open_count,
            }
        }

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time = None
        self.metrics = CircuitBreakerMetrics()
        logger.info("Circuit breaker manually reset", service=self.service_name)


class ServiceClient:
    """
    HTTP service client with circuit breaker protection.

    Provides a wrapper around httpx with circuit breaker functionality
    for calling external services.
    """

    def __init__(
        self,
        service_name: str,
        base_url: str,
        timeout_seconds: int = 30,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize service client.

        Args:
            service_name: Name of the service for logging
            base_url: Base URL for the service
            timeout_seconds: Request timeout in seconds
            circuit_breaker_config: Optional circuit breaker configuration
        """
        self.service_name = service_name
        self.base_url = base_url.rstrip('/')
        self.timeout_seconds = timeout_seconds

        # Create circuit breaker with default config if none provided
        config = circuit_breaker_config or CircuitBreakerConfig()
        self.circuit_breaker = CircuitBreaker(
            service_name=service_name,
            config=config
        )

        # Create HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_seconds
        )

        logger.info(
            "Service client initialized",
            service_name=service_name,
            base_url=base_url,
            timeout_seconds=timeout_seconds
        )

    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make GET request with circuit breaker protection.

        Args:
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            Response data as dictionary
        """
        return await self._make_request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make POST request with circuit breaker protection.

        Args:
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            Response data as dictionary
        """
        return await self._make_request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make PUT request with circuit breaker protection.

        Args:
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            Response data as dictionary
        """
        return await self._make_request("PUT", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make DELETE request with circuit breaker protection.

        Args:
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            Response data as dictionary
        """
        return await self._make_request("DELETE", endpoint, **kwargs)

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request with circuit breaker protection.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            Response data as dictionary

        Raises:
            ExternalServiceError: If request fails
        """
        @self.circuit_breaker
        async def protected_request():
            url = f"{self.base_url}/{endpoint.lstrip('/')}"

            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()

                # Try to parse JSON response
                try:
                    return response.json()
                except Exception:
                    # Return raw response if not JSON
                    return {"data": response.text, "status_code": response.status_code}

            except httpx.HTTPStatusError as e:
                logger.error(
                    "HTTP error in service call",
                    service_name=self.service_name,
                    method=method,
                    endpoint=endpoint,
                    status_code=e.response.status_code,
                    error=str(e)
                )
                raise ExternalServiceError(
                    service_name=self.service_name,
                    message=f"HTTP {e.response.status_code}: {e.response.text}",
                    status_code=e.response.status_code
                )
            except httpx.RequestError as e:
                logger.error(
                    "Request error in service call",
                    service_name=self.service_name,
                    method=method,
                    endpoint=endpoint,
                    error=str(e)
                )
                raise ExternalServiceError(
                    service_name=self.service_name,
                    message=f"Request failed: {str(e)}"
                )
            except Exception as e:
                logger.error(
                    "Unexpected error in service call",
                    service_name=self.service_name,
                    method=method,
                    endpoint=endpoint,
                    error=str(e)
                )
                raise ExternalServiceError(
                    service_name=self.service_name,
                    message=f"Unexpected error: {str(e)}"
                )

        try:
            return await protected_request()
        except ServiceUnavailableError as e:
            # Re-raise circuit breaker errors as external service errors
            raise ExternalServiceError(
                service_name=self.service_name,
                message=f"Service unavailable: {str(e)}"
            )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def health_check(self) -> bool:
        """
        Perform health check on the service.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Try a simple GET request to health endpoint
            await self.get("/health", timeout=5.0)
            return True
        except Exception as e:
            logger.warning(
                "Health check failed",
                service_name=self.service_name,
                error=str(e)
            )
            return False

    def get_circuit_status(self) -> Dict[str, Any]:
        """
        Get circuit breaker status.

        Returns:
            Circuit breaker status information
        """
        return self.circuit_breaker.get_status()
