from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from app.database import get_supabase_client


class WorkflowStatus(str, Enum):
    """Workflow status enumeration"""
    RECEIVED = "received"
    PROCESSING = "processing"
    AWAITING_APPROVAL = "awaiting_approval"
    SENT = "sent"
    ESCALATED = "escalated"
    FAILED = "failed"
    COMPLETED = "completed"


class WorkflowType(str, Enum):
    """Workflow type enumeration"""
    SMS_PROCESSING = "sms_processing"
    PAYMENT_PLAN_VALIDATION = "payment_plan_validation"
    ESCALATION = "escalation"


class StepType(str, Enum):
    """Workflow step type enumeration"""
    API_CALL = "api_call"
    AI_PROCESSING = "ai_processing"
    DATABASE_OPERATION = "database_operation"
    NOTIFICATION = "notification"


class StepStatus(str, Enum):
    """Workflow step status enumeration"""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowInstance(BaseModel):
    """Workflow instance model for database operations"""
    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    workflow_type: WorkflowType
    status: WorkflowStatus
    tenant_id: str
    phone_number: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class WorkflowStep(BaseModel):
    """Workflow step model for database operations"""
    id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    step_name: str
    step_type: StepType
    status: StepStatus
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_details: Optional[Dict[str, Any]] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class WorkflowDB:
    """Database operations for workflow instances and steps"""

    def __init__(self):
        self.supabase = get_supabase_client()

    async def create_workflow_instance(self, workflow: WorkflowInstance) -> WorkflowInstance:
        """Create a new workflow instance in database"""
        try:
            response = self.supabase.table('workflow_instances').insert({
                'id': str(workflow.id),
                'conversation_id': str(workflow.conversation_id),
                'workflow_type': workflow.workflow_type.value,
                'status': workflow.status.value,
                'tenant_id': workflow.tenant_id,
                'phone_number': workflow.phone_number,
                'started_at': workflow.started_at.isoformat(),
                'completed_at': workflow.completed_at.isoformat() if workflow.completed_at else None,
                'error_message': workflow.error_message,
                'metadata': workflow.metadata
            }).execute()

            return workflow
        except Exception as e:
            raise Exception(f"Failed to create workflow instance: {str(e)}")

    async def update_workflow_status(self, workflow_id: UUID, status: WorkflowStatus,
                                    error_message: Optional[str] = None,
                                    metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update workflow status in database"""
        try:
            update_data = {
                'status': status.value,
                'updated_at': datetime.utcnow().isoformat()
            }

            if error_message:
                update_data['error_message'] = error_message

            if metadata:
                update_data['metadata'] = metadata

            if status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.SENT]:
                update_data['completed_at'] = datetime.utcnow().isoformat()

            response = self.supabase.table('workflow_instances').update(
                update_data
            ).eq('id', str(workflow_id)).execute()

            return len(response.data) > 0
        except Exception as e:
            raise Exception(f"Failed to update workflow status: {str(e)}")

    async def get_workflow_by_id(self, workflow_id: UUID) -> Optional[WorkflowInstance]:
        """Get workflow instance by workflow ID"""
        try:
            response = self.supabase.table('workflow_instances').select(
                '*'
            ).eq('id', str(workflow_id)).single().execute()

            if response.data:
                return WorkflowInstance(**response.data)
            return None
        except Exception as e:
            raise Exception(f"Failed to get workflow by ID: {str(e)}")

    async def get_workflow_by_conversation(self, conversation_id: UUID) -> Optional[WorkflowInstance]:
        """Get workflow instance by conversation ID"""
        try:
            response = self.supabase.table('workflow_instances').select(
                '*'
            ).eq('conversation_id', str(conversation_id)).single().execute()

            if response.data:
                return WorkflowInstance(**response.data)
            return None
        except Exception as e:
            raise Exception(f"Failed to get workflow by conversation: {str(e)}")

    async def create_workflow_step(self, step: WorkflowStep) -> WorkflowStep:
        """Create a new workflow step in database"""
        try:
            # Calculate duration if step is completed
            if step.completed_at:
                step.duration_ms = int((step.completed_at - step.started_at).total_seconds() * 1000)

            response = self.supabase.table('workflow_steps').insert({
                'id': str(step.id),
                'workflow_id': str(step.workflow_id),
                'step_name': step.step_name,
                'step_type': step.step_type.value,
                'status': step.status.value,
                'input_data': step.input_data,
                'output_data': step.output_data,
                'error_details': step.error_details,
                'started_at': step.started_at.isoformat(),
                'completed_at': step.completed_at.isoformat() if step.completed_at else None,
                'duration_ms': step.duration_ms
            }).execute()

            return step
        except Exception as e:
            raise Exception(f"Failed to create workflow step: {str(e)}")

    async def get_workflow_steps(self, workflow_id: UUID) -> List[WorkflowStep]:
        """Get all steps for a workflow instance"""
        try:
            response = self.supabase.table('workflow_steps').select(
                '*'
            ).eq('workflow_id', str(workflow_id)).order('started_at').execute()

            return [WorkflowStep(**step) for step in response.data]
        except Exception as e:
            raise Exception(f"Failed to get workflow steps: {str(e)}")

    async def update_step_status(self, step_id: UUID, status: StepStatus,
                                output_data: Optional[Dict[str, Any]] = None,
                                error_details: Optional[Dict[str, Any]] = None) -> bool:
        """Update workflow step status"""
        try:
            update_data = {'status': status.value}

            if output_data:
                update_data['output_data'] = output_data

            if error_details:
                update_data['error_details'] = error_details

            if status in [StepStatus.COMPLETED, StepStatus.FAILED]:
                update_data['completed_at'] = datetime.utcnow().isoformat()

            response = self.supabase.table('workflow_steps').update(
                update_data
            ).eq('id', str(step_id)).execute()

            return len(response.data) > 0
        except Exception as e:
            raise Exception(f"Failed to update step status: {str(e)}")

    async def cleanup_old_workflows(self, days_to_keep: int = 30) -> int:
        """Clean up old completed workflows"""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days_to_keep)).isoformat()

            # Delete old workflow steps first
            steps_response = self.supabase.table('workflow_steps').delete().lt(
                'started_at', cutoff_date
            ).execute()

            # Then delete old workflow instances
            instances_response = self.supabase.table('workflow_instances').delete().lt(
                'started_at', cutoff_date
            ).execute()

            return len(instances_response.data)
        except Exception as e:
            raise Exception(f"Failed to cleanup old workflows: {str(e)}")