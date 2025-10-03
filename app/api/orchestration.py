"""
Orchestration endpoints for SMS processing and workflow management.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, status
from pydantic import ValidationError

from app.schemas.incoming_sms import IncomingSMS, SMSResponse
from app.schemas.workflow import CreateWorkflowRequest, CreateWorkflowStepRequest
from app.services.workflow_service import WorkflowService
from app.models.workflow import StepType
from app.core.exceptions import ValidationError as CustomValidationError
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)
workflow_service = WorkflowService()


@router.post(
    "/orchestrate/sms-received",
    response_model=SMSResponse,
    status_code=status.HTTP_201_CREATED,
)
async def receive_sms(request: Request, sms_data: IncomingSMS):
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

        # TODO: In future stories, this will trigger:
        # 1. AI service integration for response generation
        # 2. Payment plan detection
        # 3. Escalation logic
        # For now, we just acknowledge receipt and mark as sent

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
        raise CustomValidationError(str(e), "SMS_DATA")

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
        )
