"""
Retry logic with exponential backoff using tenacity.
"""
import asyncio
from typing import Any, Callable
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = structlog.get_logger(__name__)


def create_retry_wrapper(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    service_name: str = "Unknown Service",
) -> Callable:
    """Create a retry decorator with exponential backoff."""

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(
            (
                ConnectionError,
                TimeoutError,
                OSError,
            )
        ),
        reraise=True,
    )


async def async_retry_wrapper(
    func: Callable,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    service_name: str = "Unknown Service",
    *args,
    **kwargs
) -> Any:
    """Execute async function with retry logic."""
    retry_decorator = create_retry_wrapper(
        max_attempts=max_attempts,
        min_wait=min_wait,
        max_wait=max_wait,
        service_name=service_name,
    )

    # Apply retry decorator to sync wrapper around async function
    @retry_decorator
    def sync_wrapper():
        return asyncio.run(func(*args, **kwargs))

    return sync_wrapper()
