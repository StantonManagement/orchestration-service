"""
Collections Monitor service client for tenant context retrieval.
"""
import httpx
from typing import Dict, Any
import re
import structlog
from app.config import settings
from app.core.circuit_breaker import CircuitBreaker
from app.core.exceptions import ServiceUnavailableError

logger = structlog.get_logger(__name__)


class CollectionsMonitorClient:
    """Client for Collections Monitor service integration."""

    def __init__(self):
        self.base_url = settings.monitor_url
        self.timeout = settings.monitor_timeout
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.monitor_failure_threshold,
            timeout=settings.circuit_breaker_timeout,
            service_name="Collections Monitor",
        )

    def _validate_tenant_id(self, tenant_id: str) -> None:
        """
        Validate tenant_id parameter.

        Args:
            tenant_id: Tenant ID to validate

        Raises:
            ValueError: If tenant_id is invalid
        """
        if not isinstance(tenant_id, str):
            raise ValueError("Tenant ID must be a string")

        if not tenant_id:
            raise ValueError("Tenant ID cannot be empty")

        # Allow alphanumeric, hyphens, and underscores, reasonable length
        if not re.match(r"^[a-zA-Z0-9_-]{1,50}$", tenant_id):
            raise ValueError("Tenant ID contains invalid characters or is too long")

        logger.info("Tenant ID validated", tenant_id=tenant_id)

    async def get_tenant_context(self, tenant_id: str) -> Dict[str, Any]:
        """
        Retrieve tenant context from Collections Monitor service.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Dictionary containing tenant context data

        Raises:
            ServiceUnavailableError: If service is unavailable or circuit is open
            httpx.HTTPError: For HTTP-related errors
            ValueError: If tenant_id is invalid
        """
        self._validate_tenant_id(tenant_id)

        return await self.circuit_breaker.call_async(
            self._get_tenant_context_with_retry, tenant_id
        )

    async def _get_tenant_context_with_retry(self, tenant_id: str) -> Dict[str, Any]:
        """Execute tenant context retrieval with retry logic."""
        url = f"{self.base_url}/monitor/tenant/{tenant_id}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(
                    "Fetching tenant context",
                    service="Collections Monitor",
                    tenant_id=tenant_id,
                    url=url,
                )

                response = await client.get(url)
                response.raise_for_status()

                data = response.json()
                logger.info(
                    "Successfully retrieved tenant context",
                    service="Collections Monitor",
                    tenant_id=tenant_id,
                    data_keys=list(data.keys())
                    if isinstance(data, dict)
                    else "non-dict",
                )

                return data

        except httpx.TimeoutException as e:
            logger.error(
                "Timeout retrieving tenant context",
                service="Collections Monitor",
                tenant_id=tenant_id,
                timeout=self.timeout,
                error=str(e),
            )
            raise ServiceUnavailableError(
                "Collections Monitor", f"Request timeout after {self.timeout} seconds"
            )

        except httpx.ConnectError as e:
            logger.error(
                "Connection error to Collections Monitor",
                tenant_id=tenant_id,
                url=url,
                error=str(e),
            )
            raise ServiceUnavailableError(
                "Collections Monitor", f"Connection error: {str(e)}"
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error from Collections Monitor",
                tenant_id=tenant_id,
                status_code=e.response.status_code,
                error=str(e),
            )
            if e.response.status_code >= 500:
                raise ServiceUnavailableError(
                    "Collections Monitor", f"Server error: {e.response.status_code}"
                )
            else:
                raise  # Re-raise 4xx errors as-is

        except Exception as e:
            logger.error(
                "Unexpected error retrieving tenant context",
                service="Collections Monitor",
                tenant_id=tenant_id,
                error=str(e),
            )
            raise ServiceUnavailableError(
                "Collections Monitor", f"Unexpected error: {str(e)}"
            )

    async def health_check(self) -> bool:
        """
        Check if Collections Monitor service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Use a simple health check endpoint or just try to connect
            url = f"{self.base_url}/health"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                is_healthy = response.status_code == 200

                logger.info(
                    "Collections Monitor health check",
                    healthy=is_healthy,
                    status_code=response.status_code,
                )

                return is_healthy

        except Exception as e:
            logger.warning("Collections Monitor health check failed", error=str(e))
            return False

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get the current status of the circuit breaker."""
        return self.circuit_breaker.get_status()
