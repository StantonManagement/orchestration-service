"""SQLAlchemy database models for orchestrator service."""

from datetime import datetime
from typing import Dict, Any

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer,
    String, Text, JSON, UUID
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class OrchestrationWorkflow(Base):
    """Orchestration workflow tracking table."""
    __tablename__ = "orchestration_workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    conversation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workflow_type = Column(String(50), nullable=False, default="sms_processing")
    status = Column(String(50), nullable=False, default="received")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    error_message = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)

    # Relationships
    ai_responses = relationship("AIResponseQueue", back_populates="workflow")
    retry_attempts = relationship("WorkflowRetryAttempt", back_populates="workflow")


class AIResponseQueue(Base):
    """AI response queue for approval workflow."""
    __tablename__ = "ai_response_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    conversation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("orchestration_workflows.id"), nullable=True)
    tenant_message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    manager_action = Column(String(50), nullable=True)
    modified_response = Column(Text, nullable=True)
    actioned_by = Column(String(100), nullable=True)
    actioned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    workflow = relationship("OrchestrationWorkflow", back_populates="ai_responses")
    audit_logs = relationship("ApprovalAuditLog", back_populates="response_queue")


class ApprovalAuditLog(Base):
    """Approval workflow audit log."""
    __tablename__ = "approval_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    response_queue_id = Column(UUID(as_uuid=True), ForeignKey("ai_response_queue.id"), nullable=False)
    action = Column(String(50), nullable=False)
    original_response = Column(Text, nullable=True)
    final_response = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    approved_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    response_queue = relationship("AIResponseQueue", back_populates="audit_logs")


class WorkflowRetryAttempt(Base):
    """Workflow retry attempt tracking."""
    __tablename__ = "workflow_retry_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("orchestration_workflows.id"), nullable=False)
    reason = Column(Text, nullable=False)
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())
    success = Column(Boolean, nullable=True)

    # Relationships
    workflow = relationship("OrchestrationWorkflow", back_populates="retry_attempts")


class PaymentPlan(Base):
    """Payment plan tracking table."""
    __tablename__ = "payment_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    conversation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False)
    weekly_amount = Column(Float, nullable=False)
    weeks = Column(Integer, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="detected")
    confidence_score = Column(Float, nullable=True)
    validation_result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Escalation(Base):
    """Escalation tracking table."""
    __tablename__ = "escalations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    conversation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    escalation_type = Column(String(50), nullable=False)
    reason = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)
    auto_detected = Column(Boolean, nullable=False, default=True)
    status = Column(String(50), nullable=False, default="active")
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(100), nullable=True)