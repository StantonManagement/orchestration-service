"""
Approval workflow API endpoints for manager approval processing.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends

from app.schemas.approval import (
    ResponseApprovalRequest,
    ResponseApprovalResponse,
    PendingApprovalsResponse,
    ApprovalQueueItem,
    AuditLogResponse,
    ApprovalAuditLogItem,
    ErrorResponse,
)
from app.services.approval_service import ApprovalService
import structlog

logger = structlog.get_logger(__name__)

# Create router
router = APIRouter(prefix="/orchestrate", tags=["approval"])


# Dependency injection for approval service
def get_approval_service() -> ApprovalService:
    """Get approval service instance."""
    return ApprovalService()


@router.post(
    "/approve-response",
    response_model=ResponseApprovalResponse,
    responses={
        200: {"description": "Approval action processed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Queue entry not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Process manager approval action",
    description="Process manager approval, modification, or escalation of AI responses",
)
async def approve_response(
    request: ResponseApprovalRequest,
    approval_service: ApprovalService = Depends(get_approval_service),
) -> ResponseApprovalResponse:
    """
    Process manager approval action for AI responses.

    This endpoint allows managers to approve, modify, or escalate AI-generated responses
    that have been queued for review based on confidence scores.
    """
    try:
        # Validate action
        valid_actions = ["approve", "modify", "escalate"]
        if request.action not in valid_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Invalid action '{request.action}'. Valid actions: {valid_actions}",
                    "error_code": "INVALID_ACTION",
                },
            )

        # Validate required fields for specific actions
        if request.action == "modify" and not request.modified_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "modified_text is required for modify action",
                    "error_code": "MISSING_MODIFIED_TEXT",
                },
            )

        # Get queue entry to validate it exists
        queue_entry = approval_service.get_queue_entry(request.response_queue_id)
        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Queue entry not found",
                    "error_code": "QUEUE_ENTRY_NOT_FOUND",
                },
            )

        # Process approval action
        success = await approval_service.process_approval_action(
            queue_id=request.response_queue_id,
            action=request.action,
            manager_id=request.manager_id,
            modified_text=request.modified_text,
            escalation_reason=request.escalation_reason,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Failed to process approval action. Entry may have already been processed.",
                    "error_code": "ACTION_PROCESSING_FAILED",
                },
            )

        # Get final response for the response
        final_response = None
        if request.action == "approve":
            final_response = request.approved_text or queue_entry.ai_response
        elif request.action == "modify":
            final_response = request.modified_text
        elif request.action == "escalate":
            final_response = queue_entry.ai_response

        logger.info(
            "Approval action processed successfully",
            queue_id=str(request.response_queue_id),
            action=request.action,
            manager_id=request.manager_id,
            correlation_id=str(request.response_queue_id),
        )

        return ResponseApprovalResponse(
            success=True,
            message=f"Response {request.action}d successfully",
            queue_id=request.response_queue_id,
            action=request.action,
            final_response=final_response,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error processing approval action",
            queue_id=str(request.response_queue_id),
            action=request.action,
            manager_id=request.manager_id,
            error=str(e),
            correlation_id=str(request.response_queue_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Internal server error", "error_code": "INTERNAL_ERROR"},
        )


@router.get(
    "/pending-approvals",
    response_model=PendingApprovalsResponse,
    responses={
        200: {"description": "Pending approvals retrieved successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get pending approval requests",
    description="Retrieve all AI responses waiting for manager approval",
)
async def get_pending_approvals(
    approval_service: ApprovalService = Depends(get_approval_service),
) -> PendingApprovalsResponse:
    """
    Get all pending approval requests for manager dashboard.

    Returns a list of AI responses that are waiting for manager approval,
    ordered by creation time (oldest first).
    """
    try:
        pending_approvals = await approval_service.get_pending_approvals()

        # Convert to response schema with waiting time calculation
        approval_items = []
        for entry in pending_approvals:
            waiting_time_hours = (
                datetime.utcnow() - entry.created_at
            ).total_seconds() / 3600

            item = ApprovalQueueItem(
                id=entry.id,
                workflow_id=entry.workflow_id,
                tenant_id=entry.tenant_id,
                phone_number=entry.phone_number,
                tenant_message=entry.tenant_message,
                ai_response=entry.ai_response,
                confidence_score=entry.confidence_score,
                status=entry.status,
                created_at=entry.created_at,
                waiting_time_hours=round(waiting_time_hours, 2),
            )
            approval_items.append(item)

        logger.info("Pending approvals retrieved", total_count=len(approval_items))

        return PendingApprovalsResponse(
            pending_approvals=approval_items, total_count=len(approval_items)
        )

    except Exception as e:
        logger.error("Error retrieving pending approvals", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to retrieve pending approvals",
                "error_code": "RETRIEVAL_ERROR",
            },
        )


@router.get(
    "/audit-logs",
    response_model=AuditLogResponse,
    responses={
        200: {"description": "Audit logs retrieved successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get approval audit logs",
    description="Retrieve audit log of all approval actions (optional filter by queue ID)",
)
async def get_audit_logs(
    queue_id: UUID = None,
    approval_service: ApprovalService = Depends(get_approval_service),
) -> AuditLogResponse:
    """
    Get audit logs for approval workflow actions.

    Returns a chronological list of all approval actions taken.
    Can optionally filter logs by specific queue entry ID.
    """
    try:
        audit_logs = approval_service.get_audit_logs(queue_id)

        # Convert to response schema
        log_items = []
        for log in audit_logs:
            item = ApprovalAuditLogItem(
                id=log.id,
                response_queue_id=log.response_queue_id,
                action=log.action,
                original_response=log.original_response,
                final_response=log.final_response,
                reason=log.reason,
                approved_by=log.approved_by,
                created_at=log.created_at,
            )
            log_items.append(item)

        logger.info(
            "Audit logs retrieved",
            total_count=len(log_items),
            queue_id_filter=str(queue_id) if queue_id else None,
        )

        return AuditLogResponse(audit_logs=log_items, total_count=len(log_items))

    except Exception as e:
        logger.error(
            "Error retrieving audit logs",
            queue_id_filter=str(queue_id) if queue_id else None,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to retrieve audit logs",
                "error_code": "RETRIEVAL_ERROR",
            },
        )


@router.post(
    "/check-timeouts",
    response_model=PendingApprovalsResponse,
    responses={
        200: {"description": "Timeout check completed successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Check for approval timeouts",
    description="Check for pending approvals that have timed out and auto-escalate them",
)
async def check_approval_timeouts(
    approval_service: ApprovalService = Depends(get_approval_service),
) -> PendingApprovalsResponse:
    """
    Check for pending approvals that have exceeded the timeout threshold.

    This endpoint automatically escalates pending approvals that have been
    waiting longer than the configured timeout period.
    """
    try:
        timed_out_entries = await approval_service.check_approval_timeouts()

        # Convert to response schema
        approval_items = []
        for entry in timed_out_entries:
            waiting_time_hours = (
                datetime.utcnow() - entry.created_at
            ).total_seconds() / 3600

            item = ApprovalQueueItem(
                id=entry.id,
                workflow_id=entry.workflow_id,
                tenant_id=entry.tenant_id,
                phone_number=entry.phone_number,
                tenant_message=entry.tenant_message,
                ai_response=entry.ai_response,
                confidence_score=entry.confidence_score,
                status=entry.status,
                created_at=entry.created_at,
                waiting_time_hours=round(waiting_time_hours, 2),
            )
            approval_items.append(item)

        logger.info(
            "Approval timeout check completed", timed_out_count=len(approval_items)
        )

        return PendingApprovalsResponse(
            pending_approvals=approval_items, total_count=len(approval_items)
        )

    except Exception as e:
        logger.error("Error checking approval timeouts", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to check approval timeouts",
                "error_code": "TIMEOUT_CHECK_ERROR",
            },
        )
