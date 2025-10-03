"""
AI Response model for storing generated AI responses and metadata.
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class AIResponse(BaseModel):
    """AI response model containing generated response and metadata."""

    response_text: str = Field(..., description="Generated AI response text")
    confidence_score: Decimal = Field(
        ..., ge=0.0, le=1.0, description="AI confidence level (0.0-1.0)"
    )
    language_preference: str = Field(..., description="Tenant's preferred language")
    tokens_used: int = Field(..., ge=0, description="Number of API tokens used")
    response_metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional response metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Response creation timestamp"
    )

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class AIResponseQueue(BaseModel):
    """Queue item for pending AI responses awaiting approval."""

    id: Optional[UUID] = Field(default_factory=uuid4, description="Queue item ID")
    workflow_id: UUID = Field(..., description="Reference to parent workflow instance")
    tenant_id: str = Field(..., description="Tenant identifier")
    phone_number: str = Field(..., description="Tenant phone number")
    tenant_message: str = Field(..., description="Original SMS from tenant")
    ai_response: str = Field(
        ..., description="Generated AI response requiring approval"
    )
    confidence_score: Decimal = Field(
        ..., ge=0.0, le=1.0, description="AI confidence level"
    )
    status: str = Field(
        default="pending",
        description="Queue status (pending, approved, modified, escalated, auto_sent)",
    )
    approval_action: Optional[str] = Field(
        default=None, description="Manager action (approve, modify, escalate)"
    )
    modified_response: Optional[str] = Field(
        default=None, description="Manager-modified response if applicable"
    )
    actioned_by: Optional[str] = Field(
        default=None, description="Manager ID who handled the response"
    )
    actioned_at: Optional[datetime] = Field(
        default=None, description="When response was processed"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Queue entry creation time"
    )

    class Config:
        json_encoders = {UUID: str, Decimal: str, datetime: lambda v: v.isoformat()}


class ApprovalAuditLog(BaseModel):
    """Audit log for approval workflow actions."""

    id: Optional[UUID] = Field(default_factory=uuid4, description="Audit entry ID")
    response_queue_id: UUID = Field(..., description="Reference to queue item")
    action: str = Field(..., description="Action taken (approve, modify, escalate)")
    original_response: str = Field(..., description="Original AI response")
    final_response: str = Field(..., description="Final response sent to tenant")
    reason: Optional[str] = Field(
        default=None, description="Reason for modification or escalation"
    )
    approved_by: str = Field(..., description="Manager ID who approved/modified")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Audit entry creation time"
    )

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}
