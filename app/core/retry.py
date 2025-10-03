"""
Retry logic with exponential backoff using tenacity.
"""
import asyncio
import random
from typing import Any, Callable, Optional, Union, List, Type
from dataclasses import dataclass
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception_type,
    RetryCallState,
    before_sleep_log,
)

logger = structlog.get_logger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (
        ConnectionError,
        TimeoutError,
        OSError,
        Exception,
    )
    stop_exceptions: tuple = ()


def _add_jitter(delay: float, jitter_factor: float = 0.1) -> float:
    """Add random jitter to delay to prevent thundering herd."""
    if jitter_factor > 0:
        jitter_amount = delay * jitter_factor * (random.random() * 2 - 1)
        return max(0.1, delay + jitter_amount)
    return delay


def create_retry_decorator(
    config: Optional[RetryConfig] = None,
    service_name: str = "Unknown Service",
) -> Callable:
    """Create a retry decorator with exponential backoff and jitter."""

    config = config or RetryConfig()

    def _before_sleep(retry_state: RetryCallState) -> None:
        """Log retry attempts."""
        logger.warning(
            "Retrying failed operation",
            service=service_name,
            attempt=retry_state.attempt_number,
            max_attempts=config.max_attempts,
            delay=retry_state.next_action.sleep,
            exception=str(retry_state.outcome.exception()),
        )

    wait_strategy = wait_exponential(
        multiplier=config.exponential_base,
        min=config.base_delay,
        max=config.max_delay,
    )

    return retry(
        stop=stop_after_attempt(config.max_attempts),
        wait=wait_strategy,
        retry=retry_if_exception_type(config.retryable_exceptions),
        before_sleep=_before_sleep,
        reraise=True,
    )


def create_async_retry_decorator(
    config: Optional[RetryConfig] = None,
    service_name: str = "Unknown Service",
) -> Callable:
    """Create a retry decorator specifically for async functions."""

    config = config or RetryConfig()

    def _before_sleep(retry_state: RetryCallState) -> None:
        """Log retry attempts."""
        logger.warning(
            "Retrying failed async operation",
            service=service_name,
            attempt=retry_state.attempt_number,
            max_attempts=config.max_attempts,
            delay=retry_state.next_action.sleep,
            exception=str(retry_state.outcome.exception()),
        )

    # Use wait_random_exponential for better jitter distribution
    wait_strategy = wait_random_exponential(
        multiplier=config.base_delay,
        max=config.max_delay,
    )

    return retry(
        stop=stop_after_attempt(config.max_attempts),
        wait=wait_strategy,
        retry=retry_if_exception_type(config.retryable_exceptions),
        before_sleep=_before_sleep,
        reraise=True,
    )


def retry_with_circuit_breaker(
    circuit_breaker,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> Callable:
    """Combine retry logic with circuit breaker."""

    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
    )

    def decorator(func: Callable) -> Callable:
        retry_decorator = create_retry_decorator(config, circuit_breaker.service_name)

        @retry_decorator
        @circuit_breaker
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Service-specific retry configurations
def get_default_retry_config() -> RetryConfig:
    """Get default retry configuration for most services."""
    return RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True,
    )


def get_database_retry_config() -> RetryConfig:
    """Get retry configuration optimized for database operations."""
    return RetryConfig(
        max_attempts=5,
        base_delay=0.5,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True,
        retryable_exceptions=(
            ConnectionError,
            TimeoutError,
            OSError,
        ),
    )


def get_external_service_retry_config() -> RetryConfig:
    """Get retry configuration optimized for external services."""
    return RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        max_delay=60.0,
        exponential_base=2.5,
        jitter=True,
        retryable_exceptions=(
            ConnectionError,
            TimeoutError,
            OSError,
        ),
    )


# Backward compatibility
def create_retry_wrapper(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    service_name: str = "Unknown Service",
) -> Callable:
    """Create a retry decorator with exponential backoff (backward compatibility)."""

    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=min_wait,
        max_delay=max_wait,
    )

    return create_retry_decorator(config, service_name)
