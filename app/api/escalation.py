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
    EscalationResponse,
    EscalationStatusResponse,
    EscalationStatisticsResponse
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


@router.get("/status/{workflow_id}", response_model=ApiResponse[EscalationStatusResponse])
async def get_escalation_status(
    workflow_id: str,
    escalation_service: EscalationService = Depends(get_escalation_service)
):
    """
    Get escalation status for a specific workflow.

    Provides current escalation status, timeout information, and
    any active escalation triggers for the specified workflow.

    Args:
        workflow_id: Workflow identifier to check
        escalation_service: Escalation service instance

    Returns:
        Escalation status information

    Raises:
        HTTPException: If workflow not found or status check fails
    """
    try:
        logger.info(
            "Escalation status request",
            workflow_id=workflow_id
        )

        # Get timeout information
        timeout_info = escalation_service.timeout_monitor.get_workflow_timeout(workflow_id)

        if not timeout_info:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found or not being monitored"
            )

        # Prepare status response
        status_response = EscalationStatusResponse(
            workflow_id=workflow_id,
            customer_phone=timeout_info.customer_phone,
            last_ai_response=timeout_info.last_ai_response,
            timeout_hours=int(timeout_info.timeout_threshold.total_seconds() // 3600),
            hours_remaining=max(0, int(timeout_info.time_remaining.total_seconds() // 3600)),
            status=timeout_info.status.value,
            escalation_triggered=timeout_info.escalation_triggered,
            warning_sent=timeout_info.warning_sent,
            created_at=timeout_info.created_at,
            updated_at=timeout_info.updated_at
        )

        logger.info(
            "Escalation status retrieved",
            workflow_id=workflow_id,
            status=timeout_info.status.value,
            hours_remaining=status_response.hours_remaining
        )

        return ApiResponse(
            success=True,
            data=status_response,
            message="Escalation status retrieved successfully",
            timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error retrieving escalation status",
            workflow_id=workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error retrieving escalation status"
        )


@router.get("/statistics", response_model=ApiResponse[EscalationStatisticsResponse])
async def get_escalation_statistics(
    escalation_service: EscalationService = Depends(get_escalation_service)
):
    """
    Get comprehensive escalation monitoring statistics.

    Provides statistics about active workflows, timeout monitoring,
    escalation triggers, and system health for monitoring dashboards.

    Args:
        escalation_service: Escalation service instance

    Returns:
        Escalation statistics and monitoring data
    """
    try:
        logger.info("Escalation statistics request")

        # Get comprehensive statistics
        stats = await escalation_service.get_escalation_statistics()

        # Prepare response
        stats_response = EscalationStatisticsResponse(
            total_active_workflows=stats["total_active_workflows"],
            expired_workflows=stats["expired_workflows"],
            warning_workflows=stats["workflows_near_timeout"],
            escalated_workflows=stats["escalated_workflows"],
            escalated_today=stats["escalated_today"],
            timeout_threshold_hours=stats["timeout_threshold_hours"],
            monitoring_active=stats["escalation_service_active"],
            timestamp=datetime.utcnow()
        )

        logger.info(
            "Escalation statistics retrieved",
            total_active=stats["total_active_workflows"],
            expired=stats["expired_workflows"],
            warnings=stats["workflows_near_timeout"]
        )

        return ApiResponse(
            success=True,
            data=stats_response,
            message="Escalation statistics retrieved successfully",
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(
            "Error retrieving escalation statistics",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error retrieving statistics"
        )


@router.post("/check-timeouts", response_model=ApiResponse[Dict[str, Any]])
async def check_timeout_escalations(
    background_tasks: BackgroundTasks,
    escalation_service: EscalationService = Depends(get_escalation_service)
):
    """
    Manually trigger timeout escalation check.

    This endpoint allows manual triggering of timeout-based escalation
    checks, useful for testing or when the automated check may have missed
    workflows due to system issues.

    Args:
        background_tasks: FastAPI background tasks
        escalation_service: Escalation service instance

    Returns:
        Results of timeout check including any triggered escalations
    """
    try:
        logger.info("Manual timeout escalation check requested")

        # Perform timeout check
        escalations_triggered = await escalation_service.check_timeout_escalations()

        response_data = {
            "escalations_triggered": len(escalations_triggered),
            "escalation_details": escalations_triggered,
            "check_timestamp": datetime.utcnow().isoformat()
        }

        logger.info(
            "Manual timeout check completed",
            escalations_triggered=len(escalations_triggered)
        )

        return ApiResponse(
            success=True,
            data=response_data,
            message="Timeout escalation check completed",
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(
            "Error during manual timeout check",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during timeout check"
        )


@router.post("/register-timeout", response_model=ApiResponse[Dict[str, str]])
async def register_workflow_timeout(
    workflow_id: str,
    customer_phone: str,
    last_ai_response: datetime,
    escalation_service: EscalationService = Depends(get_escalation_service)
):
    """
    Register a workflow for timeout monitoring.

    This endpoint is typically called by the main orchestration service
    when a new workflow is started or when an AI response is sent.

    Args:
        workflow_id: Workflow identifier
        customer_phone: Customer phone number
        last_ai_response: Timestamp of last AI response
        escalation_service: Escalation service instance

    Returns:
        Registration confirmation

    Raises:
        HTTPException: If registration fails
    """
    try:
        logger.info(
            "Workflow timeout registration request",
            workflow_id=workflow_id,
            customer_phone=customer_phone,
            last_response_time=last_ai_response.isoformat()
        )

        await escalation_service.register_workflow_timeout(
            workflow_id=workflow_id,
            customer_phone=customer_phone,
            last_ai_response=last_ai_response
        )

        response_data = {
            "workflow_id": workflow_id,
            "status": "registered_for_monitoring",
            "message": "Workflow successfully registered for timeout monitoring"
        }

        logger.info(
            "Workflow timeout registered successfully",
            workflow_id=workflow_id
        )

        return ApiResponse(
            success=True,
            data=response_data,
            message="Workflow timeout monitoring registered",
            timestamp=datetime.utcnow()
        )

    except EscalationError as e:
        logger.error(
            "Workflow timeout registration failed",
            workflow_id=workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Timeout registration failed: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Unexpected error in timeout registration",
            workflow_id=workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during timeout registration"
        )


@router.put("/update-timeout/{workflow_id}", response_model=ApiResponse[Dict[str, str]])
async def update_workflow_timeout(
    workflow_id: str,
    response_time: datetime,
    escalation_service: EscalationService = Depends(get_escalation_service)
):
    """
    Update workflow timeout with new response time.

    This endpoint is called when a new AI response is sent, resetting
    the timeout clock for the specified workflow.

    Args:
        workflow_id: Workflow identifier
        response_time: New response timestamp
        escalation_service: Escalation service instance

    Returns:
        Update confirmation

    Raises:
        HTTPException: If update fails or workflow not found
    """
    try:
        logger.info(
            "Workflow timeout update request",
            workflow_id=workflow_id,
            response_time=response_time.isoformat()
        )

        await escalation_service.update_workflow_response(
            workflow_id=workflow_id,
            response_time=response_time
        )

        response_data = {
            "workflow_id": workflow_id,
            "status": "timeout_updated",
            "new_response_time": response_time.isoformat(),
            "message": "Workflow timeout updated successfully"
        }

        logger.info(
            "Workflow timeout updated successfully",
            workflow_id=workflow_id,
            new_response_time=response_time.isoformat()
        )

        return ApiResponse(
            success=True,
            data=response_data,
            message="Workflow timeout updated",
            timestamp=datetime.utcnow()
        )

    except EscalationError as e:
        logger.error(
            "Workflow timeout update failed",
            workflow_id=workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Timeout update failed: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Unexpected error in timeout update",
            workflow_id=workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during timeout update"
        )


@router.delete("/remove/{workflow_id}", response_model=ApiResponse[Dict[str, str]])
async def remove_workflow_monitoring(
    workflow_id: str,
    escalation_service: EscalationService = Depends(get_escalation_service)
):
    """
    Remove workflow from all escalation monitoring.

    This endpoint is called when a workflow is completed, cancelled,
    or otherwise no longer requires escalation monitoring.

    Args:
        workflow_id: Workflow identifier
        escalation_service: Escalation service instance

    Returns:
        Removal confirmation

    Raises:
        HTTPException: If removal fails
    """
    try:
        logger.info(
            "Workflow monitoring removal request",
            workflow_id=workflow_id
        )

        await escalation_service.remove_workflow_monitoring(workflow_id)

        response_data = {
            "workflow_id": workflow_id,
            "status": "monitoring_removed",
            "message": "Workflow removed from escalation monitoring"
        }

        logger.info(
            "Workflow monitoring removed successfully",
            workflow_id=workflow_id
        )

        return ApiResponse(
            success=True,
            data=response_data,
            message="Workflow monitoring removed",
            timestamp=datetime.utcnow()
        )

    except EscalationError as e:
        logger.error(
            "Workflow monitoring removal failed",
            workflow_id=workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Monitoring removal failed: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Unexpected error in monitoring removal",
            workflow_id=workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during monitoring removal"
        )


@router.get("/health", response_model=ApiResponse[Dict[str, Any]])
async def escalation_health_check(
    escalation_service: EscalationService = Depends(get_escalation_service)
):
    """
    Health check endpoint for escalation service.

    Provides system health status including monitoring service status,
    recent activity, and system readiness for monitoring operations.

    Args:
        escalation_service: Escalation service instance

    Returns:
        Health status information
    """
    try:
        # Get basic statistics
        stats = await escalation_service.get_escalation_statistics()

        health_data = {
            "status": "healthy",
            "monitoring_active": stats["monitoring_active"],
            "active_workflows": stats["total_active_workflows"],
            "escalation_service_ready": True,
            "last_check": datetime.utcnow().isoformat(),
            "version": "2.2.0"
        }

        return ApiResponse(
            success=True,
            data=health_data,
            message="Escalation service is healthy",
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(
            "Escalation health check failed",
            error=str(e),
            exc_info=True
        )

        health_data = {
            "status": "unhealthy",
            "error": str(e),
            "last_check": datetime.utcnow().isoformat(),
            "version": "2.2.0"
        }

        return ApiResponse(
            success=False,
            data=health_data,
            message="Escalation service health check failed",
            timestamp=datetime.utcnow()
        )