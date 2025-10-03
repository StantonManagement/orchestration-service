"""
Approval workflow service for confidence-based routing and manager approval processing.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID
import structlog

from app.config import settings
from app.models.ai_response import AIResponse, AIResponseQueue, ApprovalAuditLog
from app.services.sms_agent import SMSAgentClient
from app.core.circuit_breaker import CircuitBreaker
from app.core.exceptions import ServiceUnavailableError

logger = structlog.get_logger(__name__)


class ApprovalService:
    """Service for managing approval workflow and confidence-based routing."""

    def __init__(self):
        self.sms_client = SMSAgentClient()
        self.notification_service_circuit_breaker = CircuitBreaker(
            failure_threshold=settings.notification_failure_threshold,
            timeout=settings.circuit_breaker_timeout,
            service_name="Notification Service",
        )

        # In-memory storage for demo purposes - in production, use Supabase
        self._approval_queue: Dict[UUID, AIResponseQueue] = {}
        self._audit_logs: List[ApprovalAuditLog] = []

    def route_response_by_confidence(
        self, ai_response: AIResponse, workflow_id: UUID
    ) -> str:
        """
        Route AI response based on confidence score.

        Args:
            ai_response: Generated AI response with confidence score
            workflow_id: Workflow instance ID

        Returns:
            Action: 'auto_send', 'queue_for_approval', or 'escalate'
        """
        confidence_score = float(ai_response.confidence_score)

        if confidence_score > settings.auto_approval_threshold:
            return "auto_send"
        elif confidence_score >= settings.escalation_threshold:
            return "queue_for_approval"
        else:
            return "escalate"

    async def create_approval_queue_entry(
        self,
        workflow_id: UUID,
        tenant_id: str,
        phone_number: str,
        tenant_message: str,
        ai_response: AIResponse,
    ) -> AIResponseQueue:
        """
        Create an entry in the approval queue for manager review.

        Args:
            workflow_id: Workflow instance ID
            tenant_id: Tenant identifier
            phone_number: Tenant phone number
            tenant_message: Original SMS from tenant
            ai_response: Generated AI response

        Returns:
            Created approval queue entry
        """
        queue_entry = AIResponseQueue(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            phone_number=phone_number,
            tenant_message=tenant_message,
            ai_response=ai_response.response_text,
            confidence_score=ai_response.confidence_score,
            status="pending",
        )

        # Store in memory (in production, use Supabase)
        self._approval_queue[queue_entry.id] = queue_entry

        logger.info(
            "Created approval queue entry",
            queue_id=str(queue_entry.id),
            workflow_id=str(workflow_id),
            tenant_id=tenant_id,
            confidence_score=float(ai_response.confidence_score),
            correlation_id=str(workflow_id),
        )

        # Notify managers for approval
        await self._notify_managers_for_approval(queue_entry)

        return queue_entry

    async def process_approval_action(
        self,
        queue_id: UUID,
        action: str,
        manager_id: str,
        modified_text: Optional[str] = None,
        escalation_reason: Optional[str] = None,
    ) -> bool:
        """
        Process manager approval action (approve/modify/escalate).

        Args:
            queue_id: Queue entry ID
            action: Manager action ('approve', 'modify', 'escalate')
            manager_id: Manager ID
            modified_text: Modified response text (for modify action)
            escalation_reason: Reason for escalation (for escalate action)

        Returns:
            True if successful, False otherwise
        """
        if queue_id not in self._approval_queue:
            logger.error(
                "Queue entry not found",
                queue_id=str(queue_id),
                action=action,
                manager_id=manager_id,
            )
            return False

        queue_entry = self._approval_queue[queue_id]

        if queue_entry.status != "pending":
            logger.warning(
                "Queue entry already processed",
                queue_id=str(queue_id),
                current_status=queue_entry.status,
                requested_action=action,
            )
            return False

        # Validate action
        valid_actions = ["approve", "modify", "escalate"]
        if action not in valid_actions:
            logger.error(
                "Invalid approval action",
                queue_id=str(queue_id),
                action=action,
                valid_actions=valid_actions,
            )
            return False

        # Update queue entry
        queue_entry.approval_action = action
        queue_entry.actioned_by = manager_id
        queue_entry.actioned_at = datetime.utcnow()

        final_response = queue_entry.ai_response
        original_response = queue_entry.ai_response

        if action == "approve":
            queue_entry.status = "approved"
            final_response = queue_entry.ai_response

        elif action == "modify":
            if not modified_text:
                logger.error(
                    "Modified text required for modify action",
                    queue_id=str(queue_id),
                    manager_id=manager_id,
                )
                return False
            queue_entry.status = "modified"
            queue_entry.modified_response = modified_text
            final_response = modified_text

        elif action == "escalate":
            queue_entry.status = "escalated"
            final_response = queue_entry.ai_response  # Original response for escalation

        # Create audit log entry
        audit_log = ApprovalAuditLog(
            response_queue_id=queue_id,
            action=action,
            original_response=original_response,
            final_response=final_response,
            reason=escalation_reason,
            approved_by=manager_id,
        )
        self._audit_logs.append(audit_log)

        logger.info(
            "Processed approval action",
            queue_id=str(queue_id),
            action=action,
            manager_id=manager_id,
            final_response_length=len(final_response),
            correlation_id=str(queue_id),
        )

        # Send approved/modified response
        if action in ["approve", "modify"]:
            await self._send_approved_response(queue_entry)
        elif action == "escalate":
            await self._send_escalation_notification(queue_entry, escalation_reason)

        return True

    async def _send_approved_response(self, queue_entry: AIResponseQueue) -> bool:
        """
        Send approved response to tenant via SMS Agent.

        Args:
            queue_entry: Approval queue entry

        Returns:
            True if successful, False otherwise
        """
        try:
            response_text = queue_entry.modified_response or queue_entry.ai_response

            message_id = await self.sms_client.send_sms(
                phone_number=queue_entry.phone_number, message=response_text
            )

            logger.info(
                "Approved response sent via SMS",
                queue_id=str(queue_entry.id),
                tenant_id=queue_entry.tenant_id,
                phone_number=queue_entry.phone_number,
                message_id=message_id,
                correlation_id=str(queue_entry.id),
            )

            # Update workflow status would happen here in production
            # await self.workflow_service.update_status(queue_entry.workflow_id, "sent")

            return True

        except ServiceUnavailableError as e:
            logger.error(
                "Failed to send approved response",
                queue_id=str(queue_entry.id),
                error=str(e),
                correlation_id=str(queue_entry.id),
            )
            return False

    async def _notify_managers_for_approval(self, queue_entry: AIResponseQueue) -> bool:
        """
        Notify managers when response requires approval.

        Args:
            queue_entry: Approval queue entry

        Returns:
            True if successful, False otherwise
        """
        try:
            notification_data = {
                "type": "approval_required",
                "queue_id": str(queue_entry.id),
                "tenant_id": queue_entry.tenant_id,
                "confidence_score": float(queue_entry.confidence_score),
                "response_text": queue_entry.ai_response,
                "tenant_message": queue_entry.tenant_message,
                "created_at": queue_entry.created_at.isoformat(),
                "action_links": {
                    "approve": f"/api/v1/orchestrate/approve-response?action=approve&queue_id={queue_entry.id}",
                    "modify": f"/api/v1/orchestrate/approve-response?action=modify&queue_id={queue_entry.id}",
                    "escalate": f"/api/v1/orchestrate/approve-response?action=escalate&queue_id={queue_entry.id}",
                },
            }

            await self.notification_service_circuit_breaker.call_async(
                self._send_notification_internal, notification_data
            )

            logger.info(
                "Managers notified for approval",
                queue_id=str(queue_entry.id),
                tenant_id=queue_entry.tenant_id,
                confidence_score=float(queue_entry.confidence_score),
                correlation_id=str(queue_entry.id),
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to notify managers for approval",
                queue_id=str(queue_entry.id),
                error=str(e),
                correlation_id=str(queue_entry.id),
            )
            return False

    async def _send_escalation_notification(
        self, queue_entry: AIResponseQueue, escalation_reason: Optional[str]
    ) -> bool:
        """
        Send escalation notification to managers.

        Args:
            queue_entry: Approval queue entry
            escalation_reason: Reason for escalation

        Returns:
            True if successful, False otherwise
        """
        try:
            notification_data = {
                "type": "escalation",
                "queue_id": str(queue_entry.id),
                "tenant_id": queue_entry.tenant_id,
                "confidence_score": float(queue_entry.confidence_score),
                "response_text": queue_entry.ai_response,
                "escalation_reason": escalation_reason,
                "escalated_by": queue_entry.actioned_by,
                "escalated_at": queue_entry.actioned_at.isoformat()
                if queue_entry.actioned_at
                else None,
                "original_message": queue_entry.tenant_message,
            }

            await self.notification_service_circuit_breaker.call_async(
                self._send_notification_internal, notification_data
            )

            logger.info(
                "Escalation notification sent",
                queue_id=str(queue_entry.id),
                tenant_id=queue_entry.tenant_id,
                escalated_by=queue_entry.actioned_by,
                correlation_id=str(queue_entry.id),
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to send escalation notification",
                queue_id=str(queue_entry.id),
                error=str(e),
                correlation_id=str(queue_entry.id),
            )
            return False

    async def _send_notification_internal(
        self, notification_data: Dict[str, Any]
    ) -> None:
        """Send notification to Notification Service."""
        import httpx

        url = f"{settings.notification_url}/notifications/send"

        async with httpx.AsyncClient(timeout=settings.notification_timeout) as client:
            response = await client.post(url, json=notification_data)
            response.raise_for_status()

            logger.info(
                "Notification sent successfully",
                notification_type=notification_data.get("type"),
                queue_id=notification_data.get("queue_id"),
            )

    async def get_pending_approvals(self) -> List[AIResponseQueue]:
        """
        Get all pending approval requests.

        Returns:
            List of pending approval queue entries
        """
        pending_approvals = [
            entry
            for entry in self._approval_queue.values()
            if entry.status == "pending"
        ]

        # Sort by creation time (oldest first)
        pending_approvals.sort(key=lambda x: x.created_at)

        logger.info("Retrieved pending approvals", count=len(pending_approvals))

        return pending_approvals

    def get_queue_entry(self, queue_id: UUID) -> Optional[AIResponseQueue]:
        """
        Get approval queue entry by ID.

        Args:
            queue_id: Queue entry ID

        Returns:
            Queue entry if found, None otherwise
        """
        return self._approval_queue.get(queue_id)

    def get_audit_logs(self, queue_id: Optional[UUID] = None) -> List[ApprovalAuditLog]:
        """
        Get audit logs for approval actions.

        Args:
            queue_id: Optional queue ID to filter logs

        Returns:
            List of audit log entries
        """
        if queue_id:
            return [
                log for log in self._audit_logs if log.response_queue_id == queue_id
            ]
        return self._audit_logs.copy()

    async def check_approval_timeouts(self) -> List[AIResponseQueue]:
        """
        Check for pending approvals that have timed out and escalate them.

        Returns:
            List of timed out queue entries that were escalated
        """
        timeout_threshold = datetime.utcnow() - timedelta(
            hours=settings.approval_timeout
        )
        timed_out_entries = []

        for entry in self._approval_queue.values():
            if entry.status == "pending" and entry.created_at < timeout_threshold:
                # Auto-escalate timed out entries
                entry.status = "escalated"
                entry.approval_action = "auto_escalate"
                entry.actioned_at = datetime.utcnow()
                entry.actioned_by = "system"

                # Create audit log
                audit_log = ApprovalAuditLog(
                    response_queue_id=entry.id,
                    action="auto_escalate",
                    original_response=entry.ai_response,
                    final_response=entry.ai_response,
                    reason=f"Approval timeout after {settings.approval_timeout} hours",
                    approved_by="system",
                )
                self._audit_logs.append(audit_log)

                timed_out_entries.append(entry)

                logger.info(
                    "Approval timeout auto-escalated",
                    queue_id=str(entry.id),
                    tenant_id=entry.tenant_id,
                    hours_old=(datetime.utcnow() - entry.created_at).total_seconds()
                    / 3600,
                    correlation_id=str(entry.id),
                )

                # Send escalation notification
                await self._send_escalation_notification(
                    entry, f"Approval timeout after {settings.approval_timeout} hours"
                )

        return timed_out_entries
