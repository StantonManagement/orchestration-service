"""Pydantic schemas for request/response models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator


class MessageType(str, Enum):
    """SMS message direction types."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class WorkflowStatus(str, Enum):
    """Workflow status types."""
    RECEIVED = "received"
    PROCESSING = "processing"
    AWAITING_APPROVAL = "awaiting_approval"
    SENT = "sent"
    ESCALATED = "escalated"
    FAILED = "failed"
    COMPLETED = "completed"


class ApprovalAction(str, Enum):
    """Approval workflow actions."""
    APPROVE = "approve"
    MODIFY = "modify"
    ESCALATE = "escalate"
    REJECT = "reject"


class EscalationType(str, Enum):
    """Escalation types."""
    HOSTILE_LANGUAGE = "hostile_language"
    PAYMENT_DISPUTE = "payment_dispute"
    UNREALISTIC_PROPOSAL = "unrealistic_proposal"
    NO_RESPONSE = "no_response"
    LEGAL_THREAT = "legal_threat"
    MANUAL = "manual"


class PaymentPlanStatus(str, Enum):
    """Payment plan status types."""
    DETECTED = "detected"
    VALIDATING = "validating"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ACTIVE = "active"


# Request Models
class IncomingSMS(BaseModel):
    """Incoming SMS data from SMS Agent."""
    tenant_id: str = Field(..., description="Tenant identifier")
    phone_number: str = Field(..., description="Phone number in E.164 format")
    content: str = Field(..., min_length=1, max_length=1600, description="SMS message content")
    conversation_id: UUID = Field(..., description="Conversation identifier")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")
    direction: MessageType = Field(MessageType.INBOUND, description="Message direction")

    @validator("phone_number")
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number format."""
        if not v.startswith("+"):
            raise ValueError("Phone number must be in E.164 format (e.g., +1234567890)")
        return v


class ResponseApproval(BaseModel):
    """Manager approval for AI-generated response."""
    response_queue_id: UUID = Field(..., description="Response queue identifier")
    action: ApprovalAction = Field(..., description="Approval action")
    approved_text: Optional[str] = Field(None, description="Approved response text")
    modified_text: Optional[str] = Field(None, description="Modified response text")
    escalation_reason: Optional[str] = Field(None, description="Reason for escalation")
    manager_id: str = Field(..., description="Manager identifier")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator("approved_text")
    def validate_approval_text(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        """Validate approval text based on action."""
        if values.get("action") == ApprovalAction.APPROVE and not v:
            raise ValueError("approved_text is required when action is 'approve'")
        if values.get("action") == ApprovalAction.MODIFY and not values.get("modified_text"):
            raise ValueError("modified_text is required when action is 'modify'")
        return v


class PaymentPlanDetection(BaseModel):
    """Payment plan detection data."""
    conversation_id: UUID = Field(..., description="Conversation identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    message_content: str = Field(..., description="Original message content")
    ai_response: str = Field(..., description="AI response containing payment plan")
    weekly_amount: Optional[float] = Field(None, description="Weekly payment amount")
    weeks: Optional[int] = Field(None, description="Number of weeks")
    start_date: Optional[datetime] = Field(None, description="Plan start date")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Detection confidence")


class EscalationRequest(BaseModel):
    """Escalation request data."""
    conversation_id: UUID = Field(..., description="Conversation identifier")
    escalation_type: EscalationType = Field(..., description="Type of escalation")
    reason: str = Field(..., min_length=1, description="Escalation reason")
    severity: str = Field(..., pattern="^(low|medium|high|critical)$", description="Severity level")
    auto_detected: bool = Field(True, description="Whether escalation was auto-detected")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional escalation metadata")


class RetryRequest(BaseModel):
    """Workflow retry request."""
    reason: str = Field(..., min_length=1, description="Reason for retry")
    force_retry: bool = Field(False, description="Force retry even if not typically retriable")


# Response Models
class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    checks: Dict[str, Any] = Field(default_factory=dict, description="Health check details")


class DependencyHealthResponse(BaseModel):
    """Dependency health check response."""
    status: str = Field(..., description="Overall dependency health")
    services: Dict[str, Dict[str, Any]] = Field(..., description="Individual service health")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")


class WorkflowStatusResponse(BaseModel):
    """Workflow status response."""
    conversation_id: UUID = Field(..., description="Conversation identifier")
    workflow_id: UUID = Field(..., description="Workflow identifier")
    status: WorkflowStatus = Field(..., description="Current workflow status")
    created_at: datetime = Field(..., description="Workflow creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    current_step: str = Field(..., description="Current workflow step")
    steps_completed: List[str] = Field(default_factory=list, description="Completed steps")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional workflow metadata")


class AIResponse(BaseModel):
    """AI-generated response data."""
    content: str = Field(..., description="Generated response content")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    language: str = Field(default="english", description="Response language")
    model_used: str = Field(..., description="AI model used")
    processing_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds")
    payment_plan_detected: Optional[Dict[str, Any]] = Field(None, description="Detected payment plan")
    escalation_triggers: List[str] = Field(default_factory=list, description="Escalation triggers detected")


class MetricsResponse(BaseModel):
    """Service metrics response."""
    last_hour: Dict[str, Any] = Field(..., description="Last hour metrics")
    today: Dict[str, Any] = Field(..., description="Today's metrics")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Metrics timestamp")


# Database Models
class OrchestrationWorkflow(BaseModel):
    """Orchestration workflow database model."""
    id: UUID
    conversation_id: UUID
    workflow_type: str
    status: WorkflowStatus
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    metadata: Optional[Dict[str, Any]]


class AIResponseQueue(BaseModel):
    """AI response queue database model."""
    id: UUID
    conversation_id: UUID
    tenant_message: str
    ai_response: str
    confidence_score: float
    status: str
    manager_action: Optional[str]
    modified_response: Optional[str]
    actioned_by: Optional[str]
    actioned_at: Optional[datetime]
    created_at: datetime


class ApprovalAuditLog(BaseModel):
    """Approval audit log database model."""
    id: UUID
    response_queue_id: UUID
    action: str
    original_response: Optional[str]
    final_response: Optional[str]
    reason: Optional[str]
    approved_by: str
    created_at: datetime