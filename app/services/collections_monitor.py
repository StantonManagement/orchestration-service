"""
Collections Monitor service client for tenant context retrieval.
"""
from typing import Dict, Any
import re
import structlog
from app.config import settings
from app.core.circuit_breaker import ServiceClient, CircuitBreakerConfig
from app.core.retry import get_external_service_retry_config, create_async_retry_decorator
from app.core.exceptions import ServiceUnavailableError, ExternalServiceError

logger = structlog.get_logger(__name__)


class CollectionsMonitorClient:
    """Client for Collections Monitor service integration."""

    def __init__(self):
        self.service_name = "Collections Monitor"

        # Create circuit breaker configuration
        circuit_config = CircuitBreakerConfig(
            failure_threshold=getattr(settings, 'monitor_failure_threshold', 5),
            timeout=getattr(settings, 'circuit_breaker_timeout', 60),
            success_threshold=3,
            half_open_max_calls=5,
        )

        # Create service client with circuit breaker
        self.service_client = ServiceClient(
            service_name=self.service_name,
            base_url=settings.monitor_url,
            timeout_seconds=getattr(settings, 'monitor_timeout', 30),
            circuit_breaker_config=circuit_config,
        )

        # Create retry decorator
        retry_config = get_external_service_retry_config()
        self.retry_decorator = create_async_retry_decorator(
            config=retry_config,
            service_name=self.service_name,
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

    @self.retry_decorator
    async def get_tenant_context(self, tenant_id: str) -> Dict[str, Any]:
        """
        Retrieve tenant context from Collections Monitor service.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Dictionary containing tenant context data

        Raises:
            ServiceUnavailableError: If service is unavailable or circuit is open
            ExternalServiceError: For service-related errors
            ValueError: If tenant_id is invalid
        """
        self._validate_tenant_id(tenant_id)

        try:
            logger.info(
                "Fetching tenant context",
                service=self.service_name,
                tenant_id=tenant_id,
            )

            response_data = await self.service_client.get(f"monitor/tenant/{tenant_id}")

            logger.info(
                "Successfully retrieved tenant context",
                service=self.service_name,
                tenant_id=tenant_id,
                data_keys=list(response_data.keys()) if response_data else [],
            )

            return response_data

        except Exception as e:
            logger.error(
                "Failed to retrieve tenant context",
                service=self.service_name,
                tenant_id=tenant_id,
                error=str(e),
            )
            raise ExternalServiceError(
                service_name=self.service_name,
                message=f"Failed to retrieve tenant context: {str(e)}"
            )

    async def health_check(self) -> bool:
        """
        Check if Collections Monitor service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            logger.info(
                "Performing health check",
                service=self.service_name,
            )

            return await self.service_client.health_check()

        except Exception as e:
            logger.error(
                "Health check failed",
                service=self.service_name,
                error=str(e),
            )
            return False

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """
        Get current circuit breaker status.

        Returns:
            Circuit breaker status information
        """
        return self.service_client.get_circuit_status()

    async def close(self):
        """Close the service client."""
        await self.service_client.close()

    