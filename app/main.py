"""Main FastAPI application for the System Orchestrator Service."""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List
from decimal import Decimal

from fastapi import FastAPI, HTTPException, status, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.core.middleware import (
    CorrelationIDMiddleware,
    PerformanceMonitoringMiddleware,
    MetricsCollectionMiddleware
)
from app.services.external import ServiceClients
from app.services.openai_service import OpenAIService
from app.services.database import db_service
from app.models.schemas import (
    IncomingSMS, ResponseApproval, EscalationRequest, RetryRequest,
    HealthResponse, DependencyHealthResponse, WorkflowStatusResponse, MetricsResponse,
    WorkflowStatus, ApprovalAction, AIResponse
)
from app.api.payment_plan import router as payment_plan_router
from app.api.escalation import router as escalation_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.core.dependencies import get_escalation_service

# Initialize logging
setup_logging()
logger = get_logger(__name__)

# Get settings
settings = get_settings()

# Initialize FastAPI app
app = FastAPI(
    title="System Orchestrator Service",
    description="Coordinates collections system components for AI-powered tenant communications",
    version=settings.service_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Initialize services
service_clients = ServiceClients()
openai_service = OpenAIService()

# Add metrics and tracing middleware
app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(PerformanceMonitoringMiddleware, slow_request_threshold_ms=1000.0)
app.add_middleware(MetricsCollectionMiddleware)

# CORS middleware
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API routers
app.include_router(payment_plan_router)
app.include_router(escalation_router)
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(metrics_router, tags=["metrics"])


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Starting System Orchestrator Service", version=settings.service_version)

    # Run database health check
    db_healthy = await db_service.health_check()
    if not db_healthy:
        logger.warning("Database health check failed on startup")

    # Start escalation monitoring services (Story 2.2)
    try:
        escalation_service = get_escalation_service()
        await escalation_service.start_services()
        logger.info("Escalation monitoring services started successfully")
    except Exception as e:
        logger.error("Failed to start escalation monitoring services", error=str(e))
        # Continue startup even if escalation services fail

    logger.info("Service startup complete", database_healthy=db_healthy)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down System Orchestrator Service")

    # Stop escalation monitoring services (Story 2.2)
    try:
        escalation_service = get_escalation_service()
        await escalation_service.stop_services()
        logger.info("Escalation monitoring services stopped successfully")
    except Exception as e:
        logger.error("Failed to stop escalation monitoring services", error=str(e))




# Main SMS Orchestration Endpoint
@app.post("/orchestrate/sms-received")
async def process_incoming_sms(sms_data: IncomingSMS):
    """Main orchestration endpoint for incoming SMS messages."""
    logger.info("Processing incoming SMS", phone_number=sms_data.phone_number, conversation_id=sms_data.conversation_id)

    try:
        # Create workflow record
        workflow_id = uuid.uuid4()
        workflow_data = {
            "id": workflow_id,
            "conversation_id": sms_data.conversation_id,
            "workflow_type": "sms_processing",
            "status": WorkflowStatus.RECEIVED,
            "metadata": {
                "tenant_id": sms_data.tenant_id,
                "phone_number": sms_data.phone_number,
                "message_content": sms_data.content
            }
        }

        await db_service.create_workflow(workflow_data)

        # Update workflow status to processing
        await db_service.update_workflow(workflow_id, {"status": WorkflowStatus.PROCESSING})

        # Get tenant context
        tenant_data = await service_clients.collections_monitor.get_tenant(sms_data.tenant_id)
        if not tenant_data.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )

        tenant_context = tenant_data.get("data", {}).get("tenant", {})

        # Get conversation history
        conversation_data = await service_clients.sms_agent.get_conversation(sms_data.phone_number)
        conversation_history = conversation_data.get("messages", [])

        # Get tenant language preference
        language = tenant_context.get("language_preference", "english")

        # Generate AI response
        ai_response = await openai_service.generate_response(
            tenant_context=tenant_context,
            conversation_history=conversation_history,
            current_message=sms_data.content,
            language=language
        )

        logger.info("AI response generated", confidence=ai_response.confidence)

        # Route based on confidence score
        if ai_response.confidence >= settings.auto_approval_confidence:
            # Auto-send response
            await _auto_send_response(sms_data, ai_response)
            await db_service.update_workflow(workflow_id, {
                "status": WorkflowStatus.COMPLETED,
                "completed_at": datetime.utcnow()
            })
        elif ai_response.confidence >= settings.manual_approval_min_confidence:
            # Queue for approval
            await _queue_for_approval(sms_data, ai_response, workflow_id)
            await db_service.update_workflow(workflow_id, {"status": WorkflowStatus.AWAITING_APPROVAL})
        else:
            # Escalate due to low confidence
            await _escalate_low_confidence(sms_data, ai_response, workflow_id)
            await db_service.update_workflow(workflow_id, {"status": WorkflowStatus.ESCALATED})

        # Process payment plan if detected
        if ai_response.payment_plan_detected:
            await _process_payment_plan(sms_data, ai_response, workflow_id)

        # Handle escalation triggers
        if ai_response.escalation_triggers:
            await _handle_escalation_triggers(sms_data, ai_response, workflow_id)

        return {
            "status": "processed",
            "workflow_id": str(workflow_id),
            "conversation_id": str(sms_data.conversation_id),
            "action_taken": _get_routing_action(ai_response.confidence)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process SMS", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


async def _auto_send_response(sms_data: IncomingSMS, ai_response: AIResponse):
    """Send response automatically."""
    await service_clients.sms_agent.send_sms(
        to=sms_data.phone_number,
        body=ai_response.content,
        conversation_id=str(sms_data.conversation_id)
    )
    logger.info("Response auto-sent", phone_number=sms_data.phone_number)


async def _queue_for_approval(sms_data: IncomingSMS, ai_response: AIResponse, workflow_id: uuid.UUID):
    """Queue response for manager approval."""
    queue_data = {
        "conversation_id": sms_data.conversation_id,
        "workflow_id": workflow_id,
        "tenant_message": sms_data.content,
        "ai_response": ai_response.content,
        "confidence_score": ai_response.confidence,
        "status": "pending"
    }

    await db_service.create_ai_response_queue(queue_data)

    # Notify manager
    await service_clients.notification_service.notify_manager(
        subject="Response Approval Required",
        body=f"AI response needs approval for conversation {sms_data.conversation_id}. "
             f"Confidence: {ai_response.confidence:.2f}\n\nAI Response: {ai_response.content}",
        priority="normal",
        metadata={"conversation_id": str(sms_data.conversation_id), "workflow_id": str(workflow_id)}
    )

    logger.info("Response queued for approval", conversation_id=sms_data.conversation_id)


async def _escalate_low_confidence(sms_data: IncomingSMS, ai_response: AIResponse, workflow_id: uuid.UUID):
    """Escalate due to low confidence."""
    escalation_data = {
        "conversation_id": sms_data.conversation_id,
        "escalation_type": "low_confidence",
        "reason": f"AI confidence too low: {ai_response.confidence:.2f}",
        "severity": "medium",
        "auto_detected": True
    }

    # Note: This would create escalation in database if escalation table exists

    # Notify manager
    await service_clients.notification_service.notify_manager(
        subject="Low Confidence Response - Manual Intervention Required",
        body=f"AI confidence too low ({ai_response.confidence:.2f}) for conversation {sms_data.conversation_id}. "
             f"Manual response required.\n\nTenant Message: {sms_data.content}",
        priority="high",
        metadata={"conversation_id": str(sms_data.conversation_id), "workflow_id": str(workflow_id)}
    )

    logger.info("Low confidence escalation", conversation_id=sms_data.conversation_id)


async def _process_payment_plan(sms_data: IncomingSMS, ai_response: AIResponse, workflow_id: uuid.UUID):
    """Process detected payment plan by calling payment plan detection API."""
    try:
        # Import the payment plan request schema
        from app.schemas.payment_plan import PaymentPlanDetectedRequest
        from app.api.payment_plan import payment_extractor, payment_validator

        # Create payment plan detection request
        payment_plan_request = PaymentPlanDetectedRequest(
            conversation_id=sms_data.conversation_id,
            tenant_id=sms_data.tenant_id,
            message_content=sms_data.content,
            ai_response=ai_response.response_text,
            tenant_context=await _get_tenant_context(sms_data.tenant_id)
        )

        # Extract payment plan using the utility
        payment_plan = payment_extractor.extract_payment_plan(
            sms_data.content,
            payment_extractor.ExtractionSource.TENANT_MESSAGE
        )

        # If not found in tenant message, try AI response
        if not payment_plan and ai_response.payment_plan_data:
            # Recreate payment plan object from stored data
            from app.utils.payment_plan_extraction import ExtractedPaymentPlan, ExtractionSource
            from datetime import datetime

            payment_plan = ExtractedPaymentPlan(
                weekly_amount=Decimal(str(ai_response.payment_plan_data.get("weekly_amount"))) if ai_response.payment_plan_data.get("weekly_amount") else None,
                duration_weeks=ai_response.payment_plan_data.get("duration_weeks"),
                start_date=datetime.fromisoformat(ai_response.payment_plan_data["start_date"]) if ai_response.payment_plan_data.get("start_date") else None,
                confidence_score=ai_response.payment_plan_data.get("confidence_score", 0.0),
                extracted_from=ExtractionSource.AI_RESPONSE,
                original_text=ai_response.response_text,
                extraction_patterns=ai_response.payment_plan_data.get("extraction_patterns", [])
            )

        if payment_plan:
            # Validate payment plan
            validation_result = payment_validator.validate_payment_plan(
                payment_plan,
                payment_plan_request.tenant_context
            )

            # Store payment plan in database
            from app.models.payment_plan import PaymentPlanAttempt
            from app.database import get_supabase_client

            supabase = get_supabase_client()
            payment_plan_id = await PaymentPlanAttempt.create(
                supabase,
                {
                    "workflow_id": str(workflow_id),
                    "extracted_from": payment_plan.extracted_from.value,
                    "weekly_amount": float(payment_plan.weekly_amount) if payment_plan.weekly_amount else None,
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
                                "rule_code": error.rule_code
                            } for error in validation_result.errors
                        ],
                        "warnings": [
                            {
                                "field": warning.field,
                                "message": warning.message,
                                "severity": warning.severity,
                                "rule_code": warning.rule_code
                            } for warning in validation_result.warnings
                        ],
                        "validation_summary": validation_result.validation_summary
                    },
                    "status": validation_result.status.value,
                    "extraction_patterns": payment_plan.extraction_patterns
                }
            )

            logger.info(
                "Payment plan processed successfully",
                conversation_id=sms_data.conversation_id,
                payment_plan_id=str(payment_plan_id),
                validation_status=validation_result.status.value,
                is_auto_approvable=validation_result.is_auto_approvable
            )

            # Update workflow status based on validation results
            if validation_result.is_auto_approvable:
                await db_service.update_workflow(workflow_id, {
                    "status": "payment_plan_approved",
                    "payment_plan_id": str(payment_plan_id)
                })
            else:
                await db_service.update_workflow(workflow_id, {
                    "status": "payment_plan_needs_review",
                    "payment_plan_id": str(payment_plan_id)
                })
        else:
            logger.warning(
                "Payment plan flag set but no plan extracted",
                conversation_id=sms_data.conversation_id
            )

    except Exception as e:
        logger.error(
            "Failed to process payment plan",
            conversation_id=sms_data.conversation_id,
            error=str(e)
        )
        # Don't fail the entire SMS processing due to payment plan processing error


