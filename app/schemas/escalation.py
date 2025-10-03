"""
Pydantic schemas for escalation API endpoints.

Request/response models for escalation operations per Story 2.2 requirements.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class EscalationReason(str, Enum):
    """Enumeration of escalation reasons matching the utility enum."""
    CUSTOMER_ANGER = "customer_anger"
    LEGAL_REQUEST = "legal_request"
    FORMAL_COMPLAINT = "formal_complaint"
    CUSTOMER_CONFUSION = "customer_confusion"
    GENERAL_DISSATISFACTION = "general_dissatisfaction"


class EscalationType(str, Enum):
    """Enumeration of escalation types."""
    TRIGGER_BASED = "trigger_based"
    TIMEOUT_BASED = "timeout_based"
    MANUAL = "manual"


class EscalationStatus(str, Enum):
    """Enumeration of escalation statuses."""
    TRIGGERED = "triggered"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Request Schemas

class EscalationRequest(BaseModel):
    """Request model for manual escalation triggering."""
    workflow_id: str = Field(..., description="Unique workflow identifier")
    customer_phone: str = Field(..., description="Customer phone number")
    reason: EscalationReason = Field(..., description="Reason for escalation")
    notes: Optional[str] = Field(None, description="Additional notes about the escalation")

    @validator('customer_phone')
    def validate_phone(cls, v):
        """Validate phone number format."""
        if not v or len(v) < 10:
            raise ValueError('Phone number must be at least 10 digits')
        return v

    @validator('workflow_id')
    def validate_workflow_id(cls, v):
        """Validate workflow ID."""
        if not v or len(v) < 3:
            raise ValueError('Workflow ID must be at least 3 characters')
        return v

    class Config:
        use_enum_values = True


class TimeoutRegistrationRequest(BaseModel):
    """Request model for registering workflow timeout monitoring."""
    workflow_id: str = Field(..., description="Unique workflow identifier")
    customer_phone: str = Field(..., description="Customer phone number")
    last_ai_response: datetime = Field(..., description="Timestamp of last AI response")
    timeout_hours: Optional[int] = Field(36, description="Timeout threshold in hours")

    @validator('customer_phone')
    def validate_phone(cls, v):
        """Validate phone number format."""
        if not v or len(v) < 10:
            raise ValueError('Phone number must be at least 10 digits')
        return v

    @validator('workflow_id')
    def validate_workflow_id(cls, v):
        """Validate workflow ID."""
        if not v or len(v) < 3:
            raise ValueError('Workflow ID must be at least 3 characters')
        return v

    @validator('timeout_hours')
    def validate_timeout_hours(cls, v):
        """Validate timeout hours."""
        if v <= 0 or v > 168:  # Max 1 week
            raise ValueError('Timeout hours must be between 1 and 168')
        return v


class TimeoutUpdateRequest(BaseModel):
    """Request model for updating workflow timeout."""
    response_time: datetime = Field(..., description="New response timestamp")


# Response Schemas

class EscalationResponse(BaseModel):
    """Response model for escalation operations."""
    escalation_id: str = Field(..., description="Unique escalation identifier")
    workflow_id: str = Field(..., description="Associated workflow ID")
    status: str = Field(..., description="Escalation status")
    message: str = Field(..., description="Status message")
    timestamp: datetime = Field(..., description="Response timestamp")


class EscalationStatusResponse(BaseModel):
    """Response model for escalation status queries."""
    workflow_id: str = Field(..., description="Workflow identifier")
    customer_phone: str = Field(..., description="Customer phone number")
    last_ai_response: datetime = Field(..., description="Last AI response timestamp")
    timeout_hours: int = Field(..., description="Timeout threshold in hours")
    hours_remaining: int = Field(..., description="Hours remaining before timeout")
    status: str = Field(..., description="Current timeout status")
    escalation_triggered: bool = Field(..., description="Whether escalation has been triggered")
    warning_sent: bool = Field(..., description="Whether warning has been sent")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class EscalationStatisticsResponse(BaseModel):
    """Response model for escalation statistics."""
    total_active_workflows: int = Field(..., description="Total active workflows")
    expired_workflows: int = Field(..., description="Workflows past timeout")
    warning_workflows: int = Field(..., description="Workflows approaching timeout")
    escalated_workflows: int = Field(..., description="Workflows with escalations")
    escalated_today: int = Field(..., description="Escalations triggered today")
    timeout_threshold_hours: int = Field(..., description="Default timeout threshold")
    monitoring_active: bool = Field(..., description="Whether monitoring is active")
    timestamp: datetime = Field(..., description="Statistics timestamp")


class EscalationEventResponse(BaseModel):
    """Response model for escalation event details."""
    id: str = Field(..., description="Event ID")
    escalation_id: str = Field(..., description="Escalation ID")
    workflow_id: str = Field(..., description="Workflow ID")
    customer_phone: str = Field(..., description="Customer phone number")
    escalation_type: str = Field(..., description="Type of escalation")
    reason: str = Field(..., description="Escalation reason")
    confidence: float = Field(..., description="Confidence score")
    matched_text: Optional[str] = Field(None, description="Text that triggered escalation")
    status: str = Field(..., description="Current status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class NotificationLogResponse(BaseModel):
    """Response model for notification log entries."""
    id: str = Field(..., description="Log entry ID")
    escalation_id: str = Field(..., description="Associated escalation ID")
    notification_type: str = Field(..., description="Type of notification")
    target_service: str = Field(..., description="Target service URL/identifier")
    attempt_number: int = Field(..., description="Attempt number")
    status: str = Field(..., description="Notification status")
    response_code: Optional[int] = Field(None, description="HTTP response code")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Creation timestamp")


class HealthCheckResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Service health status")
    monitoring_active: bool = Field(..., description="Whether monitoring is active")
    active_workflows: int = Field(..., description="Number of active workflows")
    escalation_service_ready: bool = Field(..., description="Whether escalation service is ready")
    last_check: str = Field(..., description="Last health check timestamp")
    version: str = Field(..., description="Service version")


# Internal Schemas (not exposed in API)

class EscalationNotificationPayload(BaseModel):
    """Internal schema for notification payloads."""
    escalation_id: str
    workflow_id: str
    customer_phone: str
    reason: str
    confidence: float
    timestamp: str
    escalation_type: str
    matched_text: Optional[str] = None


class TimeoutWarningPayload(BaseModel):
    """Internal schema for timeout warning notifications."""
    workflow_id: str
    customer_phone: str
    hours_remaining: int
    timeout_time: str
    warning_type: str = "approaching_timeout"


class EscalationTrigger(BaseModel):
    """Internal schema for escalation triggers."""
    reason: EscalationReason
    confidence: float
    matched_text: str
    pattern_type: str

    class Config:
        use_enum_values = True


class EscalationEvent(BaseModel):
    """Internal schema for escalation events."""
    escalation_id: str
    workflow_id: str
    customer_phone: str
    escalation_type: EscalationType
    reason: EscalationReason
    confidence: float
    matched_text: Optional[str] = None
    trigger_pattern_type: Optional[str] = None
    status: EscalationStatus = EscalationStatus.TRIGGERED
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


# Validation Helper Functions

def validate_escalation_request(request: EscalationRequest) -> bool:
    """Validate escalation request parameters."""
    if not request.workflow_id or len(request.workflow_id) < 3:
        return False
    if not request.customer_phone or len(request.customer_phone) < 10:
        return False
    if request.reason not in EscalationReason.__members__:
        return False
    return True


def validate_timeout_registration(request: TimeoutRegistrationRequest) -> bool:
    """Validate timeout registration request."""
    if not validate_escalation_request(
        EscalationRequest(
            workflow_id=request.workflow_id,
            customer_phone=request.customer_phone,
            reason=EscalationReason.GENERAL_DISSATISFACTION
        )
    ):
        return False
    if request.timeout_hours <= 0 or request.timeout_hours > 168:
        return False
    return True