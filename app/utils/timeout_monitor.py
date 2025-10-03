"""
Timeout monitoring utilities for Story 2.2

Implements 36-hour response timeout monitoring as specified in AC3 requirements.
Tracks workflow timeouts and triggers escalation when response times exceed limits.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class TimeoutStatus(Enum):
    """Enumeration of timeout statuses."""
    ACTIVE = "active"
    WARNING = "warning"  # Approaching timeout
    EXPIRED = "expired"  # Past timeout
    ESCALATED = "escalated"  # Escalation triggered


@dataclass
class WorkflowTimeout:
    """Represents a workflow timeout tracking entry."""
    workflow_id: str
    customer_phone: str
    last_ai_response: datetime
    timeout_threshold: timedelta
    status: TimeoutStatus
    warning_sent: bool = False
    escalation_triggered: bool = False
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

    @property
    def time_remaining(self) -> timedelta:
        """Calculate remaining time before timeout."""
        timeout_time = self.last_ai_response + self.timeout_threshold
        return timeout_time - datetime.utcnow()

    @property
    def is_expired(self) -> bool:
        """Check if workflow has exceeded timeout."""
        return datetime.utcnow() > (self.last_ai_response + self.timeout_threshold)

    @property
    def is_warning_threshold(self) -> bool:
        """Check if workflow is approaching timeout (6 hours remaining)."""
        warning_threshold = timedelta(hours=6)
        time_remaining = self.time_remaining
        return timedelta(0) < time_remaining <= warning_threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert timeout to dictionary format."""
        return {
            "workflow_id": self.workflow_id,
            "customer_phone": self.customer_phone,
            "last_ai_response": self.last_ai_response.isoformat(),
            "timeout_threshold_hours": int(self.timeout_threshold.total_seconds() // 3600),
            "status": self.status.value,
            "warning_sent": self.warning_sent,
            "escalation_triggered": self.escalation_triggered,
            "time_remaining_hours": max(0, int(self.time_remaining.total_seconds() // 3600)),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class TimeoutMonitor:
    """
    Monitors workflow timeouts and triggers escalation when response times
    exceed the 36-hour threshold as specified in AC3.
    """

    def __init__(self, timeout_hours: int = 36):
        """
        Initialize timeout monitor.

        Args:
            timeout_hours: Hours before timeout (default: 36 per AC3)
        """
        self.timeout_threshold = timedelta(hours=timeout_hours)
        self.active_timeouts: Dict[str, WorkflowTimeout] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_interval = 300  # 5 minutes in seconds

        logger.info(
            "Timeout monitor initialized",
            timeout_hours=timeout_hours,
            monitoring_interval_seconds=self._monitoring_interval
        )

    async def start_monitoring(self) -> None:
        """Start the background timeout monitoring task."""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Timeout monitoring already running")
            return

        self._monitoring_task = asyncio.create_task(self._monitor_timeouts())
        logger.info("Timeout monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop the background timeout monitoring task."""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Timeout monitoring stopped")

    def register_workflow(
        self,
        workflow_id: str,
        customer_phone: str,
        last_ai_response: datetime
    ) -> WorkflowTimeout:
        """
        Register a workflow for timeout monitoring.

        Args:
            workflow_id: Unique workflow identifier
            customer_phone: Customer phone number
            last_ai_response: Timestamp of last AI response

        Returns:
            Created WorkflowTimeout instance
        """
        timeout = WorkflowTimeout(
            workflow_id=workflow_id,
            customer_phone=customer_phone,
            last_ai_response=last_ai_response,
            timeout_threshold=self.timeout_threshold,
            status=TimeoutStatus.ACTIVE
        )

        self.active_timeouts[workflow_id] = timeout

        logger.info(
            "Workflow registered for timeout monitoring",
            workflow_id=workflow_id,
            customer_phone=customer_phone,
            timeout_hours=int(self.timeout_threshold.total_seconds() // 3600)
        )

        return timeout

    def update_workflow_response(
        self,
        workflow_id: str,
        response_time: datetime
    ) -> Optional[WorkflowTimeout]:
        """
        Update workflow with new response time.

        Args:
            workflow_id: Workflow identifier
            response_time: New response timestamp

        Returns:
            Updated WorkflowTimeout or None if not found
        """
        if workflow_id not in self.active_timeouts:
            logger.warning(
                "Attempted to update unregistered workflow",
                workflow_id=workflow_id
            )
            return None

        timeout = self.active_timeouts[workflow_id]
        timeout.last_ai_response = response_time
        timeout.status = TimeoutStatus.ACTIVE
        timeout.warning_sent = False
        timeout.updated_at = datetime.utcnow()

        logger.info(
            "Workflow timeout updated",
            workflow_id=workflow_id,
            new_response_time=response_time.isoformat()
        )

        return timeout

    def remove_workflow(self, workflow_id: str) -> bool:
        """
        Remove workflow from timeout monitoring.

        Args:
            workflow_id: Workflow identifier

        Returns:
            True if removed, False if not found
        """
        if workflow_id not in self.active_timeouts:
            return False

        del self.active_timeouts[workflow_id]

        logger.info(
            "Workflow removed from timeout monitoring",
            workflow_id=workflow_id
        )

        return True

    def get_expired_workflows(self) -> List[WorkflowTimeout]:
        """
        Get all workflows that have exceeded timeout.

        Returns:
            List of expired WorkflowTimeout instances
        """
        expired = []
        for timeout in self.active_timeouts.values():
            if timeout.is_expired and not timeout.escalation_triggered:
                expired.append(timeout)

        return expired

    def get_warning_workflows(self) -> List[WorkflowTimeout]:
        """
        Get workflows approaching timeout (6 hours remaining).

        Returns:
            List of warning WorkflowTimeout instances
        """
        warnings = []
        for timeout in self.active_timeouts.values():
            if timeout.is_warning_threshold and not timeout.warning_sent:
                warnings.append(timeout)

        return warnings

    def get_workflow_timeout(self, workflow_id: str) -> Optional[WorkflowTimeout]:
        """
        Get timeout tracking for specific workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            WorkflowTimeout or None if not found
        """
        return self.active_timeouts.get(workflow_id)

    def get_all_timeouts(self) -> List[WorkflowTimeout]:
        """
        Get all active timeout tracking entries.

        Returns:
            List of all WorkflowTimeout instances
        """
        return list(self.active_timeouts.values())

    async def check_timeouts(self) -> Dict[str, List[WorkflowTimeout]]:
        """
        Check all workflows for timeout conditions.

        Returns:
            Dictionary with 'expired' and 'warnings' lists
        """
        expired_workflows = self.get_expired_workflows()
        warning_workflows = self.get_warning_workflows()

        # Update status for expired workflows
        for timeout in expired_workflows:
            timeout.status = TimeoutStatus.EXPIRED
            timeout.updated_at = datetime.utcnow()

        # Update status for warning workflows
        for timeout in warning_workflows:
            timeout.status = TimeoutStatus.WARNING
            timeout.warning_sent = True
            timeout.updated_at = datetime.utcnow()

        result = {
            "expired": expired_workflows,
            "warnings": warning_workflows
        }

        if expired_workflows or warning_workflows:
            logger.info(
                "Timeout check complete",
                expired_count=len(expired_workflows),
                warning_count=len(warning_workflows),
                total_active=len(self.active_timeouts)
            )

        return result

    async def _monitor_timeouts(self) -> None:
        """Background task to continuously monitor timeouts."""
        logger.info("Starting timeout monitoring loop")

        while True:
            try:
                await asyncio.sleep(self._monitoring_interval)
                await self.check_timeouts()

            except asyncio.CancelledError:
                logger.info("Timeout monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(
                    "Error in timeout monitoring loop",
                    error=str(e),
                    exc_info=True
                )
                # Continue monitoring despite errors

    def get_timeout_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about timeout monitoring.

        Returns:
            Dictionary with monitoring statistics
        """
        total_active = len(self.active_timeouts)
        expired_count = len([t for t in self.active_timeouts.values() if t.is_expired])
        warning_count = len([t for t in self.active_timeouts.values() if t.is_warning_threshold])
        escalated_count = len([t for t in self.active_timeouts.values() if t.escalation_triggered])

        return {
            "total_active_workflows": total_active,
            "expired_workflows": expired_count,
            "warning_workflows": warning_count,
            "escalated_workflows": escalated_count,
            "timeout_threshold_hours": int(self.timeout_threshold.total_seconds() // 3600),
            "monitoring_active": self._monitoring_task and not self._monitoring_task.done()
        }

    def mark_workflow_escalated(self, workflow_id: str) -> bool:
        """
        Mark workflow as escalated to prevent duplicate escalations.

        Args:
            workflow_id: Workflow identifier

        Returns:
            True if marked successfully, False if not found
        """
        if workflow_id not in self.active_timeouts:
            return False

        timeout = self.active_timeouts[workflow_id]
        timeout.escalation_triggered = True
        timeout.status = TimeoutStatus.ESCALATED
        timeout.updated_at = datetime.utcnow()

        logger.info(
            "Workflow marked as escalated",
            workflow_id=workflow_id
        )

        return True

    def cleanup_old_timeouts(self, days_old: int = 7) -> int:
        """
        Remove old timeout entries to prevent memory leaks.

        Args:
            days_old: Remove entries older than this many days

        Returns:
            Number of entries removed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        old_workflows = []

        for workflow_id, timeout in list(self.active_timeouts.items()):
            if timeout.created_at < cutoff_date and timeout.escalation_triggered:
                old_workflows.append(workflow_id)

        for workflow_id in old_workflows:
            del self.active_timeouts[workflow_id]

        if old_workflows:
            logger.info(
                "Cleaned up old timeout entries",
                removed_count=len(old_workflows),
                days_old=days_old
            )

        return len(old_workflows)