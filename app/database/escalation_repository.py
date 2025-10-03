"""
Escalation database repository for Story 2.2

Database operations for escalation events, timeout tracking, and statistics.
Provides data access layer for escalation service operations.
"""

from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.dialects.postgresql import UUID
import structlog

from app.models.escalation import (
    EscalationEvent,
    WorkflowTimeoutTracking,
    EscalationNotificationLog,
    EscalationStatistics
)
from app.schemas.escalation import EscalationRequest, EscalationType, EscalationStatus
from app.core.exceptions import DatabaseError

logger = structlog.get_logger(__name__)


class EscalationRepository:
    """
    Repository for escalation database operations.

    Handles all database interactions for escalation events,
    timeout tracking, and statistics generation.
    """

    def __init__(self, db: Session):
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    # Escalation Event Operations

    def create_escalation_event(
        self,
        escalation_id: str,
        workflow_id: str,
        customer_phone: str,
        escalation_type: EscalationType,
        reason: str,
        confidence: float,
        matched_text: Optional[str] = None,
        trigger_pattern_type: Optional[str] = None
    ) -> EscalationEvent:
        """
        Create a new escalation event record.

        Args:
            escalation_id: Unique escalation identifier
            workflow_id: Associated workflow ID
            customer_phone: Customer phone number
            escalation_type: Type of escalation
            reason: Reason for escalation
            confidence: Confidence score (0.0-1.0)
            matched_text: Text that triggered escalation
            trigger_pattern_type: Type of pattern that matched

        Returns:
            Created EscalationEvent instance

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            escalation_event = EscalationEvent(
                escalation_id=escalation_id,
                workflow_id=workflow_id,
                customer_phone=customer_phone,
                escalation_type=escalation_type.value,
                reason=reason,
                confidence=confidence,
                matched_text=matched_text,
                trigger_pattern_type=trigger_pattern_type,
                status=EscalationStatus.TRIGGERED.value
            )

            self.db.add(escalation_event)
            self.db.commit()
            self.db.refresh(escalation_event)

            logger.info(
                "Escalation event created",
                escalation_id=escalation_id,
                workflow_id=workflow_id,
                escalation_type=escalation_type.value,
                reason=reason
            )

            return escalation_event

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to create escalation event",
                escalation_id=escalation_id,
                workflow_id=workflow_id,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to create escalation event: {str(e)}")

    def get_escalation_event(self, escalation_id: str) -> Optional[EscalationEvent]:
        """
        Get escalation event by ID.

        Args:
            escalation_id: Escalation identifier

        Returns:
            EscalationEvent or None if not found
        """
        try:
            return self.db.query(EscalationEvent).filter(
                EscalationEvent.escalation_id == escalation_id
            ).first()

        except Exception as e:
            logger.error(
                "Failed to get escalation event",
                escalation_id=escalation_id,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to get escalation event: {str(e)}")

    def get_escalation_events_by_workflow(self, workflow_id: str) -> List[EscalationEvent]:
        """
        Get all escalation events for a workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            List of escalation events for the workflow
        """
        try:
            return self.db.query(EscalationEvent).filter(
                EscalationEvent.workflow_id == workflow_id
            ).order_by(desc(EscalationEvent.created_at)).all()

        except Exception as e:
            logger.error(
                "Failed to get escalation events by workflow",
                workflow_id=workflow_id,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to get escalation events: {str(e)}")

    def update_escalation_event(
        self,
        escalation_id: str,
        status: Optional[EscalationStatus] = None,
        resolution_notes: Optional[str] = None,
        resolved_by: Optional[str] = None,
        failure_reason: Optional[str] = None
    ) -> Optional[EscalationEvent]:
        """
        Update escalation event status and details.

        Args:
            escalation_id: Escalation identifier
            status: New status (optional)
            resolution_notes: Resolution notes (optional)
            resolved_by: Who resolved the escalation (optional)
            failure_reason: Reason for failure (optional)

        Returns:
            Updated EscalationEvent or None if not found
        """
        try:
            escalation = self.get_escalation_event(escalation_id)
            if not escalation:
                return None

            # Update fields
            if status:
                escalation.status = status.value
                if status == EscalationStatus.PROCESSING:
                    escalation.processing_started_at = datetime.utcnow()
                elif status == EscalationStatus.COMPLETED:
                    escalation.completed_at = datetime.utcnow()
                    if escalation.processing_started_at:
                        duration = escalation.completed_at - escalation.processing_started_at
                        escalation.resolution_time_minutes = int(duration.total_seconds() / 60)
                elif status == EscalationStatus.FAILED:
                    escalation.failed_at = datetime.utcnow()

            if resolution_notes:
                escalation.resolution_notes = resolution_notes

            if resolved_by:
                escalation.resolved_by = resolved_by

            if failure_reason:
                escalation.failure_reason = failure_reason

            escalation.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(escalation)

            logger.info(
                "Escalation event updated",
                escalation_id=escalation_id,
                status=status.value if status else None,
                updated_fields=[
                    field for field, value in [
                        ("status", status),
                        ("resolution_notes", resolution_notes),
                        ("resolved_by", resolved_by),
                        ("failure_reason", failure_reason)
                    ] if value is not None
                ]
            )

            return escalation

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to update escalation event",
                escalation_id=escalation_id,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to update escalation event: {str(e)}")

    # Timeout Tracking Operations

    def create_timeout_tracking(
        self,
        workflow_id: str,
        customer_phone: str,
        last_ai_response: datetime,
        timeout_threshold_hours: int = 36
    ) -> WorkflowTimeoutTracking:
        """
        Create timeout tracking record for workflow.

        Args:
            workflow_id: Workflow identifier
            customer_phone: Customer phone number
            last_ai_response: Last AI response timestamp
            timeout_threshold_hours: Timeout threshold in hours

        Returns:
            Created WorkflowTimeoutTracking instance
        """
        try:
            timeout_tracking = WorkflowTimeoutTracking(
                workflow_id=workflow_id,
                customer_phone=customer_phone,
                last_ai_response=last_ai_response,
                timeout_threshold_hours=timeout_threshold_hours,
                status="active"
            )

            self.db.add(timeout_tracking)
            self.db.commit()
            self.db.refresh(timeout_tracking)

            logger.info(
                "Timeout tracking created",
                workflow_id=workflow_id,
                timeout_hours=timeout_threshold_hours
            )

            return timeout_tracking

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to create timeout tracking",
                workflow_id=workflow_id,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to create timeout tracking: {str(e)}")

    def get_timeout_tracking(self, workflow_id: str) -> Optional[WorkflowTimeoutTracking]:
        """
        Get timeout tracking by workflow ID.

        Args:
            workflow_id: Workflow identifier

        Returns:
            WorkflowTimeoutTracking or None if not found
        """
        try:
            return self.db.query(WorkflowTimeoutTracking).filter(
                WorkflowTimeoutTracking.workflow_id == workflow_id
            ).first()

        except Exception as e:
            logger.error(
                "Failed to get timeout tracking",
                workflow_id=workflow_id,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to get timeout tracking: {str(e)}")

    def get_expired_timeouts(self) -> List[WorkflowTimeoutTracking]:
        """
        Get all expired timeout tracking records.

        Returns:
            List of expired WorkflowTimeoutTracking instances
        """
        try:
            current_time = datetime.utcnow()
            return self.db.query(WorkflowTimeoutTracking).filter(
                and_(
                    WorkflowTimeoutTracking.escalation_triggered == False,
                    current_time > (
                        WorkflowTimeoutTracking.last_ai_response +
                        func.make_interval(0, 0, 0, 0, WorkflowTimeoutTracking.timeout_threshold_hours, 0, 0)
                    )
                )
            ).all()

        except Exception as e:
            logger.error(
                "Failed to get expired timeouts",
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to get expired timeouts: {str(e)}")

    def get_warning_timeouts(self) -> List[WorkflowTimeoutTracking]:
        """
        Get timeouts approaching threshold (6 hours remaining).

        Returns:
            List of WorkflowTimeoutTracking instances near timeout
        """
        try:
            current_time = datetime.utcnow()
            warning_threshold_hours = 6

            return self.db.query(WorkflowTimeoutTracking).filter(
                and_(
                    WorkflowTimeoutTracking.warning_sent == False,
                    WorkflowTimeoutTracking.escalation_triggered == False,
                    current_time > (
                        WorkflowTimeoutTracking.last_ai_response +
                        func.make_interval(0, 0, 0, 0, WorkflowTimeoutTracking.timeout_threshold_hours - warning_threshold_hours, 0, 0)
                    ),
                    current_time <= (
                        WorkflowTimeoutTracking.last_ai_response +
                        func.make_interval(0, 0, 0, 0, WorkflowTimeoutTracking.timeout_threshold_hours, 0, 0)
                    )
                )
            ).all()

        except Exception as e:
            logger.error(
                "Failed to get warning timeouts",
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to get warning timeouts: {str(e)}")

    def update_timeout_tracking(
        self,
        workflow_id: str,
        last_ai_response: Optional[datetime] = None,
        status: Optional[str] = None,
        escalation_triggered: Optional[bool] = None,
        warning_sent: Optional[bool] = None
    ) -> Optional[WorkflowTimeoutTracking]:
        """
        Update timeout tracking record.

        Args:
            workflow_id: Workflow identifier
            last_ai_response: New response time (optional)
            status: New status (optional)
            escalation_triggered: Whether escalation triggered (optional)
            warning_sent: Whether warning sent (optional)

        Returns:
            Updated WorkflowTimeoutTracking or None if not found
        """
        try:
            timeout = self.get_timeout_tracking(workflow_id)
            if not timeout:
                return None

            # Update fields
            if last_ai_response:
                timeout.last_ai_response = last_ai_response

            if status:
                timeout.status = status

            if escalation_triggered is not None:
                timeout.escalation_triggered = escalation_triggered
                if escalation_triggered:
                    timeout.escalation_triggered_at = datetime.utcnow()

            if warning_sent is not None:
                timeout.warning_sent = warning_sent
                if warning_sent:
                    timeout.warning_sent_at = datetime.utcnow()

            timeout.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(timeout)

            logger.info(
                "Timeout tracking updated",
                workflow_id=workflow_id,
                updated_fields=[
                    field for field, value in [
                        ("last_ai_response", last_ai_response),
                        ("status", status),
                        ("escalation_triggered", escalation_triggered),
                        ("warning_sent", warning_sent)
                    ] if value is not None
                ]
            )

            return timeout

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to update timeout tracking",
                workflow_id=workflow_id,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to update timeout tracking: {str(e)}")

    def delete_timeout_tracking(self, workflow_id: str) -> bool:
        """
        Delete timeout tracking record.

        Args:
            workflow_id: Workflow identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            timeout = self.get_timeout_tracking(workflow_id)
            if not timeout:
                return False

            self.db.delete(timeout)
            self.db.commit()

            logger.info(
                "Timeout tracking deleted",
                workflow_id=workflow_id
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to delete timeout tracking",
                workflow_id=workflow_id,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to delete timeout tracking: {str(e)}")

    # Notification Log Operations

    def create_notification_log(
        self,
        escalation_id: str,
        workflow_id: str,
        notification_type: str,
        target_service: str,
        notification_payload: Dict[str, Any],
        attempt_number: int,
        status: str,
        response_code: Optional[int] = None,
        response_body: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> EscalationNotificationLog:
        """
        Create notification log entry.

        Args:
            escalation_id: Associated escalation ID
            workflow_id: Associated workflow ID
            notification_type: Type of notification
            target_service: Target service URL/identifier
            notification_payload: Full notification payload
            attempt_number: Attempt number
            status: Notification status
            response_code: HTTP response code (optional)
            response_body: Response body (optional)
            error_message: Error message (optional)
            duration_ms: Duration in milliseconds (optional)

        Returns:
            Created EscalationNotificationLog instance
        """
        try:
            notification_log = EscalationNotificationLog(
                escalation_id=escalation_id,
                workflow_id=workflow_id,
                notification_type=notification_type,
                target_service=target_service,
                notification_payload=notification_payload,
                attempt_number=attempt_number,
                status=status,
                response_code=response_code,
                response_body=response_body,
                error_message=error_message,
                sent_at=datetime.utcnow(),
                duration_ms=duration_ms
            )

            self.db.add(notification_log)
            self.db.commit()
            self.db.refresh(notification_log)

            logger.info(
                "Notification log created",
                escalation_id=escalation_id,
                notification_type=notification_type,
                status=status,
                attempt_number=attempt_number
            )

            return notification_log

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to create notification log",
                escalation_id=escalation_id,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to create notification log: {str(e)}")

    def get_notification_logs(self, escalation_id: str) -> List[EscalationNotificationLog]:
        """
        Get notification logs for an escalation.

        Args:
            escalation_id: Escalation identifier

        Returns:
            List of notification log entries
        """
        try:
            return self.db.query(EscalationNotificationLog).filter(
                EscalationNotificationLog.escalation_id == escalation_id
            ).order_by(asc(EscalationNotificationLog.attempt_number)).all()

        except Exception as e:
            logger.error(
                "Failed to get notification logs",
                escalation_id=escalation_id,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to get notification logs: {str(e)}")

    # Statistics Operations

    def get_daily_statistics(self, target_date: date) -> Optional[EscalationStatistics]:
        """
        Get daily statistics for a specific date.

        Args:
            target_date: Target date for statistics

        Returns:
            EscalationStatistics or None if not found
        """
        try:
            return self.db.query(EscalationStatistics).filter(
                func.date(EscalationStatistics.date) == target_date
            ).first()

        except Exception as e:
            logger.error(
                "Failed to get daily statistics",
                target_date=target_date,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to get daily statistics: {str(e)}")

    def create_or_update_daily_statistics(self, target_date: date) -> EscalationStatistics:
        """
        Create or update daily statistics for a date.

        Args:
            target_date: Target date for statistics

        Returns:
            Created or updated EscalationStatistics
        """
        try:
            # Try to get existing statistics
            stats = self.get_daily_statistics(target_date)

            if stats:
                # Update existing statistics
                return self._update_daily_statistics(stats, target_date)
            else:
                # Create new statistics
                return self._create_daily_statistics(target_date)

        except Exception as e:
            logger.error(
                "Failed to create/update daily statistics",
                target_date=target_date,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to create/update daily statistics: {str(e)}")

    def _create_daily_statistics(self, target_date: date) -> EscalationStatistics:
        """Create new daily statistics."""
        # Calculate statistics from database
        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = start_time + timedelta(days=1)

        # Count escalations by type
        trigger_based = self.db.query(EscalationEvent).filter(
            and_(
                EscalationEvent.created_at >= start_time,
                EscalationEvent.created_at < end_time,
                EscalationEvent.escalation_type == "trigger_based"
            )
        ).count()

        timeout_based = self.db.query(EscalationEvent).filter(
            and_(
                EscalationEvent.created_at >= start_time,
                EscalationEvent.created_at < end_time,
                EscalationEvent.escalation_type == "timeout_based"
            )
        ).count()

        manual = self.db.query(EscalationEvent).filter(
            and_(
                EscalationEvent.created_at >= start_time,
                EscalationEvent.created_at < end_time,
                EscalationEvent.escalation_type == "manual"
            )
        ).count()

        # Count escalations by reason
        anger = self.db.query(EscalationEvent).filter(
            and_(
                EscalationEvent.created_at >= start_time,
                EscalationEvent.created_at < end_time,
                EscalationEvent.reason == "customer_anger"
            )
        ).count()

        legal = self.db.query(EscalationEvent).filter(
            and_(
                EscalationEvent.created_at >= start_time,
                EscalationEvent.created_at < end_time,
                EscalationEvent.reason == "legal_request"
            )
        ).count()

        complaint = self.db.query(EscalationEvent).filter(
            and_(
                EscalationEvent.created_at >= start_time,
                EscalationEvent.created_at < end_time,
                EscalationEvent.reason == "formal_complaint"
            )
        ).count()

        confusion = self.db.query(EscalationEvent).filter(
            and_(
                EscalationEvent.created_at >= start_time,
                EscalationEvent.created_at < end_time,
                EscalationEvent.reason == "customer_confusion"
            )
        ).count()

        dissatisfaction = self.db.query(EscalationEvent).filter(
            and_(
                EscalationEvent.created_at >= start_time,
                EscalationEvent.created_at < end_time,
                EscalationEvent.reason == "general_dissatisfaction"
            )
        ).count()

        # Create statistics record
        stats = EscalationStatistics(
            date=start_time,
            trigger_based_escalations=trigger_based,
            timeout_based_escalations=timeout_based,
            manual_escalations=manual,
            total_escalations=trigger_based + timeout_based + manual,
            anger_escalations=anger,
            legal_request_escalations=legal,
            complaint_escalations=complaint,
            confusion_escalations=confusion,
            dissatisfaction_escalations=dissatisfaction
        )

        self.db.add(stats)
        self.db.commit()
        self.db.refresh(stats)

        return stats

    def _update_daily_statistics(self, stats: EscalationStatistics, target_date: date) -> EscalationStatistics:
        """Update existing daily statistics."""
        # Recalculate all statistics
        new_stats = self._create_daily_statistics(target_date)

        # Update the existing record
        stats.trigger_based_escalations = new_stats.trigger_based_escalations
        stats.timeout_based_escalations = new_stats.timeout_based_escalations
        stats.manual_escalations = new_stats.manual_escalations
        stats.total_escalations = new_stats.total_escalations
        stats.anger_escalations = new_stats.anger_escalations
        stats.legal_request_escalations = new_stats.legal_request_escalations
        stats.complaint_escalations = new_stats.complaint_escalations
        stats.confusion_escalations = new_stats.confusion_escalations
        stats.dissatisfaction_escalations = new_stats.dissatisfaction_escalations

        self.db.commit()
        self.db.refresh(stats)

        return stats

    # Cleanup Operations

    def cleanup_old_timeouts(self, days_old: int = 7) -> int:
        """
        Clean up old timeout tracking records.

        Args:
            days_old: Remove records older than this many days

        Returns:
            Number of records removed
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            deleted = self.db.query(WorkflowTimeoutTracking).filter(
                and_(
                    WorkflowTimeoutTracking.created_at < cutoff_date,
                    WorkflowTimeoutTracking.escalation_triggered == True
                )
            ).delete()

            self.db.commit()

            logger.info(
                "Old timeout tracking records cleaned up",
                days_old=days_old,
                records_deleted=deleted
            )

            return deleted

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to cleanup old timeouts",
                days_old=days_old,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to cleanup old timeouts: {str(e)}")

    def cleanup_old_notification_logs(self, days_old: int = 30) -> int:
        """
        Clean up old notification log records.

        Args:
            days_old: Remove records older than this many days

        Returns:
            Number of records removed
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            deleted = self.db.query(EscalationNotificationLog).filter(
                EscalationNotificationLog.created_at < cutoff_date
            ).delete()

            self.db.commit()

            logger.info(
                "Old notification log records cleaned up",
                days_old=days_old,
                records_deleted=deleted
            )

            return deleted

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to cleanup old notification logs",
                days_old=days_old,
                error=str(e),
                exc_info=True
            )
            raise DatabaseError(f"Failed to cleanup old notification logs: {str(e)}")