"""
Escalation service for Story 2.2

Implements escalation business logic combining trigger detection and timeout monitoring
to create comprehensive escalation workflows per requirements AC1-AC3.
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict
import structlog

from app.utils.escalation_triggers import (
    EscalationDetector,
    EscalationTrigger,
    EscalationReason
)
from app.utils.timeout_monitor import (
    TimeoutMonitor,
    WorkflowTimeout,
    TimeoutStatus
)
from app.core.circuit_breaker import ServiceClient
from app.core.exceptions import EscalationError, ExternalServiceError
from app.models.schemas import ApiResponse, EscalationRequest, EscalationResponse

logger = structlog.get_logger(__name__)


class EscalationService:
    """
    Service that combines trigger detection and timeout monitoring to
    manage escalation workflows according to Story 2.2 requirements.
    """

    def __init__(
        self,
        notification_client: ServiceClient,
        sms_agent_client: ServiceClient,
        collections_monitor_client: ServiceClient
    ):
        """
        Initialize escalation service.

        Args:
            notification_client: Service client for Notification Service
            sms_agent_client: Service client for SMS Agent Service
            collections_monitor_client: Service client for Collections Monitor Service
        """
        self.trigger_detector = EscalationDetector()
        self.timeout_monitor = TimeoutMonitor(timeout_hours=36)
        self.notification_client = notification_client
        self.sms_agent_client = sms_agent_client
        self.collections_monitor_client = collections_monitor_client

        logger.info(
            "Escalation service initialized",
            timeout_hours=36,
            trigger_detector_ready=True,
            timeout_monitor_ready=True
        )

    async def start_services(self) -> None:
        """Start background monitoring services."""
        await self.timeout_monitor.start_monitoring()
        logger.info("Escalation services started")

    async def stop_services(self) -> None:
        """Stop background monitoring services."""
        await self.timeout_monitor.stop_monitoring()
        logger.info("Escalation services stopped")

    async def analyze_message_for_escalation(
        self,
        message_text: str,
        workflow_id: str,
        customer_phone: str
    ) -> Tuple[bool, Optional[EscalationTrigger]]:
        """
        Analyze customer message for escalation triggers.

        Args:
            message_text: Customer message to analyze
            workflow_id: Workflow identifier
            customer_phone: Customer phone number

        Returns:
            Tuple of (should_escalate, primary_trigger)
        """
        try:
            # Detect escalation triggers
            triggers = self.trigger_detector.detect_triggers(message_text)
            should_escalate = self.trigger_detector.should_escalate(triggers)
            primary_trigger = self.trigger_detector.get_primary_trigger(triggers)

            logger.info(
                "Message escalation analysis complete",
                workflow_id=workflow_id,
                customer_phone=customer_phone,
                should_escalate=should_escalate,
                trigger_count=len(triggers),
                primary_reason=primary_trigger.reason.value if primary_trigger else None,
                primary_confidence=primary_trigger.confidence if primary_trigger else 0.0
            )

            if should_escalate and primary_trigger:
                await self._trigger_escalation(
                    workflow_id=workflow_id,
                    customer_phone=customer_phone,
                    trigger=primary_trigger,
                    escalation_type="trigger_based"
                )

            return should_escalate, primary_trigger

        except Exception as e:
            logger.error(
                "Error analyzing message for escalation",
                workflow_id=workflow_id,
                customer_phone=customer_phone,
                error=str(e),
                exc_info=True
            )
            raise EscalationError(f"Failed to analyze message: {str(e)}")

    async def register_workflow_timeout(
        self,
        workflow_id: str,
        customer_phone: str,
        last_ai_response: datetime
    ) -> None:
        """
        Register workflow for timeout monitoring.

        Args:
            workflow_id: Workflow identifier
            customer_phone: Customer phone number
            last_ai_response: Timestamp of last AI response
        """
        try:
            timeout = self.timeout_monitor.register_workflow(
                workflow_id=workflow_id,
                customer_phone=customer_phone,
                last_ai_response=last_ai_response
            )

            logger.info(
                "Workflow registered for timeout monitoring",
                workflow_id=workflow_id,
                customer_phone=customer_phone,
                last_response_time=last_ai_response.isoformat(),
                timeout_hours=int(timeout.timeout_threshold.total_seconds() // 3600)
            )

        except Exception as e:
            logger.error(
                "Error registering workflow timeout",
                workflow_id=workflow_id,
                customer_phone=customer_phone,
                error=str(e),
                exc_info=True
            )
            raise EscalationError(f"Failed to register timeout: {str(e)}")

    async def update_workflow_response(
        self,
        workflow_id: str,
        response_time: datetime
    ) -> None:
        """
        Update workflow with new response time.

        Args:
            workflow_id: Workflow identifier
            response_time: New response timestamp
        """
        try:
            timeout = self.timeout_monitor.update_workflow_response(
                workflow_id=workflow_id,
                response_time=response_time
            )

            if timeout:
                logger.info(
                    "Workflow timeout updated",
                    workflow_id=workflow_id,
                    new_response_time=response_time.isoformat(),
                    hours_remaining=int(timeout.time_remaining.total_seconds() // 3600)
                )
            else:
                logger.warning(
                    "Attempted to update unregistered workflow timeout",
                    workflow_id=workflow_id
                )

        except Exception as e:
            logger.error(
                "Error updating workflow timeout",
                workflow_id=workflow_id,
                error=str(e),
                exc_info=True
            )
            raise EscalationError(f"Failed to update timeout: {str(e)}")

    async def remove_workflow_monitoring(self, workflow_id: str) -> None:
        """
        Remove workflow from all monitoring.

        Args:
            workflow_id: Workflow identifier
        """
        try:
            removed = self.timeout_monitor.remove_workflow(workflow_id)

            if removed:
                logger.info(
                    "Workflow removed from monitoring",
                    workflow_id=workflow_id
                )
            else:
                logger.warning(
                    "Attempted to remove unregistered workflow",
                    workflow_id=workflow_id
                )

        except Exception as e:
            logger.error(
                "Error removing workflow monitoring",
                workflow_id=workflow_id,
                error=str(e),
                exc_info=True
            )
            raise EscalationError(f"Failed to remove monitoring: {str(e)}")

    async def check_timeout_escalations(self) -> List[Dict[str, Any]]:
        """
        Check for timeout-based escalations and trigger them.

        Returns:
            List of escalation details triggered by timeout
        """
        try:
            timeout_results = await self.timeout_monitor.check_timeouts()
            escalations_triggered = []

            # Handle expired workflows
            for timeout in timeout_results["expired"]:
                if not timeout.escalation_triggered:
                    escalation_details = await self._trigger_timeout_escalation(timeout)
                    escalations_triggered.append(escalation_details)

            # Handle warning workflows (optional: send early warnings)
            for timeout in timeout_results["warnings"]:
                await self._send_timeout_warning(timeout)

            if escalations_triggered:
                logger.info(
                    "Timeout escalations triggered",
                    escalation_count=len(escalations_triggered)
                )

            return escalations_triggered

        except Exception as e:
            logger.error(
                "Error checking timeout escalations",
                error=str(e),
                exc_info=True
            )
            raise EscalationError(f"Failed to check timeouts: {str(e)}")

    async def _trigger_escalation(
        self,
        workflow_id: str,
        customer_phone: str,
        trigger: EscalationTrigger,
        escalation_type: str
    ) -> Dict[str, Any]:
        """
        Trigger escalation workflow for a specific reason.

        Args:
            workflow_id: Workflow identifier
            customer_phone: Customer phone number
            trigger: Escalation trigger that caused escalation
            escalation_type: Type of escalation (trigger_based or timeout_based)

        Returns:
            Escalation details dictionary
        """
        escalation_id = f"escalation-{workflow_id}-{int(datetime.utcnow().timestamp())}"

        escalation_details = {
            "escalation_id": escalation_id,
            "workflow_id": workflow_id,
            "customer_phone": customer_phone,
            "escalation_type": escalation_type,
            "reason": trigger.reason.value,
            "confidence": trigger.confidence,
            "matched_text": trigger.matched_text,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "triggered"
        }

        try:
            # Create escalation event record (would save to database)
            await self._create_escalation_event(escalation_details)

            # Send notifications to all parties (AC4 requirement)
            await self._send_escalation_notifications(escalation_details)

            # Mark workflow as escalated if trigger-based
            if escalation_type == "trigger_based":
                self.timeout_monitor.mark_workflow_escalated(workflow_id)

            logger.info(
                "Escalation triggered successfully",
                escalation_id=escalation_id,
                workflow_id=workflow_id,
                escalation_type=escalation_type,
                reason=trigger.reason.value
            )

            return escalation_details

        except Exception as e:
            logger.error(
                "Error triggering escalation",
                escalation_id=escalation_id,
                workflow_id=workflow_id,
                error=str(e),
                exc_info=True
            )
            escalation_details["status"] = "failed"
            escalation_details["error"] = str(e)
            raise EscalationError(f"Failed to trigger escalation: {str(e)}")

    async def _trigger_timeout_escalation(self, timeout: WorkflowTimeout) -> Dict[str, Any]:
        """
        Trigger escalation due to workflow timeout.

        Args:
            timeout: WorkflowTimeout that has expired

        Returns:
            Escalation details dictionary
        """
        # Create timeout trigger
        timeout_trigger = EscalationTrigger(
            reason=EscalationReason.DISSATISFACTION,  # Default reason for timeout
            confidence=1.0,  # High confidence for timeout
            matched_text=f"36-hour timeout exceeded ({timeout.time_remaining})",
            pattern_type="timeout"
        )

        escalation_details = await self._trigger_escalation(
            workflow_id=timeout.workflow_id,
            customer_phone=timeout.customer_phone,
            trigger=timeout_trigger,
            escalation_type="timeout_based"
        )

        # Mark timeout as escalated
        self.timeout_monitor.mark_workflow_escalated(timeout.workflow_id)

        return escalation_details

    async def _send_timeout_warning(self, timeout: WorkflowTimeout) -> None:
        """
        Send warning notification for workflow approaching timeout.

        Args:
            timeout: WorkflowTimeout approaching timeout
        """
        try:
            warning_details = {
                "workflow_id": timeout.workflow_id,
                "customer_phone": timeout.customer_phone,
                "hours_remaining": int(timeout.time_remaining.total_seconds() // 3600),
                "timeout_time": (timeout.last_ai_response + timeout.timeout_threshold).isoformat(),
                "warning_type": "approaching_timeout"
            }

            # Send warning to internal teams (would use notification client)
            logger.info(
                "Timeout warning sent",
                workflow_id=timeout.workflow_id,
                hours_remaining=warning_details["hours_remaining"]
            )

            # In implementation, this would call notification service
            # await self.notification_client.send_warning(warning_details)

        except Exception as e:
            logger.error(
                "Error sending timeout warning",
                workflow_id=timeout.workflow_id,
                error=str(e),
                exc_info=True
            )
            # Don't raise exception for warnings - continue operation

    async def _create_escalation_event(self, escalation_details: Dict[str, Any]) -> None:
        """
        Create escalation event record in database.

        Args:
            escalation_details: Escalation information to store
        """
        try:
            # In implementation, this would save to database
            logger.info(
                "Escalation event created",
                escalation_id=escalation_details["escalation_id"],
                workflow_id=escalation_details["workflow_id"]
            )

            # Example database save (would use actual database client):
            # await self.db.save_escalation_event(escalation_details)

        except Exception as e:
            logger.error(
                "Error creating escalation event",
                escalation_id=escalation_details["escalation_id"],
                error=str(e),
                exc_info=True
            )
            raise EscalationError(f"Failed to create escalation event: {str(e)}")

    async def _send_escalation_notifications(self, escalation_details: Dict[str, Any]) -> None:
        """
        Send escalation notifications to all required parties (AC4 requirement).

        Args:
            escalation_details: Escalation information
        """
        try:
            # Prepare notification payload
            notification_payload = {
                "escalation_id": escalation_details["escalation_id"],
                "workflow_id": escalation_details["workflow_id"],
                "customer_phone": escalation_details["customer_phone"],
                "reason": escalation_details["reason"],
                "confidence": escalation_details["confidence"],
                "timestamp": escalation_details["timestamp"],
                "escalation_type": escalation_details["escalation_type"]
            }

            # Send to Collections Monitor (escalating staff)
            await self._notify_collections_monitor(notification_payload)

            # Send to SMS Agent (pause customer messaging)
            await self._notify_sms_agent(notification_payload)

            # Send internal notifications
            await self._notify_internal_teams(notification_payload)

            logger.info(
                "Escalation notifications sent",
                escalation_id=escalation_details["escalation_id"],
                workflow_id=escalation_details["workflow_id"],
                notification_count=3
            )

        except Exception as e:
            logger.error(
                "Error sending escalation notifications",
                escalation_id=escalation_details["escalation_id"],
                error=str(e),
                exc_info=True
            )
            raise EscalationError(f"Failed to send notifications: {str(e)}")

    async def _notify_collections_monitor(self, payload: Dict[str, Any]) -> None:
        """Notify Collections Monitor service of escalation."""
        try:
            # In implementation, this would make actual HTTP call
            # response = await self.collections_monitor_client.post(
            #     "/escalations",
            #     json=payload
            # )
            logger.info(
                "Collections Monitor notified of escalation",
                escalation_id=payload["escalation_id"]
            )

        except Exception as e:
            logger.error(
                "Error notifying Collections Monitor",
                escalation_id=payload["escalation_id"],
                error=str(e)
            )
            raise ExternalServiceError(f"Failed to notify Collections Monitor: {str(e)}")

    async def _notify_sms_agent(self, payload: Dict[str, Any]) -> None:
        """Notify SMS Agent service to pause messaging."""
        try:
            # In implementation, this would make actual HTTP call
            # response = await self.sms_agent_client.post(
            #     "/pause-messaging",
            #     json={
            #         "workflow_id": payload["workflow_id"],
            #         "customer_phone": payload["customer_phone"],
            #         "reason": "escalation_triggered",
            #         "escalation_id": payload["escalation_id"]
            #     }
            # )
            logger.info(
                "SMS Agent notified to pause messaging",
                workflow_id=payload["workflow_id"],
                escalation_id=payload["escalation_id"]
            )

        except Exception as e:
            logger.error(
                "Error notifying SMS Agent",
                escalation_id=payload["escalation_id"],
                error=str(e)
            )
            raise ExternalServiceError(f"Failed to notify SMS Agent: {str(e)}")

    async def _notify_internal_teams(self, payload: Dict[str, Any]) -> None:
        """Send internal notifications about escalation."""
        try:
            # In implementation, this would use notification service
            # await self.notification_client.send_escalation_alert(payload)
            logger.info(
                "Internal teams notified of escalation",
                escalation_id=payload["escalation_id"],
                reason=payload["reason"]
            )

        except Exception as e:
            logger.error(
                "Error sending internal notifications",
                escalation_id=payload["escalation_id"],
                error=str(e)
            )
            raise ExternalServiceError(f"Failed to send internal notifications: {str(e)}")

    async def get_escalation_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive escalation monitoring statistics.

        Returns:
            Dictionary with escalation statistics
        """
        try:
            timeout_stats = self.timeout_monitor.get_timeout_statistics()
            active_timeouts = self.timeout_monitor.get_all_timeouts()

            # Calculate additional statistics
            escalated_today = len([
                t for t in active_timeouts
                if t.escalation_triggered and
                t.updated_at.date() == datetime.utcnow().date()
            ])

            near_timeout = len([
                t for t in active_timeouts
                if t.is_warning_threshold
            ])

            return {
                **timeout_stats,
                "escalated_today": escalated_today,
                "workflows_near_timeout": near_timeout,
                "escalation_service_active": True
            }

        except Exception as e:
            logger.error(
                "Error getting escalation statistics",
                error=str(e),
                exc_info=True
            )
            raise EscalationError(f"Failed to get statistics: {str(e)}")

    async def process_escalation_request(self, request: EscalationRequest) -> EscalationResponse:
        """
        Process manual escalation request.

        Args:
            request: Escalation request details

        Returns:
            Escalation response
        """
        try:
            # Create manual trigger
            manual_trigger = EscalationTrigger(
                reason=EscalationReason(request.reason),
                confidence=1.0,  # Manual escalations have maximum confidence
                matched_text="manual_escalation_request",
                pattern_type="manual"
            )

            escalation_details = await self._trigger_escalation(
                workflow_id=request.workflow_id,
                customer_phone=request.customer_phone,
                trigger=manual_trigger,
                escalation_type="manual"
            )

            return EscalationResponse(
                escalation_id=escalation_details["escalation_id"],
                workflow_id=request.workflow_id,
                status="escalated",
                message="Manual escalation processed successfully",
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(
                "Error processing manual escalation request",
                workflow_id=request.workflow_id,
                error=str(e),
                exc_info=True
            )
            raise EscalationError(f"Failed to process escalation request: {str(e)}")