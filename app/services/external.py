"""External service integration clients."""

import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class CircuitBreaker:
    """Simple circuit breaker implementation."""

    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure = None
        self.state = "closed"  # closed, open, half_open

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        import time
        return time.time() - (self.last_failure or 0) > self.timeout_seconds

    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = "closed"

    def _on_failure(self):
        """Handle failed call."""
        import time
        self.failure_count += 1
        self.last_failure = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class CollectionsMonitorClient:
    """Client for Collections Monitor service integration."""

    def __init__(self):
        self.base_url = str(settings.collections_monitor_url)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            timeout_seconds=settings.circuit_breaker_timeout_seconds
        )

    @retry(
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.retry_base_delay_seconds,
            min=4,
            max=10
        )
    )
    async def get_tenant(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant context information."""
        logger.info("Getting tenant context", tenant_id=tenant_id)

        async with httpx.AsyncClient(timeout=30.0) as client:
            return await self.circuit_breaker.call(
                client.get,
                f"{self.base_url}/monitor/tenant/{tenant_id}"
            )

    @retry(
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.retry_base_delay_seconds,
            min=4,
            max=10
        )
    )
    async def get_delinquent_tenants(
        self,
        min_days_late: Optional[int] = None,
        min_amount_owed: Optional[float] = None,
        property_name: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get list of delinquent tenants."""
        logger.info("Getting delinquent tenants", page=page, page_size=page_size)

        params = {
            "page": page,
            "page_size": min(page_size, 100)
        }

        if min_days_late is not None:
            params["min_days_late"] = min_days_late
        if min_amount_owed is not None:
            params["min_amount_owed"] = min_amount_owed
        if property_name:
            params["property_name"] = property_name
        if status:
            params["status"] = status

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self.circuit_breaker.call(
                client.get,
                f"{self.base_url}/monitor/delinquent",
                params=params
            )
            return response.json()

    @retry(
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.retry_base_delay_seconds,
            min=4,
            max=10
        )
    )
    async def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        logger.info("Getting monitoring stats")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self.circuit_breaker.call(
                client.get,
                f"{self.base_url}/monitor/stats"
            )
            return response.json()

    async def health_check(self) -> bool:
        """Check service health."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


class SMSAgentClient:
    """Client for SMS Agent service integration."""

    def __init__(self):
        self.base_url = str(settings.sms_agent_url)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            timeout_seconds=settings.circuit_breaker_timeout_seconds
        )

    @retry(
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.retry_base_delay_seconds,
            min=4,
            max=10
        )
    )
    async def send_sms(self, to: str, body: str, conversation_id: str) -> Dict[str, Any]:
        """Send SMS message."""
        logger.info("Sending SMS", to=to, conversation_id=conversation_id)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self.circuit_breaker.call(
                client.post,
                f"{self.base_url}/sms/send",
                json={
                    "to": to,
                    "body": body,
                    "conversation_id": conversation_id
                }
            )
            response.raise_for_status()
            return response.json()

    @retry(
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.retry_base_delay_seconds,
            min=4,
            max=10
        )
    )
    async def get_conversation(
        self,
        phone_number: str,
        page: int = 1,
        limit: int = 20,
        offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get conversation history."""
        logger.info("Getting conversation", phone_number=phone_number)

        params = {"page": page, "limit": min(limit, 100)}
        if offset is not None:
            params["offset"] = offset

        encoded_phone = quote(phone_number, safe='')

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self.circuit_breaker.call(
                client.get,
                f"{self.base_url}/conversations/{encoded_phone}",
                params=params
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> bool:
        """Check service health."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


class NotificationServiceClient:
    """Client for Notification service integration."""

    def __init__(self):
        self.base_url = str(settings.notification_service_url)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            timeout_seconds=settings.circuit_breaker_timeout_seconds
        )

    @retry(
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.retry_base_delay_seconds,
            min=4,
            max=10
        )
    )
    async def send_notification(
        self,
        channel: str,
        recipient: str,
        subject: str,
        body: str,
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send notification."""
        logger.info("Sending notification", channel=channel, recipient=recipient, priority=priority)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self.circuit_breaker.call(
                client.post,
                f"{self.base_url}/notifications/send",
                json={
                    "channel": channel,
                    "recipient": recipient,
                    "content": {"subject": subject, "body": body},
                    "priority": priority,
                    "metadata": metadata or {}
                }
            )
            response.raise_for_status()
            return response.json()

    async def notify_manager(
        self,
        subject: str,
        body: str,
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send notification to manager."""
        return await self.send_notification(
            channel="email",
            recipient=settings.manager_email,
            subject=subject,
            body=body,
            priority=priority,
            metadata=metadata
        )

    async def health_check(self) -> bool:
        """Check service health."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


class ServiceClients:
    """Container for all external service clients."""

    def __init__(self):
        self.collections_monitor = CollectionsMonitorClient()
        self.sms_agent = SMSAgentClient()
        self.notification_service = NotificationServiceClient()

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all external services."""
        health_checks = {
            "collections_monitor": await self.collections_monitor.health_check(),
            "sms_agent": await self.sms_agent.health_check(),
            "notification_service": await self.notification_service.health_check(),
        }

        # Add OpenAI health check
        try:
            import openai
            client = openai.OpenAI(api_key=settings.openai_api_key)
            client.models.list()  # Simple test call
            health_checks["openai"] = True
        except Exception:
            health_checks["openai"] = False

        # Add Supabase health check
        try:
            from supabase import create_client
            supabase = create_client(str(settings.supabase_url), settings.supabase_key)
            supabase.table('health_check').select('id').limit(1).execute()
            health_checks["supabase"] = True
        except Exception:
            health_checks["supabase"] = False

        return health_checks