async def _get_tenant_context(tenant_id: str) -> Dict[str, Any]:
    """Get tenant context for payment plan validation."""
    try:
        tenant_data = await service_clients.collections_monitor.get_tenant(tenant_id)
        if tenant_data.get("success"):
            return tenant_data.get("data", {}).get("tenant", {})
        return {}
    except Exception as e:
        logger.error(f"Failed to get tenant context for {tenant_id}: {str(e)}")
        return {}


async def _handle_escalation_triggers(sms_data: IncomingSMS, ai_response: AIResponse, workflow_id: uuid.UUID):
    """Handle detected escalation triggers."""
    for trigger in ai_response.escalation_triggers:
        escalation_type = trigger.split(":")[0] if ":" in trigger else trigger

        # Notify manager
        await service_clients.notification_service.notify_manager(
            subject=f"Escalation Triggered: {escalation_type}",
            body=f"Escalation trigger detected in conversation {sms_data.conversation_id}.\n"
                 f"Trigger: {trigger}\n\nMessage: {sms_data.content}",
            priority="high",
            metadata={"conversation_id": str(sms_data.conversation_id), "workflow_id": str(workflow_id)}
        )

        logger.warning("Escalation trigger detected", trigger=trigger, conversation_id=sms_data.conversation_id)


def _get_routing_action(confidence: float) -> str:
    """Get routing action based on confidence score."""
    if confidence >= settings.auto_approval_confidence:
        return "auto_sent"
    elif confidence >= settings.manual_approval_min_confidence:
        return "queued_for_approval"
    else:
        return "escalated"


