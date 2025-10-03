"""
Orchestration endpoints for SMS processing and workflow management.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, status, Depends
from pydantic import ValidationError

from app.schemas.incoming_sms import IncomingSMS, SMSResponse
from app.schemas.workflow import CreateWorkflowRequest, CreateWorkflowStepRequest
from app.services.workflow_service import WorkflowService
from app.models.workflow import StepType
from app.core.exceptions import ValidationError as CustomValidationError, WorkflowError, ExternalServiceError, ServiceUnavailableError
from app.core.logging import get_logger
from app.services.escalation_service import EscalationService
from app.core.dependencies import get_escalation_service
from app.core.degradation import degradation_manager

router = APIRouter()
logger = get_logger(__name__)
workflow_service = WorkflowService()


@router.post(
    "/orchestrate/sms-received",
    response_model=SMSResponse,
    status_code=status.HTTP_201_CREATED,
)
async def receive_sms(
    request: Request,
    sms_data: IncomingSMS,
    escalation_service: EscalationService = Depends(get_escalation_service)
):
    """
    Process incoming SMS data from the SMS Agent.

    This endpoint receives SMS data, validates it, and initiates the workflow
    for processing the message and generating AI responses.

    Args:
        request: FastAPI request object
        sms_data: Validated SMS data from the SMS Agent

    Returns:
        SMSResponse: Processing status with workflow ID for tracking

    Raises:
        ValidationError: If SMS data is malformed or missing required fields
        HTTPException: For other processing errors
    """
    correlation_id = request.headers.get("X-Correlation-ID", "unknown")

    logger.info(
        "Received SMS data",
        tenant_id=sms_data.tenant_id,
        phone_number=sms_data.phone_number,
        conversation_id=sms_data.conversation_id,
        content_length=len(sms_data.content),
        correlation_id=correlation_id,
    )

    try:
        # Create workflow instance for tracking SMS processing
        workflow_request = CreateWorkflowRequest(
            conversation_id=sms_data.conversation_id,
            tenant_id=sms_data.tenant_id,
            phone_number=sms_data.phone_number,
            metadata={
                "content_length": len(sms_data.content),
                "message_type": "incoming_sms",
                "correlation_id": correlation_id
            }
        )

        workflow_instance = await workflow_service.create_workflow_instance(workflow_request)
        workflow_id = str(workflow_instance.id)

        logger.info(
            "Created workflow instance for SMS processing",
            workflow_id=workflow_id,
            conversation_id=sms_data.conversation_id,
            correlation_id=correlation_id,
        )

        # Create workflow step for SMS receipt
        sms_step_id = await workflow_service.create_workflow_step(
            workflow_instance.id,
            CreateWorkflowStepRequest(
                step_name="sms_received",
                step_type=StepType.API_CALL,
                input_data={
                    "sms_content": sms_data.content,
                    "content_length": len(sms_data.content),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        )

        # Update workflow status to processing
        from app.schemas.workflow import UpdateWorkflowStatusRequest
        from app.models.workflow import WorkflowStatus

        await workflow_service.update_workflow_status(
            workflow_instance.id,
            UpdateWorkflowStatusRequest(status=WorkflowStatus.PROCESSING)
        )

        # Check for payment plan in SMS content
        payment_plan_detected = _check_for_payment_plan(
            sms_data.content, workflow_instance.id, correlation_id
        )

        if payment_plan_detected:
            logger.info(
                "Payment plan detected in SMS",
                workflow_id=workflow_id,
                conversation_id=sms_data.conversation_id,
                correlation_id=correlation_id
            )

        # Check for escalation triggers in SMS content (Story 2.2)
        try:
            should_escalate, escalation_trigger = await escalation_service.analyze_message_for_escalation(
                message_text=sms_data.content,
                workflow_id=workflow_id,
                customer_phone=sms_data.phone_number
            )
        except ExternalServiceError as e:
            logger.warning(
                "Escalation service unavailable, using degraded fallback",
                service_name=e.service_name,
                error=str(e),
                workflow_id=workflow_id,
                correlation_id=correlation_id
            )
            # Fallback: don't escalate if service is unavailable
            should_escalate = False
            escalation_trigger = None

            # Update degradation manager
            degradation_manager.update_service_status(
                "escalation_service",
                available=False,
                circuit_breaker_open=True
            )

        if should_escalate:
            logger.info(
                "Escalation triggered by SMS content",
                workflow_id=workflow_id,
                conversation_id=sms_data.conversation_id,
                escalation_reason=escalation_trigger.reason.value if escalation_trigger else "unknown",
                escalation_confidence=escalation_trigger.confidence if escalation_trigger else 0.0,
                correlation_id=correlation_id
            )

        # Register workflow for timeout monitoring (Story 2.2 - AC3)
        try:
            await escalation_service.register_workflow_timeout(
                workflow_id=workflow_id,
                customer_phone=sms_data.phone_number,
                last_ai_response=datetime.utcnow()
            )
        except ExternalServiceError as e:
            logger.warning(
                "Failed to register workflow timeout, continuing with processing",
                service_name=e.service_name,
                error=str(e),
                workflow_id=workflow_id,
                correlation_id=correlation_id
            )

        # TODO: In future stories, this will trigger:
        # 1. AI service integration for response generation
        # For now, we just acknowledge receipt and mark as sent

        # Simulate AI response generation (will be implemented in future stories)
        ai_response_time = datetime.utcnow()

        # Update workflow timeout with new response time (Story 2.2 - AC3)
        try:
            await escalation_service.update_workflow_response(
                workflow_id=workflow_id,
                response_time=ai_response_time
            )
        except ExternalServiceError as e:
            logger.warning(
                "Failed to update workflow response time, continuing with processing",
                service_name=e.service_name,
                error=str(e),
                workflow_id=workflow_id,
                correlation_id=correlation_id
            )

        # Complete the SMS processing step
        from app.schemas.workflow import UpdateWorkflowStepRequest
        from app.models.workflow import StepStatus

        await workflow_service.update_workflow_step(
            sms_step_id,
            UpdateWorkflowStepRequest(
                status=StepStatus.COMPLETED,
                output_data={
                    "sms_processed": True,
                    "workflow_id": workflow_id,
                    "ai_response_generated": True,
                    "ai_response_time": ai_response_time.isoformat(),
                    "escalation_triggered": should_escalate,
                    "escalation_reason": escalation_trigger.reason.value if escalation_trigger else None,
                    "processing_timestamp": datetime.utcnow().isoformat()
                }
            )
        )

        # Mark workflow as completed for basic SMS processing
        await workflow_service.update_workflow_status(
            workflow_instance.id,
            UpdateWorkflowStatusRequest(status=WorkflowStatus.COMPLETED)
        )

        response = SMSResponse(
            status="processed",
            conversation_id=sms_data.conversation_id,
            workflow_id=workflow_id,
            timestamp=datetime.utcnow(),
        )

        logger.info(
            "SMS processing completed successfully",
            workflow_id=workflow_id,
            conversation_id=sms_data.conversation_id,
            status=response.status,
            correlation_id=correlation_id,
        )

        return response

    except ValidationError as e:
        logger.error(
            "SMS validation failed",
            tenant_id=sms_data.tenant_id,
            conversation_id=sms_data.conversation_id,
            validation_errors=str(e),
            correlation_id=correlation_id,
        )
        raise CustomValidationError(str(e), "SMS_DATA", correlation_id=correlation_id)

    except WorkflowError as e:
        logger.error(
            "Workflow error during SMS processing",
            tenant_id=sms_data.tenant_id,
            conversation_id=sms_data.conversation_id,
            workflow_id=getattr(e, 'workflow_id', 'unknown'),
            error=str(e),
            correlation_id=correlation_id,
        )
        raise WorkflowError(
            detail=str(e),
            workflow_id=getattr(e, 'workflow_id', None),
            tenant_id=sms_data.tenant_id,
            correlation_id=correlation_id
        )

    except ExternalServiceError as e:
        logger.error(
            "External service error during SMS processing",
            tenant_id=sms_data.tenant_id,
            conversation_id=sms_data.conversation_id,
            service_name=e.service_name,
            error=str(e),
            correlation_id=correlation_id,
        )

        # Update degradation manager
        degradation_manager.update_service_status(
            e.service_name,
            available=False,
            circuit_breaker_open=True
        )

        # Check if we can continue with degraded functionality
        can_execute, fallback = degradation_manager.can_execute_operation(
            e.service_name, "write"
        )

        if can_execute:
            logger.info(
                "Continuing with degraded functionality",
                service_name=e.service_name,
                fallback_used=fallback.fallback_used if fallback else None,
                correlation_id=correlation_id
            )
            # Continue processing with fallback logic would go here
            # For now, we'll acknowledge and create a simple response
            response = SMSResponse(
                status="processed_degraded",
                conversation_id=sms_data.conversation_id,
                workflow_id=f"degraded_{uuid.uuid4().hex[:8]}",
                timestamp=datetime.utcnow(),
            )
            return response
        else:
            raise ServiceUnavailableError(
                service_name=e.service_name,
                detail=f"Service unavailable: {str(e)}",
                correlation_id=correlation_id,
                **e.context
            )

    except Exception as e:
        logger.error(
            "Unexpected error processing SMS",
            tenant_id=sms_data.tenant_id,
            conversation_id=sms_data.conversation_id,
            error=str(e),
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the SMS",
            headers={"X-Correlation-ID": correlation_id}
        )


def _check_for_payment_plan(
    content: str,
    workflow_id: str,
    correlation_id: str
) -> bool:
    """
    Check if SMS content contains a payment plan.

    Args:
        content: SMS content to analyze
        workflow_id: Associated workflow ID
        correlation_id: Request correlation ID

    Returns:
        True if payment plan detected, False otherwise
    """
    try:
        from app.utils.payment_plan_extraction import PaymentPlanExtractor

        extractor = PaymentPlanExtractor()
        extracted_plan = extractor.extract_payment_plan(content)

        if extracted_plan.is_complete():
            logger.info(
                "Complete payment plan extracted from SMS",
                workflow_id=workflow_id,
                confidence=extracted_plan.confidence.value,
                weekly_amount=extracted_plan.weekly_amount,
                duration_weeks=extracted_plan.duration_weeks,
                correlation_id=correlation_id
            )
            return True

        # Check for keywords that suggest payment plan intent
        payment_keywords = [
            "payment plan", "pay weekly", "weekly payment",
            "installment", "pay over time", "payment arrangement"
        ]

        has_keywords = any(keyword.lower() in content.lower() for keyword in payment_keywords)

        if has_keywords:
            logger.info(
                "Payment plan keywords detected in SMS",
                workflow_id=workflow_id,
                keywords_found=[kw for kw in payment_keywords if kw.lower() in content.lower()],
                correlation_id=correlation_id
            )
            return True

        return False

    except Exception as e:
        logger.error(
            "Error checking for payment plan in SMS",
            workflow_id=workflow_id,
            error=str(e),
            correlation_id=correlation_id
        )
        return False
