"""
Escalation database models for Story 2.2

Database models for storing escalation events, tracking workflow timeouts,
and maintaining escalation history per requirements.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.database import Base


class EscalationStatus(str, Enum):
    """Enumeration of escalation statuses."""
    TRIGGERED = "triggered"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EscalationType(str, Enum):
    """Enumeration of escalation types."""
    TRIGGER_BASED = "trigger_based"
    TIMEOUT_BASED = "timeout_based"
    MANUAL = "manual"


class EscalationEvent(Base):
    """
    Database model for escalation events.

    Stores all escalation events with full context including triggers,
    notifications sent, and resolution status.
    """

    __tablename__ = "escalation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    escalation_id = Column(String(255), unique=True, nullable=False, index=True)
    workflow_id = Column(String(255), nullable=False, index=True)
    customer_phone = Column(String(20), nullable=False, index=True)

    # Escalation details
    escalation_type = Column(String(50), nullable=False)  # trigger_based, timeout_based, manual
    reason = Column(String(100), nullable=False)  # customer_anger, legal_request, etc.
    confidence = Column(Float, nullable=False)
    matched_text = Column(Text, nullable=True)
    trigger_pattern_type = Column(String(50), nullable=True)  # regex, keyword, timeout, manual

    # Status tracking
    status = Column(String(50), nullable=False, default=EscalationStatus.TRIGGERED)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)

    # Notification tracking
    notifications_sent = Column(JSONB, nullable=True)  # Track which notifications were sent
    last_notification_attempt = Column(DateTime(timezone=True), nullable=True)
    notification_retry_count = Column(Integer, default=0)

    # Resolution information
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(String(100), nullable=True)  # Staff member who resolved
    resolution_time_minutes = Column(Integer, nullable=True)  # Time to resolution

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Indexes for performance
    __table_args__ = (
        Index('idx_escalation_events_workflow_status', 'workflow_id', 'status'),
        Index('idx_escalation_events_created_at', 'created_at'),
        Index('idx_escalation_events_customer_type', 'customer_phone', 'escalation_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses."""
        return {
            "id": str(self.id),
            "escalation_id": self.escalation_id,
            "workflow_id": self.workflow_id,
            "customer_phone": self.customer_phone,
            "escalation_type": self.escalation_type,
            "reason": self.reason,
            "confidence": self.confidence,
            "matched_text": self.matched_text,
            "trigger_pattern_type": self.trigger_pattern_type,
            "status": self.status,
            "processing_started_at": self.processing_started_at.isoformat() if self.processing_started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "failure_reason": self.failure_reason,
            "notifications_sent": self.notifications_sent,
            "last_notification_attempt": self.last_notification_attempt.isoformat() if self.last_notification_attempt else None,
            "notification_retry_count": self.notification_retry_count,
            "resolution_notes": self.resolution_notes,
            "resolved_by": self.resolved_by,
            "resolution_time_minutes": self.resolution_time_minutes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class WorkflowTimeoutTracking(Base):
    """
    Database model for tracking workflow timeouts.

    Persistent storage for timeout monitoring to ensure continuity
    across service restarts and provide audit trail.
    """

    __tablename__ = "workflow_timeout_tracking"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(String(255), unique=True, nullable=False, index=True)
    customer_phone = Column(String(20), nullable=False, index=True)
    last_ai_response = Column(DateTime(timezone=True), nullable=False)
    timeout_threshold_hours = Column(Integer, nullable=False, default=36)

    # Status tracking
    status = Column(String(50), nullable=False, default="active")  # active, warning, expired, escalated
    escalation_triggered = Column(Boolean, default=False, nullable=False)
    warning_sent = Column(Boolean, default=False, nullable=False)
    warning_sent_at = Column(DateTime(timezone=True), nullable=True)
    escalation_triggered_at = Column(DateTime(timezone=True), nullable=True)

    # Associated escalation (if any)
    escalation_event_id = Column(UUID(as_uuid=True), ForeignKey('escalation_events.id'), nullable=True)
    escalation_event = relationship("EscalationEvent", backref="timeout_tracking")

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Indexes for performance
    __table_args__ = (
        Index('idx_timeout_tracking_status', 'status'),
        Index('idx_timeout_tracking_customer_status', 'customer_phone', 'status'),
        Index('idx_timeout_tracking_created_at', 'created_at'),
    )

    @property
    def time_remaining_hours(self) -> float:
        """Calculate hours remaining before timeout."""
        from datetime import datetime, timedelta
        timeout_time = self.last_ai_response + timedelta(hours=self.timeout_threshold_hours)
        remaining = timeout_time - datetime.utcnow(self.last_ai_response.tzinfo)
        return max(0, remaining.total_seconds() / 3600)

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses."""
        return {
            "id": str(self.id),
            "workflow_id": self.workflow_id,
            "customer_phone": self.customer_phone,
            "last_ai_response": self.last_ai_response.isoformat(),
            "timeout_threshold_hours": self.timeout_threshold_hours,
            "status": self.status,
            "escalation_triggered": self.escalation_triggered,
            "warning_sent": self.warning_sent,
            "warning_sent_at": self.warning_sent_at.isoformat() if self.warning_sent_at else None,
            "escalation_triggered_at": self.escalation_triggered_at.isoformat() if self.escalation_triggered_at else None,
            "time_remaining_hours": self.time_remaining_hours,
            "escalation_event_id": str(self.escalation_event_id) if self.escalation_event_id else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class EscalationNotificationLog(Base):
    """
    Database model for tracking escalation notification attempts.

    Provides audit trail for all notification attempts and their outcomes.
    """

    __tablename__ = "escalation_notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    escalation_id = Column(String(255), nullable=False, index=True)
    workflow_id = Column(String(255), nullable=False, index=True)

    # Notification details
    notification_type = Column(String(50), nullable=False)  # collections_monitor, sms_agent, internal_teams
    target_service = Column(String(100), nullable=False)  # URL or service identifier
    notification_payload = Column(JSONB, nullable=False)  # Full payload sent

    # Attempt tracking
    attempt_number = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)  # sent, failed, retry, cancelled
    response_code = Column(Integer, nullable=True)  # HTTP status code
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timing
    sent_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)  # Duration in milliseconds

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Indexes for performance
    __table_args__ = (
        Index('idx_notification_logs_escalation_type', 'escalation_id', 'notification_type'),
        Index('idx_notification_logs_status_created', 'status', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses."""
        return {
            "id": str(self.id),
            "escalation_id": self.escalation_id,
            "workflow_id": self.workflow_id,
            "notification_type": self.notification_type,
            "target_service": self.target_service,
            "notification_payload": self.notification_payload,
            "attempt_number": self.attempt_number,
            "status": self.status,
            "response_code": self.response_code,
            "response_body": self.response_body,
            "error_message": self.error_message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat()
        }


class EscalationStatistics(Base):
    """
    Database model for storing daily escalation statistics.

    Aggregated statistics for monitoring and reporting purposes.
    """

    __tablename__ = "escalation_statistics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(DateTime(timezone=True), nullable=False, index=True)  # Daily partition key

    # Escalation counts by type
    trigger_based_escalations = Column(Integer, default=0)
    timeout_based_escalations = Column(Integer, default=0)
    manual_escalations = Column(Integer, default=0)
    total_escalations = Column(Integer, default=0)

    # Escalation counts by reason
    anger_escalations = Column(Integer, default=0)
    legal_request_escalations = Column(Integer, default=0)
    complaint_escalations = Column(Integer, default=0)
    confusion_escalations = Column(Integer, default=0)
    dissatisfaction_escalations = Column(Integer, default=0)

    # Workflow statistics
    active_workflows_count = Column(Integer, default=0)
    expired_workflows_count = Column(Integer, default=0)
    warning_workflows_count = Column(Integer, default=0)

    # Resolution statistics
    resolved_escalations = Column(Integer, default=0)
    average_resolution_time_minutes = Column(Float, nullable=True)

    # Notification statistics
    notifications_sent = Column(Integer, default=0)
    notifications_failed = Column(Integer, default=0)
    average_notification_duration_ms = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Unique constraint to prevent duplicate daily entries
    __table_args__ = (
        Index('idx_stats_date_unique', 'date', unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses."""
        return {
            "id": str(self.id),
            "date": self.date.isoformat(),
            "trigger_based_escalations": self.trigger_based_escalations,
            "timeout_based_escalations": self.timeout_based_escalations,
            "manual_escalations": self.manual_escalations,
            "total_escalations": self.total_escalations,
            "anger_escalations": self.anger_escalations,
            "legal_request_escalations": self.legal_request_escalations,
            "complaint_escalations": self.complaint_escalations,
            "confusion_escalations": self.confusion_escalations,
            "dissatisfaction_escalations": self.dissatisfaction_escalations,
            "active_workflows_count": self.active_workflows_count,
            "expired_workflows_count": self.expired_workflows_count,
            "warning_workflows_count": self.warning_workflows_count,
            "resolved_escalations": self.resolved_escalations,
            "average_resolution_time_minutes": self.average_resolution_time_minutes,
            "notifications_sent": self.notifications_sent,
            "notifications_failed": self.notifications_failed,
            "average_notification_duration_ms": self.average_notification_duration_ms,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }