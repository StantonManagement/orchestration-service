"""
Payment Plan API Endpoints

REST API endpoints for payment plan detection and validation.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from app.schemas.payment_plan import (
    PaymentPlanDetectedRequest,
    PaymentPlanDetectedResponse,
    PaymentPlanResponse,
    ValidationResultResponse,
    ValidationErrorResponse,
    PaymentPlanListResponse,
    PaymentPlanListItem,
)
from app.utils.payment_plan_extraction import PaymentPlanExtractor
from app.services.payment_plan_service import PaymentPlanValidator
from app.models.payment_plan import PaymentPlanAttempt
from app.models.workflow import WorkflowInstance
from app.core.exceptions import ValidationError as AppValidationError, DatabaseError
from app.database import get_supabase_client
from app.core.logging import get_request_logger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orchestrate", tags=["payment-plans"])

# Initialize services
payment_extractor = PaymentPlanExtractor()
payment_validator = PaymentPlanValidator()


def get_request_logger():
    """Get request-specific logger with correlation ID"""
    return get_request_logger()


@router.post(
    "/payment-plan-detected",
    response_model=PaymentPlanDetectedResponse,
    status_code=status.HTTP_200_OK,
)
async def payment_plan_detected(
    request: PaymentPlanDetectedRequest,
    supabase=Depends(get_supabase_client),
    request_logger=Depends(get_request_logger),
):
    """
    Process detected payment plan from tenant or AI response

    This endpoint extracts payment plan information from the provided text,
    validates it against business rules, and stores it in the database.
    """
    request_logger.info(
        f"Payment plan detection request: conversation_id={request.conversation_id}, "
        f"tenant_id={request.tenant_id}"
    )

    try:
        # Step 1: Extract payment plan from message content
        payment_plan = None
        extracted_from = None

        # Try to extract from tenant message first
        payment_plan = payment_extractor.extract_payment_plan(request.message_content)
        if payment_plan:
            extracted_from = "tenant_message"

        # If not found in tenant message, try AI response
        if not payment_plan and request.ai_response:
            payment_plan = payment_extractor.extract_from_ai_response(request.ai_response)
            if payment_plan:
                extracted_from = "ai_response"

        if not payment_plan:
            request_logger.info("No payment plan detected in provided text")
            return PaymentPlanDetectedResponse(
                success=False,
                payment_plan=None,
                validation=None,
                payment_plan_id=None,
                workflow_id=None,
                message="No payment plan detected in the provided message content",
            )

        request_logger.info(
            f"Payment plan extracted: ${payment_plan.weekly_amount}/week for "
            f"{payment_plan.duration_weeks} weeks (confidence: {payment_plan.confidence_score})"
        )

        # Step 2: Validate the extracted payment plan
        validation_result = payment_validator.validate_payment_plan(
            payment_plan, request.tenant_context
        )

        request_logger.info(
            f"Validation result: status={validation_result.status.value}, "
            f"valid={validation_result.is_valid}, auto_approvable={validation_result.is_auto_approvable}"
        )

        # Step 3: Get or create workflow
        workflow_id = await _get_or_create_workflow(
            supabase, request.conversation_id, request.tenant_id, request_logger
        )

        # Step 4: Store payment plan attempt in database
        payment_plan_id = await _store_payment_plan_attempt(
            supabase, workflow_id, payment_plan, validation_result, extracted_from, request_logger
        )

        # Step 5: Create response
        response = PaymentPlanDetectedResponse(
            success=True,
            payment_plan=PaymentPlanResponse(
                weekly_amount=payment_plan.weekly_amount,
                duration_weeks=payment_plan.duration_weeks,
                start_date=payment_plan.start_date,
                confidence_score=payment_plan.confidence_score,
                extracted_from=extracted_from,
                extraction_patterns=payment_plan.extraction_patterns,
            ),
            validation=ValidationResultResponse(
                status=validation_result.status.value,
                is_valid=validation_result.is_valid,
                is_auto_approvable=validation_result.is_auto_approvable,
                errors=[
                    ValidationErrorResponse(
                        field=error.field,
                        message=error.message,
                        severity=error.severity,
                        rule_code=error.rule_code,
                    )
                    for error in validation_result.errors
                ],
                warnings=[
                    ValidationErrorResponse(
                        field=warning.field,
                        message=warning.message,
                        severity=warning.severity,
                        rule_code=warning.rule_code,
                    )
                    for warning in validation_result.warnings
                ],
                validation_summary=validation_result.validation_summary,
            ),
            payment_plan_id=payment_plan_id,
            workflow_id=workflow_id,
            message=f"Payment plan detected and validated: {validation_result.validation_summary}",
        )

        request_logger.info(
            f"Payment plan processed successfully: payment_plan_id={payment_plan_id}"
        )
        return response

    except AppValidationError as e:
        request_logger.error(f"Validation error in payment plan detection: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseError as e:
        request_logger.error(f"Database error in payment plan detection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while processing payment plan",
        )
    except Exception as e:
        request_logger.error(f"Unexpected error in payment plan detection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the payment plan",
        )


@router.get("/payment-plans/{conversation_id}", response_model=PaymentPlanListResponse)
async def get_payment_plans_by_conversation(
    conversation_id: UUID,
    limit: int = 10,
    offset: int = 0,
    supabase=Depends(get_supabase_client),
    request_logger=Depends(get_request_logger),
):
    """
    Retrieve payment plans for a specific conversation
    """
    request_logger.info(f"Retrieving payment plans for conversation: {conversation_id}")

    try:
        payment_plans = await PaymentPlanAttempt.get_by_conversation_id(
            supabase, conversation_id, limit=limit, offset=offset
        )

        total_count = await PaymentPlanAttempt.count_by_conversation_id(supabase, conversation_id)

        plan_items = [
            PaymentPlanListItem(
                id=plan["id"],
                workflow_id=plan["workflow_id"],
                weekly_amount=plan.get("weekly_amount"),
                duration_weeks=plan.get("duration_weeks"),
                start_date=plan.get("start_date"),
                status=plan["status"],
                extracted_from=plan["extracted_from"],
                confidence_score=plan["confidence_score"],
                created_at=plan["created_at"],
                validation_status=plan.get("validation_status"),
                is_auto_approvable=plan.get("validation_result", {}).get(
                    "is_auto_approvable", False
                ),
            )
            for plan in payment_plans
        ]

        return PaymentPlanListResponse(
            payment_plans=plan_items, total_count=total_count, limit=limit, offset=offset
        )

    except DatabaseError as e:
        request_logger.error(f"Database error retrieving payment plans: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve payment plans",
        )


@router.get("/payment-plans/{payment_plan_id}", response_model=PaymentPlanDetectedResponse)
async def get_payment_plan_details(
    payment_plan_id: UUID,
    supabase=Depends(get_supabase_client),
    request_logger=Depends(get_request_logger),
):
    """
    Retrieve detailed information about a specific payment plan
    """
    request_logger.info(f"Retrieving payment plan details: {payment_plan_id}")

    try:
        payment_plan = await PaymentPlanAttempt.get_by_id(supabase, payment_plan_id)

        if not payment_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Payment plan not found"
            )

        # Convert database record to response format
        validation_result = payment_plan.get("validation_result", {})

        return PaymentPlanDetectedResponse(
            success=True,
            payment_plan=PaymentPlanResponse(
                weekly_amount=payment_plan.get("weekly_amount"),
                duration_weeks=payment_plan.get("duration_weeks"),
                start_date=payment_plan.get("start_date"),
                confidence_score=payment_plan["confidence_score"],
                extracted_from=payment_plan["extracted_from"],
                extraction_patterns=payment_plan.get("extraction_patterns", []),
            ),
            validation=ValidationResultResponse(
                status=validation_result.get("status", "unknown"),
                is_valid=validation_result.get("is_valid", False),
                is_auto_approvable=validation_result.get("is_auto_approvable", False),
                errors=[
                    ValidationErrorResponse(**error)
                    for error in validation_result.get("errors", [])
                ],
                warnings=[
                    ValidationErrorResponse(**warning)
                    for warning in validation_result.get("warnings", [])
                ],
                validation_summary=validation_result.get("validation_summary", ""),
            )
            if validation_result
            else None,
            payment_plan_id=payment_plan["id"],
            workflow_id=payment_plan["workflow_id"],
            message="Payment plan details retrieved successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        request_logger.error(f"Error retrieving payment plan details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve payment plan details",
        )


async def _get_or_create_workflow(
    supabase, conversation_id: UUID, tenant_id: str, request_logger
) -> UUID:
    """Get existing workflow or create new one"""
    try:
        # Try to find existing workflow for this conversation
        existing_workflow = await WorkflowInstance.get_by_conversation_id(supabase, conversation_id)

        if existing_workflow:
            request_logger.info(f"Using existing workflow: {existing_workflow['id']}")
            return existing_workflow["id"]

        # Create new workflow
        workflow_id = await WorkflowInstance.create(
            supabase,
            {
                "conversation_id": str(conversation_id),
                "tenant_id": tenant_id,
                "status": "payment_plan_detected",
                "current_step": "payment_plan_validation",
            },
        )

        request_logger.info(f"Created new workflow: {workflow_id}")
        return workflow_id

    except Exception as e:
        request_logger.error(f"Error getting/creating workflow: {str(e)}")
        raise DatabaseError(f"Failed to get or create workflow: {str(e)}")


async def _store_payment_plan_attempt(
    supabase, workflow_id: UUID, payment_plan, validation_result, extracted_from: str, request_logger
) -> UUID:
    """Store payment plan attempt in database"""
    try:
        payment_plan_data = {
            "workflow_id": str(workflow_id),
            "extracted_from": extracted_from,
            "weekly_amount": float(payment_plan.weekly_amount)
            if payment_plan.weekly_amount
            else None,
            "duration_weeks": payment_plan.duration_weeks,
            "start_date": payment_plan.start_date.isoformat() if payment_plan.start_date else None,
            "confidence_score": payment_plan.confidence_score,
            "validation_result": {
                "status": validation_result.status.value,
                "is_valid": validation_result.is_valid,
                "is_auto_approvable": validation_result.is_auto_approvable,
                "errors": [
                    {
                        "field": error.field,
                        "message": error.message,
                        "severity": error.severity,
                        "rule_code": error.rule_code,
                    }
                    for error in validation_result.errors
                ],
                "warnings": [
                    {
                        "field": warning.field,
                        "message": warning.message,
                        "severity": warning.severity,
                        "rule_code": warning.rule_code,
                    }
                    for warning in validation_result.warnings
                ],
                "validation_summary": validation_result.validation_summary,
            },
            "status": validation_result.status.value,
            "extraction_patterns": payment_plan.extraction_patterns,
        }

        payment_plan_id = await PaymentPlanAttempt.create(supabase, payment_plan_data)
        request_logger.info(f"Stored payment plan attempt: {payment_plan_id}")
        return payment_plan_id

    except Exception as e:
        request_logger.error(f"Error storing payment plan attempt: {str(e)}")
        raise DatabaseError(f"Failed to store payment plan attempt: {str(e)}")
