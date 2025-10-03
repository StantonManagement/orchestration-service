"""
Payment Plan API Schemas

Pydantic models for payment plan request/response validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PaymentPlanDetectedRequest(BaseModel):
    """Request schema for payment plan detection endpoint"""

    conversation_id: UUID = Field(..., description="Conversation identifier")
    tenant_id: str = Field(..., min_length=1, max_length=100, description="Tenant identifier")
    message_content: str = Field(
        ..., min_length=1, max_length=5000, description="Original message content"
    )
    ai_response: Optional[str] = Field(
        None, max_length=5000, description="AI-generated response with payment plan"
    )
    tenant_context: Optional[Dict[str, Any]] = Field(
        None, description="Optional tenant context for validation"
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v):
        """Validate conversation_id format"""
        if not v:
            raise ValueError("conversation_id cannot be empty")
        return v

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v):
        """Validate tenant_id format"""
        if not v or not v.strip():
            raise ValueError("tenant_id cannot be empty")
        return v.strip()

    @field_validator("message_content")
    @classmethod
    def validate_message_content(cls, v):
        """Validate message_content"""
        if not v or not v.strip():
            raise ValueError("message_content cannot be empty")
        return v.strip()


class ValidationErrorResponse(BaseModel):
    """Individual validation error response"""

    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Error message")
    severity: str = Field(..., description="Error severity: error, warning, info")
    rule_code: str = Field(..., description="Validation rule code")


class PaymentPlanResponse(BaseModel):
    """Payment plan data response"""

    weekly_amount: Optional[Decimal] = Field(None, description="Weekly payment amount")
    duration_weeks: Optional[int] = Field(None, description="Payment plan duration in weeks")
    start_date: Optional[datetime] = Field(None, description="Payment plan start date")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")
    extracted_from: str = Field(..., description="Source: tenant_message or ai_response")
    extraction_patterns: List[str] = Field(
        default_factory=list, description="Patterns used for extraction"
    )


class ValidationResultResponse(BaseModel):
    """Validation result response"""

    status: str = Field(
        ..., description="Validation status: valid, invalid, needs_review, auto_approved"
    )
    is_valid: bool = Field(..., description="Whether the payment plan passed validation")
    is_auto_approvable: bool = Field(
        ..., description="Whether the payment plan can be auto-approved"
    )
    errors: List[ValidationErrorResponse] = Field(
        default_factory=list, description="Validation errors"
    )
    warnings: List[ValidationErrorResponse] = Field(
        default_factory=list, description="Validation warnings"
    )
    validation_summary: str = Field(..., description="Human-readable validation summary")


class PaymentPlanDetectedResponse(BaseModel):
    """Response schema for payment plan detection endpoint"""

    success: bool = Field(..., description="Whether payment plan was detected and processed")
    payment_plan: Optional[PaymentPlanResponse] = Field(
        None, description="Extracted payment plan details"
    )
    validation: Optional[ValidationResultResponse] = Field(None, description="Validation results")
    payment_plan_id: Optional[UUID] = Field(None, description="Database ID of stored payment plan")
    workflow_id: Optional[UUID] = Field(None, description="Associated workflow ID")
    message: str = Field(..., description="Response message")


class PaymentPlanListItem(BaseModel):
    """Payment plan item for list responses"""

    id: UUID = Field(..., description="Payment plan ID")
    workflow_id: UUID = Field(..., description="Associated workflow ID")
    weekly_amount: Optional[Decimal] = Field(None, description="Weekly payment amount")
    duration_weeks: Optional[int] = Field(None, description="Duration in weeks")
    start_date: Optional[datetime] = Field(None, description="Start date")
    status: str = Field(..., description="Payment plan status")
    extracted_from: str = Field(..., description="Source of extraction")
    confidence_score: float = Field(..., description="Confidence score")
    created_at: datetime = Field(..., description="Creation timestamp")
    validation_status: Optional[str] = Field(None, description="Validation status")
    is_auto_approvable: bool = Field(default=False, description="Whether auto-approvable")


class PaymentPlanListResponse(BaseModel):
    """Response for payment plan list endpoint"""

    payment_plans: List[PaymentPlanListItem] = Field(..., description="List of payment plans")
    total_count: int = Field(..., description="Total number of payment plans")
    limit: int = Field(..., description="Number of items returned")
    offset: int = Field(..., description="Starting offset")