# Approval Workflow Endpoints
@app.post("/orchestrate/approve-response")
async def approve_response(approval: ResponseApproval):
    """Handle manager approval of AI responses."""
    logger.info("Processing approval request", action=approval.action, queue_id=approval.response_queue_id)

    try:
        # Get response queue entry
        queue_entry = await db_service.get_response_queue(approval.response_queue_id)
        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Response queue entry not found"
            )

        # Get conversation ID for sending response
        conversation_id = queue_entry["conversation_id"]

        if approval.action == ApprovalAction.APPROVE:
            # Send approved response
            response = await service_clients.sms_agent.send_sms(
                to=queue_entry.get("metadata", {}).get("phone_number", ""),
                body=approval.approved_text,
                conversation_id=str(conversation_id)
            )

        elif approval.action == ApprovalAction.MODIFY:
            # Send modified response
            response = await service_clients.sms_agent.send_sms(
                to=queue_entry.get("metadata", {}).get("phone_number", ""),
                body=approval.modified_text,
                conversation_id=str(conversation_id)
            )

        elif approval.action == ApprovalAction.ESCALATE:
            # Create escalation
            escalation_data = {
                "conversation_id": conversation_id,
                "escalation_type": "manual",
                "reason": approval.escalation_reason,
                "severity": "high",
                "auto_detected": False
            }
            # Store escalation (simplified)

        # Update queue entry
        update_data = {
            "status": "completed",
            "manager_action": approval.action,
            "modified_response": approval.modified_text or approval.approved_text,
            "actioned_by": approval.manager_id
        }

        await db_service.update_response_queue(approval.response_queue_id, update_data)

        # Create audit log
        audit_data = {
            "response_queue_id": approval.response_queue_id,
            "action": approval.action,
            "original_response": queue_entry["ai_response"],
            "final_response": approval.modified_text or approval.approved_text,
            "reason": approval.escalation_reason or approval.notes,
            "approved_by": approval.manager_id
        }

        await db_service.create_approval_audit_log(audit_data)

        return {"status": "processed", "action": approval.action}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process approval", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# Workflow Status Tracking
