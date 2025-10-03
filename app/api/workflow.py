from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID
from typing import List

from app.core.logging import get_logger
from app.schemas.workflow import WorkflowStatusResponse
from app.services.workflow_service import WorkflowService

logger = get_logger(__name__)
router = APIRouter()
workflow_service = WorkflowService()


@router.get("/orchestrate/workflow/{conversation_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(conversation_id: UUID):
    """Get workflow status for a conversation"""
    try:
        workflow_status = await workflow_service.get_workflow_status(conversation_id)

        if not workflow_status:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow not found for conversation: {conversation_id}"
            )

        logger.info(
            f"Retrieved workflow status for conversation {conversation_id}",
            extra={
                "conversation_id": str(conversation_id),
                "workflow_id": str(workflow_status.workflow_id),
                "status": workflow_status.status.value,
                "steps_completed": workflow_status.steps_completed
            }
        )

        return workflow_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow status for conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving workflow status"
        )


@router.get("/orchestrate/workflows", response_model=List[WorkflowStatusResponse])
async def list_workflows():
    """List all workflows (admin endpoint)"""
    try:
        # This would be implemented with pagination and filtering in a real system
        # For now, return empty list as this is not part of the current requirements
        logger.info("Listing workflows (admin endpoint)")
        return []

    except Exception as e:
        logger.error(f"Failed to list workflows: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while listing workflows"
        )