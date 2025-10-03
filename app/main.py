"""Main FastAPI application for the System Orchestrator Service."""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, status, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.services.external import ServiceClients
from app.services.openai_service import OpenAIService
from app.services.database import db_service
from app.models.schemas import (
    IncomingSMS, ResponseApproval, PaymentPlanDetection, EscalationRequest, RetryRequest,
    HealthResponse, DependencyHealthResponse, WorkflowStatusResponse, MetricsResponse,
    WorkflowStatus, ApprovalAction, AIResponse
)

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
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Initialize services
service_clients = ServiceClients()
openai_service = OpenAIService()

# CORS middleware
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Starting System Orchestrator Service", version=settings.service_version)

    # Run database health check
    db_healthy = await db_service.health_check()
    if not db_healthy:
        logger.warning("Database health check failed on startup")

    logger.info("Service startup complete", database_healthy=db_healthy)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down System Orchestrator Service")


# Health Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint."""
    try:
        return HealthResponse(
            status="healthy",
            version=settings.service_version,
            checks={
                "database": await db_service.health_check(),
                "external_services": await service_clients.health_check()
            }
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return HealthResponse(
            status="unhealthy",
            version=settings.service_version,
            checks={"error": str(e)}
        )


@app.get("/health/dependencies", response_model=DependencyHealthResponse)
async def dependency_health_check():
    """Check health of all external service dependencies."""
    try:
        service_health = await service_clients.health_check()

        overall_status = "healthy" if all(service_health.values()) else "unhealthy"

        return DependencyHealthResponse(
            status=overall_status,
            services=service_health
        )
    except Exception as e:
        logger.error("Dependency health check failed", error=str(e))
        return DependencyHealthResponse(
            status="unhealthy",
            services={"error": str(e)}
        )


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
            await _process_payment_plan(sms_data, ai_response)

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


async def _process_payment_plan(sms_data: IncomingSMS, ai_response: AIResponse):
    """Process detected payment plan."""
    plan_data = {
        "conversation_id": sms_data.conversation_id,
        "tenant_id": sms_data.tenant_id,
        "message_content": sms_data.content,
        "ai_response": ai_response.content,
        **ai_response.payment_plan_detected
    }

    # This would store payment plan in database if needed
    logger.info("Payment plan detected", conversation_id=sms_data.conversation_id)


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


# Metrics Endpoint
@app.get("/orchestrate/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get service metrics."""
    try:
        # Get database metrics
        db_metrics = await db_service.get_workflow_metrics()

        # Get today's metrics
        metrics = {
            "last_hour": {
                "sms_processed": 0,  # Would be calculated from recent workflows
                "ai_responses": 0,
                "auto_approval_rate": 0.0,
                "avg_response_time_ms": 0
            },
            "today": db_metrics
        }

        return MetricsResponse(**metrics)

    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# Additional endpoints for Epic 2 functionality (placeholder implementations)
@app.post("/orchestrate/payment-plan-detected")
async def payment_plan_detected(payment_data: PaymentPlanDetection):
    """Process detected payment plan."""
    logger.info("Processing payment plan detection", conversation_id=payment_data.conversation_id)

    # Store payment plan and validate against business rules
    # This would be fully implemented in Epic 2

    return {"status": "payment_plan_processed"}


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