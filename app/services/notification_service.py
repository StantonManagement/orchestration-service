"""
Notification service for sending manager alerts and workflow notifications.
"""
import httpx
from typing import Dict, Any, Optional
import structlog

from app.config import settings
from app.core.circuit_breaker import CircuitBreaker
from app.core.exceptions import ServiceUnavailableError

logger = structlog.get_logger(__name__)


class NotificationService:
    """Service for sending notifications to managers and other services."""

    def __init__(self):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.notification_failure_threshold,
            timeout=settings.circuit_breaker_timeout,
            service_name="Notification Service",
        )

    async def send_approval_notification(
        self,
        queue_id: str,
        tenant_id: str,
        confidence_score: float,
        response_text: str,
        tenant_message: str,
        created_at: str,
        action_links: Dict[str, str],
    ) -> bool:
        """
        Send notification to managers when approval is required.

        Args:
            queue_id: Queue entry ID
            tenant_id: Tenant identifier
            confidence_score: AI confidence score
            response_text: Generated AI response
            tenant_message: Original tenant message
            created_at: Queue creation timestamp
            action_links: Direct action links for approval

        Returns:
            True if successful, False otherwise
        """
        notification_data = {
            "type": "approval_required",
            "priority": "medium",
            "queue_id": queue_id,
            "tenant_id": tenant_id,
            "confidence_score": confidence_score,
            "response_text": response_text,
            "tenant_message": tenant_message,
            "created_at": created_at,
            "action_links": action_links,
            "subject": f"Approval Required: Tenant {tenant_id} Response (Confidence: {confidence_score:.0%})",
        }

        return await self._send_notification(notification_data)

    async def send_escalation_notification(
        self,
        queue_id: str,
        tenant_id: str,
        confidence_score: float,
        response_text: str,
        escalation_reason: Optional[str],
        escalated_by: str,
        escalated_at: Optional[str],
        original_message: str,
    ) -> bool:
        """
        Send notification when response is escalated.

        Args:
            queue_id: Queue entry ID
            tenant_id: Tenant identifier
            confidence_score: AI confidence score
            response_text: Generated AI response
            escalation_reason: Reason for escalation
            escalated_by: Who escalated the response
            escalated_at: When escalation occurred
            original_message: Original tenant message

        Returns:
            True if successful, False otherwise
        """
        notification_data = {
            "type": "escalation",
            "priority": "high",
            "queue_id": queue_id,
            "tenant_id": tenant_id,
            "confidence_score": confidence_score,
            "response_text": response_text,
            "escalation_reason": escalation_reason,
            "escalated_by": escalated_by,
            "escalated_at": escalated_at,
            "original_message": original_message,
            "subject": f"ESCALATION: Tenant {tenant_id} Response (Confidence: {confidence_score:.0%})",
        }

        return await self._send_notification(notification_data)

    async def send_auto_approval_notification(
        self,
        workflow_id: str,
        tenant_id: str,
        confidence_score: float,
        response_text: str,
        auto_approved_at: str,
    ) -> bool:
        """
        Send notification when response is auto-approved.

        Args:
            workflow_id: Workflow instance ID
            tenant_id: Tenant identifier
            confidence_score: AI confidence score
            response_text: Auto-approved response
            auto_approved_at: When auto-approval occurred

        Returns:
            True if successful, False otherwise
        """
        notification_data = {
            "type": "auto_approval",
            "priority": "low",
            "workflow_id": workflow_id,
            "tenant_id": tenant_id,
            "confidence_score": confidence_score,
            "response_text": response_text,
            "auto_approved_at": auto_approved_at,
            "subject": f"Auto-Approved: Tenant {tenant_id} Response (Confidence: {confidence_score:.0%})",
        }

        return await self._send_notification(notification_data)

    async def send_timeout_notification(
        self,
        queue_id: str,
        tenant_id: str,
        confidence_score: float,
        response_text: str,
        timeout_hours: int,
        auto_escalated_at: str,
    ) -> bool:
        """
        Send notification when approval times out and is auto-escalated.

        Args:
            queue_id: Queue entry ID
            tenant_id: Tenant identifier
            confidence_score: AI confidence score
            response_text: Original response
            timeout_hours: Hours before timeout
            auto_escalated_at: When auto-escalation occurred

        Returns:
            True if successful, False otherwise
        """
        notification_data = {
            "type": "approval_timeout",
            "priority": "high",
            "queue_id": queue_id,
            "tenant_id": tenant_id,
            "confidence_score": confidence_score,
            "response_text": response_text,
            "timeout_hours": timeout_hours,
            "auto_escalated_at": auto_escalated_at,
            "subject": f"TIMEOUT: Tenant {tenant_id} Approval Expired ({timeout_hours}h)",
        }

        return await self._send_notification(notification_data)

    async def send_workflow_status_notification(
        self,
        workflow_id: str,
        tenant_id: str,
        status: str,
        status_details: Dict[str, Any],
    ) -> bool:
        """
        Send workflow status change notifications.

        Args:
            workflow_id: Workflow instance ID
            tenant_id: Tenant identifier
            status: New workflow status
            status_details: Additional status information

        Returns:
            True if successful, False otherwise
        """
        notification_data = {
            "type": "workflow_status",
            "priority": "medium",
            "workflow_id": workflow_id,
            "tenant_id": tenant_id,
            "status": status,
            "status_details": status_details,
            "subject": f"Workflow Update: Tenant {tenant_id} - {status}",
        }

        return await self._send_notification(notification_data)

    async def _send_notification(self, notification_data: Dict[str, Any]) -> bool:
        """
        Send notification to Notification Service.

        Args:
            notification_data: Notification payload

        Returns:
            True if successful, False otherwise
        """
        try:
            return await self.circuit_breaker.call_async(
                self._send_notification_internal, notification_data
            )
        except ServiceUnavailableError as e:
            logger.error(
                "Notification service unavailable",
                notification_type=notification_data.get("type"),
                queue_id=notification_data.get("queue_id"),
                error=str(e),
            )
            return False

    async def _send_notification_internal(
        self, notification_data: Dict[str, Any]
    ) -> bool:
        """Execute notification sending."""
        url = f"{settings.notification_url}/notifications/send"

        try:
            async with httpx.AsyncClient(
                timeout=settings.notification_timeout
            ) as client:
                logger.info(
                    "Sending notification",
                    service="Notification Service",
                    notification_type=notification_data.get("type"),
                    queue_id=notification_data.get("queue_id"),
                    url=url,
                )

                response = await client.post(url, json=notification_data)
                response.raise_for_status()

                data = response.json()

                logger.info(
                    "Notification sent successfully",
                    service="Notification Service",
                    notification_type=notification_data.get("type"),
                    queue_id=notification_data.get("queue_id"),
                    response_data=data,
                )

                return True

        except httpx.TimeoutException as e:
            logger.error(
                "Timeout sending notification",
                service="Notification Service",
                notification_type=notification_data.get("type"),
                queue_id=notification_data.get("queue_id"),
                timeout=settings.notification_timeout,
                error=str(e),
            )
            raise ServiceUnavailableError(
                "Notification Service",
                f"Request timeout after {settings.notification_timeout} seconds",
            )

        except httpx.ConnectError as e:
            logger.error(
                "Connection error to Notification Service",
                notification_type=notification_data.get("type"),
                queue_id=notification_data.get("queue_id"),
                url=url,
                error=str(e),
            )
            raise ServiceUnavailableError(
                "Notification Service", f"Connection error: {str(e)}"
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error from Notification Service",
                notification_type=notification_data.get("type"),
                queue_id=notification_data.get("queue_id"),
                status_code=e.response.status_code,
                error=str(e),
            )
            if e.response.status_code >= 500:
                raise ServiceUnavailableError(
                    "Notification Service", f"Server error: {e.response.status_code}"
                )
            else:
                # For 4xx errors, log but don't raise ServiceUnavailableError
                logger.warning(
                    "Notification rejected by service",
                    notification_type=notification_data.get("type"),
                    queue_id=notification_data.get("queue_id"),
                    status_code=e.response.status_code,
                    error=str(e),
                )
                return False

        except Exception as e:
            logger.error(
                "Unexpected error sending notification",
                service="Notification Service",
                notification_type=notification_data.get("type"),
                queue_id=notification_data.get("queue_id"),
                error=str(e),
            )
            raise ServiceUnavailableError(
                "Notification Service", f"Unexpected error: {str(e)}"
            )

    async def health_check(self) -> bool:
        """
        Check if Notification Service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            url = f"{settings.notification_url}/health"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                is_healthy = response.status_code == 200

                logger.info(
                    "Notification Service health check",
                    healthy=is_healthy,
                    status_code=response.status_code,
                )

                return is_healthy

        except Exception as e:
            logger.warning("Notification Service health check failed", error=str(e))
            return False

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get the current status of the circuit breaker."""
        return self.circuit_breaker.get_status()
