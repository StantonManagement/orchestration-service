"""
Circuit breaker implementation for external service calls.
"""
import time
from enum import Enum
from typing import Callable, Any
import structlog
from app.core.exceptions import ServiceUnavailableError

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for external service calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 300,
        service_name: str = "Unknown Service",
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.service_name = service_name
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap functions with circuit breaker."""

        async def wrapper(*args, **kwargs) -> Any:
            return await self.call_async(func, *args, **kwargs)

        return wrapper

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(
                    "Circuit breaker transitioning to half-open",
                    service=self.service_name,
                )
            else:
                raise ServiceUnavailableError(
                    self.service_name,
                    f"Circuit breaker is OPEN for {self.service_name}",
                )

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt circuit reset."""
        return (
            self.last_failure_time
            and time.time() - self.last_failure_time >= self.timeout
        )

    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker reset to closed", service=self.service_name)
        self.failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker opened",
                service=self.service_name,
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
            )

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "service": self.service_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "is_available": self.state != CircuitState.OPEN,
        }
