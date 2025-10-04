"""
Escalation API endpoints for Story 2.2

REST API endpoints for managing escalation workflows, including manual escalations,
status checking, and monitoring endpoints as per requirements.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from app.models.schemas import (
    ApiResponse,
    EscalationRequest,
    EscalationResponse
)
from app.services.escalation_service import EscalationService
from app.core.exceptions import EscalationError, ExternalServiceError
from app.core.dependencies import get_escalation_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.post("/trigger", response_model=ApiResponse[EscalationResponse])
async def trigger_manual_escalation(
    request: EscalationRequest,
    background_tasks: BackgroundTasks,
    escalation_service: EscalationService = Depends(get_escalation_service)
):
    """
    Trigger manual escalation for a workflow.

    This endpoint allows internal staff to manually trigger an escalation
    when they determine a customer interaction requires human intervention.

    Args:
        request: Manual escalation request details
        background_tasks: FastAPI background tasks
        escalation_service: Escalation service instance

    Returns:
        Escalation response with details

    Raises:
        HTTPException: If escalation fails
    """
    try:
        logger.info(
            "Manual escalation request received",
            workflow_id=request.workflow_id,
            customer_phone=request.customer_phone,
            reason=request.reason
        )

        # Process the escalation
        response = await escalation_service.process_escalation_request(request)

        # Log successful escalation
        logger.info(
            "Manual escalation processed successfully",
            escalation_id=response.escalation_id,
            workflow_id=request.workflow_id
        )

        return ApiResponse(
            success=True,
            data=response,
            message="Manual escalation triggered successfully",
            timestamp=datetime.utcnow()
        )

    except EscalationError as e:
        logger.error(
            "Manual escalation failed",
            workflow_id=request.workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Escalation processing failed: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Unexpected error in manual escalation",
            workflow_id=request.workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during escalation processing"
        )