@app.get("/orchestrate/workflow/{conversation_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(conversation_id: uuid.UUID):
    """Get workflow status for a conversation."""
    try:
        workflow = await db_service.get_workflow_by_conversation(conversation_id)
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )

        return WorkflowStatusResponse(
            conversation_id=conversation_id,
            workflow_id=workflow["id"],
            status=workflow["status"],
            created_at=workflow["started_at"],
            updated_at=workflow["updated_at"],
            current_step=workflow.get("metadata", {}).get("current_step", "unknown"),
            steps_completed=workflow.get("metadata", {}).get("steps_completed", []),
            error_message=workflow.get("error_message"),
            metadata=workflow.get("metadata")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get workflow status", conversation_id=str(conversation_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# Retry Mechanism
@app.post("/orchestrate/retry/{workflow_id}")
async def retry_workflow(workflow_id: uuid.UUID, retry_data: RetryRequest):
    """Retry a failed workflow."""
    logger.info("Retrying workflow", workflow_id=str(workflow_id), reason=retry_data.reason)

    try:
        # Get workflow
        workflow = await db_service.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )

        # Check if workflow can be retried
        if workflow["status"] not in ["failed", "escalated"]:
            if not retry_data.force_retry:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Workflow cannot be retried"
                )

        # Create retry attempt record
        await db_service.create_retry_attempt(workflow_id, retry_data.reason)

        # Reset workflow status for retry
        await db_service.update_workflow(workflow_id, {
            "status": WorkflowStatus.PROCESSING,
            "error_message": None,
            "metadata": {
                **workflow.get("metadata", {}),
                "retry_reason": retry_data.reason,
                "retry_attempted_at": datetime.utcnow().isoformat()
            }
        })

        # Note: In a real implementation, you would restart the workflow process here
        # For now, we just mark it as ready for retry

        return {"status": "retry_initiated", "workflow_id": str(workflow_id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retry workflow", workflow_id=str(workflow_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )






@app.post("/orchestrate/escalate")
async def escalate_conversation(escalation_data: EscalationRequest):
    """Handle conversation escalation."""
    logger.info("Processing escalation", conversation_id=escalation_data.conversation_id, type=escalation_data.escalation_type)

    # Store escalation and notify appropriate parties
    # This would be fully implemented in Epic 2

    return {"status": "escalation_processed"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )