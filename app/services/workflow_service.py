import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from app.core.logging import get_logger
from app.models.workflow import (
    WorkflowInstance, WorkflowStep, WorkflowStatus, WorkflowType,
    StepType, StepStatus, WorkflowDB
)
from app.schemas.workflow import (
    WorkflowStatusResponse, WorkflowStepResponse, CreateWorkflowRequest,
    UpdateWorkflowStatusRequest, CreateWorkflowStepRequest,
    UpdateWorkflowStepRequest
)

logger = get_logger(__name__)


class WorkflowStateTransitionError(Exception):
    """Raised when invalid workflow state transition is attempted"""
    pass


class WorkflowService:
    """Service for workflow status tracking and state management"""

    def __init__(self):
        self.db = WorkflowDB()

        # Define valid state transitions
        self.valid_transitions = {
            WorkflowStatus.RECEIVED: [WorkflowStatus.PROCESSING, WorkflowStatus.FAILED],
            WorkflowStatus.PROCESSING: [
                WorkflowStatus.AWAITING_APPROVAL,
                WorkflowStatus.SENT,
                WorkflowStatus.ESCALATED,
                WorkflowStatus.FAILED,
                WorkflowStatus.COMPLETED
            ],
            WorkflowStatus.AWAITING_APPROVAL: [
                WorkflowStatus.SENT,
                WorkflowStatus.ESCALATED,
                WorkflowStatus.FAILED
            ],
            WorkflowStatus.SENT: [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED],
            WorkflowStatus.ESCALATED: [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED],
            WorkflowStatus.FAILED: [WorkflowStatus.PROCESSING, WorkflowStatus.ESCALATED],
            WorkflowStatus.COMPLETED: []  # Terminal state
        }

    def _validate_state_transition(self, current_status: WorkflowStatus,
                                 new_status: WorkflowStatus) -> bool:
        """Validate if state transition is allowed"""
        if current_status == new_status:
            return True

        valid_next_states = self.valid_transitions.get(current_status, [])
        return new_status in valid_next_states

    async def create_workflow_instance(self, request: CreateWorkflowRequest) -> WorkflowInstance:
        """Create a new workflow instance"""
        try:
            workflow = WorkflowInstance(
                conversation_id=request.conversation_id,
                workflow_type=request.workflow_type,
                status=WorkflowStatus.RECEIVED,
                tenant_id=request.tenant_id,
                phone_number=request.phone_number,
                metadata=request.metadata or {}
            )

            # Create initial step
            initial_step = WorkflowStep(
                workflow_id=workflow.id,
                step_name="workflow_created",
                step_type=StepType.DATABASE_OPERATION,
                status=StepStatus.COMPLETED,
                input_data={"request": request.model_dump()},
                output_data={"workflow_id": str(workflow.id)}
            )

            # Save to database
            await self.db.create_workflow_instance(workflow)
            await self.db.create_workflow_step(initial_step)

            logger.info(
                f"Created workflow instance {workflow.id} for conversation {request.conversation_id}",
                extra={
                    "workflow_id": str(workflow.id),
                    "conversation_id": str(request.conversation_id),
                    "tenant_id": request.tenant_id,
                    "workflow_type": request.workflow_type.value
                }
            )

            return workflow

        except Exception as e:
            logger.error(f"Failed to create workflow instance: {str(e)}")
            raise

    async def update_workflow_status(self, workflow_id: UUID,
                                   request: UpdateWorkflowStatusRequest) -> bool:
        """Update workflow status with audit trail"""
        try:
            # Get current workflow to validate transition
            current_workflow = await self.db.get_workflow_by_id(workflow_id)
            if not current_workflow:
                logger.error(f"Workflow {workflow_id} not found")
                return False

            # Validate state transition
            if not self._validate_state_transition(current_workflow.status, request.status):
                raise WorkflowStateTransitionError(
                    f"Invalid transition from {current_workflow.status} to {request.status}"
                )

            # Create status update step
            status_step = WorkflowStep(
                workflow_id=workflow_id,
                step_name=f"status_update_{request.status.value}",
                step_type=StepType.DATABASE_OPERATION,
                status=StepStatus.COMPLETED,
                input_data={"previous_status": current_workflow.status.value},
                output_data={"new_status": request.status.value, "error_message": request.error_message}
            )

            # Update workflow status
            success = await self.db.update_workflow_status(
                workflow_id, request.status, request.error_message, request.metadata
            )

            if success:
                await self.db.create_workflow_step(status_step)

                logger.info(
                    f"Updated workflow {workflow_id} status to {request.status.value}",
                    extra={
                        "workflow_id": str(workflow_id),
                        "previous_status": current_workflow.status.value,
                        "new_status": request.status.value,
                        "error_message": request.error_message
                    }
                )

            return success

        except WorkflowStateTransitionError as e:
            logger.error(f"Invalid workflow state transition: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to update workflow status: {str(e)}")
            return False

    async def get_workflow_status(self, conversation_id: UUID) -> Optional[WorkflowStatusResponse]:
        """Get workflow status with detailed step information"""
        try:
            workflow = await self.db.get_workflow_by_conversation(conversation_id)
            if not workflow:
                return None

            # Get workflow steps
            steps = await self.db.get_workflow_steps(workflow.id)

            # Calculate step counts and timing
            completed_steps = [s for s in steps if s.status == StepStatus.COMPLETED]
            current_step = None

            if steps:
                last_step = steps[-1]
                if last_step.status in [StepStatus.STARTED, StepStatus.FAILED]:
                    current_step = last_step.step_name

            # Estimate completion time based on average step duration
            estimated_completion = None
            if completed_steps and workflow.status not in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                avg_duration = sum(s.duration_ms or 0 for s in completed_steps) / len(completed_steps)
                remaining_steps = max(0, 6 - len(completed_steps))  # Estimate 6 total steps
                estimated_ms = avg_duration * remaining_steps
                estimated_completion = datetime.utcnow() + timedelta(milliseconds=estimated_ms)

            # Convert to response schema
            workflow_response = WorkflowStatusResponse(
                conversation_id=workflow.conversation_id,
                workflow_id=workflow.id,
                status=workflow.status,
                started_at=workflow.started_at,
                last_updated=workflow.completed_at or workflow.started_at,
                tenant_id=workflow.tenant_id,
                phone_number=workflow.phone_number,
                workflow_type=workflow.workflow_type,
                current_step=current_step,
                steps_completed=len(completed_steps),
                total_steps=max(len(steps), 6),  # Estimate 6 total steps
                estimated_completion=estimated_completion,
                workflow_steps=[
                    WorkflowStepResponse(
                        id=step.id,
                        step_name=step.step_name,
                        step_type=step.step_type,
                        status=step.status,
                        started_at=step.started_at,
                        completed_at=step.completed_at,
                        duration_ms=step.duration_ms,
                        error_details=step.error_details
                    ) for step in steps
                ],
                error_message=workflow.error_message,
                metadata=workflow.metadata
            )

            return workflow_response

        except Exception as e:
            logger.error(f"Failed to get workflow status: {str(e)}")
            return None

    async def create_workflow_step(self, workflow_id: UUID,
                                 request: CreateWorkflowStepRequest) -> UUID:
        """Create a new workflow step"""
        try:
            step = WorkflowStep(
                workflow_id=workflow_id,
                step_name=request.step_name,
                step_type=request.step_type,
                status=StepStatus.STARTED,
                input_data=request.input_data or {}
            )

            created_step = await self.db.create_workflow_step(step)

            logger.info(
                f"Created workflow step {request.step_name} for workflow {workflow_id}",
                extra={
                    "workflow_id": str(workflow_id),
                    "step_id": str(created_step.id),
                    "step_name": request.step_name,
                    "step_type": request.step_type.value
                }
            )

            return created_step.id

        except Exception as e:
            logger.error(f"Failed to create workflow step: {str(e)}")
            raise

    async def update_workflow_step(self, step_id: UUID,
                                 request: UpdateWorkflowStepRequest) -> bool:
        """Update workflow step status"""
        try:
            success = await self.db.update_step_status(
                step_id, request.status, request.output_data, request.error_details
            )

            if success:
                logger.info(
                    f"Updated workflow step {step_id} status to {request.status.value}",
                    extra={
                        "step_id": str(step_id),
                        "new_status": request.status.value,
                        "has_output": request.output_data is not None,
                        "has_error": request.error_details is not None
                    }
                )

            return success

        except Exception as e:
            logger.error(f"Failed to update workflow step: {str(e)}")
            return False

    async def handle_workflow_recovery(self, workflow_id: UUID,
                                     error_context: Dict[str, Any]) -> bool:
        """Handle workflow recovery from error state"""
        try:
            # Get current workflow
            workflow = await self.db.get_workflow_by_id(workflow_id)
            if not workflow:
                return False

            # Only recover from failed state
            if workflow.status != WorkflowStatus.FAILED:
                logger.warning(f"Cannot recover workflow {workflow_id} from status {workflow.status}")
                return False

            # Determine recovery strategy based on error context
            recovery_strategy = error_context.get("recovery_strategy", "retry")

            if recovery_strategy == "retry":
                # Reset to processing state
                recovery_step = WorkflowStep(
                    workflow_id=workflow_id,
                    step_name="workflow_recovery",
                    step_type=StepType.DATABASE_OPERATION,
                    status=StepStatus.COMPLETED,
                    input_data={"error_context": error_context},
                    output_data={"recovery_action": "retry", "timestamp": datetime.utcnow().isoformat()}
                )

                await self.db.create_workflow_step(recovery_step)
                success = await self.db.update_workflow_status(
                    workflow_id, WorkflowStatus.PROCESSING,
                    metadata={"recovery_attempt": True}
                )

                if success:
                    logger.info(
                        f"Recovered workflow {workflow_id} to processing state",
                        extra={
                            "workflow_id": str(workflow_id),
                            "recovery_strategy": recovery_strategy,
                            "error_context": error_context
                        }
                    )

                return success

            elif recovery_strategy == "escalate":
                # Escalate workflow
                return await self.update_workflow_status(
                    workflow_id,
                    UpdateWorkflowStatusRequest(status=WorkflowStatus.ESCALATED)
                )

            else:
                logger.error(f"Unknown recovery strategy: {recovery_strategy}")
                return False

        except Exception as e:
            logger.error(f"Failed to handle workflow recovery: {str(e)}")
            return False

    async def cleanup_old_workflows(self, days_to_keep: int = 30) -> int:
        """Clean up old completed workflows"""
        try:
            cleaned_count = await self.db.cleanup_old_workflows(days_to_keep)

            logger.info(
                f"Cleaned up {cleaned_count} old workflows older than {days_to_keep} days"
            )

            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup old workflows: {str(e)}")
            return 0