"""
Pydantic models for incoming SMS data validation.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class IncomingSMS(BaseModel):
    """Incoming SMS request schema."""

    tenant_id: str = Field(
        ..., description="Tenant identifier from Collections Monitor", min_length=1
    )
    phone_number: str = Field(..., description="Tenant phone number", min_length=1)
    content: str = Field(..., description="SMS message content", min_length=1)
    conversation_id: str = Field(
        ..., description="Conversation ID linking to SMS Agent", min_length=1
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id_format(cls, v):
        """Validate that conversation_id is in a reasonable format (UUID-like)."""
        try:
            # Try to parse as UUID to ensure proper format
            uuid.UUID(v)
        except ValueError:
            # If not a valid UUID, check if it's at least a reasonable identifier
            if len(v) < 3 or not v.replace("-", "").replace("_", "").isalnum():
                raise ValueError("conversation_id must be a valid UUID or identifier")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v):
        """Basic phone number validation."""
        # Remove spaces, dashes, parentheses for basic validation
        cleaned = v.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not cleaned.startswith("+") and not cleaned.isdigit():
            raise ValueError(
                "phone_number must start with + for international format or contain only digits"
            )
        if len(cleaned) < 10:
            raise ValueError("phone_number appears too short for a valid phone number")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "tenant_id": "12345",
                "phone_number": "+1234567890",
                "content": "I can pay $200 per week",
                "conversation_id": "conv-uuid-123",
            }
        }
    }


class SMSResponse(BaseModel):
    """Response model for SMS processing."""

    status: str = Field(default="processed", description="Processing status")
    conversation_id: str = Field(..., description="Echo back the conversation ID")
    workflow_id: str = Field(..., description="Generated workflow ID for tracking")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Processing timestamp"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "processed",
                "conversation_id": "conv-uuid-123",
                "workflow_id": "workflow-uuid-456",
                "timestamp": "2023-10-02T16:30:00Z",
            }
        }
    }
