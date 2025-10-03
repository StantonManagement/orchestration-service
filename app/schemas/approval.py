"""
Request and response schemas for approval workflow API endpoints.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import UUID
from decimal import Decimal
from datetime import datetime


class ResponseApprovalRequest(BaseModel):
    """Request schema for manager approval actions."""

    response_queue_id: UUID = Field(..., description="Queue item ID requiring approval")
    action: str = Field(..., description="Action: approve, modify, or escalate")
    manager_id: str = Field(..., description="Manager ID performing the action")
    approved_text: Optional[str] = Field(
        default=None, description="Original approved text (for approve action)"
    )
    modified_text: Optional[str] = Field(
        default=None, description="Modified response text (for modify action)"
    )
    escalation_reason: Optional[str] = Field(
        default=None, description="Reason for escalation (for escalate action)"
    )

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}


class ResponseApprovalResponse(BaseModel):
    """Response schema for approval actions."""

    success: bool = Field(..., description="Whether the approval action was successful")
    message: str = Field(..., description="Response message")
    queue_id: UUID = Field(..., description="Queue item ID")
    action: str = Field(..., description="Action performed")
    final_response: Optional[str] = Field(
        default=None, description="Final response text that was sent"
    )

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}


class ApprovalQueueItem(BaseModel):
    """Schema for approval queue items returned to managers."""

    id: UUID = Field(..., description="Queue item ID")
    workflow_id: UUID = Field(..., description="Workflow instance ID")
    tenant_id: str = Field(..., description="Tenant identifier")
    phone_number: str = Field(..., description="Tenant phone number")
    tenant_message: str = Field(..., description="Original SMS from tenant")
    ai_response: str = Field(
        ..., description="Generated AI response requiring approval"
    )
    confidence_score: Decimal = Field(..., description="AI confidence level")
    status: str = Field(..., description="Queue status")
    created_at: datetime = Field(..., description="Queue entry creation time")
    waiting_time_hours: float = Field(..., description="Hours waiting for approval")

    class Config:
        json_encoders = {UUID: str, Decimal: str, datetime: lambda v: v.isoformat()}


class PendingApprovalsResponse(BaseModel):
    """Response schema for pending approvals list."""

    pending_approvals: List[ApprovalQueueItem] = Field(
        ..., description="List of pending approval requests"
    )
    total_count: int = Field(..., description="Total number of pending approvals")

    class Config:
        json_encoders = {UUID: str, Decimal: str, datetime: lambda v: v.isoformat()}


class ApprovalAuditLogItem(BaseModel):
    """Schema for audit log entries."""

    id: UUID = Field(..., description="Audit log entry ID")
    response_queue_id: UUID = Field(..., description="Reference to queue item")
    action: str = Field(..., description="Action taken")
    original_response: str = Field(..., description="Original AI response")
    final_response: str = Field(..., description="Final response sent to tenant")
    reason: Optional[str] = Field(
        default=None, description="Reason for modification or escalation"
    )
    approved_by: str = Field(..., description="Manager ID who approved/modified")
    created_at: datetime = Field(..., description="Audit entry creation time")

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}


class AuditLogResponse(BaseModel):
    """Response schema for audit logs."""

    audit_logs: List[ApprovalAuditLogItem] = Field(
        ..., description="List of audit log entries"
    )
    total_count: int = Field(..., description="Total number of audit log entries")

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    success: bool = Field(default=False, description="Always false for error responses")
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(
        default=None, description="Error code for debugging"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error details"
    )

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}
