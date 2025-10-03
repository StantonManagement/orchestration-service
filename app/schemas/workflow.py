from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field
from app.models.workflow import WorkflowStatus, WorkflowType, StepType, StepStatus


class WorkflowStepResponse(BaseModel):
    """Workflow step response schema"""
    id: UUID
    step_name: str
    step_type: StepType
    status: StepStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_details: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class WorkflowStatusResponse(BaseModel):
    """Workflow status response schema"""
    conversation_id: UUID
    workflow_id: UUID
    status: WorkflowStatus
    started_at: datetime
    last_updated: datetime
    tenant_id: str
    phone_number: str
    workflow_type: WorkflowType
    current_step: Optional[str] = None
    steps_completed: int = 0
    total_steps: int = 0
    estimated_completion: Optional[datetime] = None
    workflow_steps: List[WorkflowStepResponse] = []
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class CreateWorkflowRequest(BaseModel):
    """Create workflow request schema"""
    conversation_id: UUID
    tenant_id: str
    phone_number: str
    workflow_type: WorkflowType = WorkflowType.SMS_PROCESSING
    metadata: Optional[Dict[str, Any]] = None


class UpdateWorkflowStatusRequest(BaseModel):
    """Update workflow status request schema"""
    status: WorkflowStatus
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CreateWorkflowStepRequest(BaseModel):
    """Create workflow step request schema"""
    step_name: str
    step_type: StepType
    input_data: Optional[Dict[str, Any]] = None


class UpdateWorkflowStepRequest(BaseModel):
    """Update workflow step request schema"""
    status: StepStatus
    output_data: Optional[Dict[str, Any]] = None
    error_details: Optional[Dict[str, Any]] = None