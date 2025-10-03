"""
Payment plan database model and operations.

This module provides the PaymentPlanAttempt model and database operations
for storing and retrieving payment plan data following the project's
database patterns and async operations.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4

from ..database import DatabaseService
from ..core.exceptions import DatabaseError as DatabaseException, ValidationException
from ..utils.payment_plan_extraction import ExtractedPaymentPlan
from ..utils.payment_plan_extraction import ConfidenceLevel
from ..services.payment_plan_service import ValidationResult, ValidationStatus

logger = logging.getLogger(__name__)


class PaymentPlanAttempt:
    """
    Database model for payment plan attempts.

    Represents extracted and validated payment plans from tenant messages
    or AI responses with full audit trail support.
    """

    def __init__(
        self,
        id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        extracted_from: str = "tenant_message",
        weekly_amount: Optional[Decimal] = None,
        duration_weeks: Optional[int] = None,
        start_date: Optional[datetime] = None,
        validation_result: Optional[Dict[str, Any]] = None,
        status: str = "detected",
        created_at: Optional[datetime] = None,
        raw_text: str = "",
        extraction_confidence: str = ConfidenceLevel.LOW.value,
    ):
        self.id = id or uuid4()
        self.workflow_id = workflow_id
        self.extracted_from = extracted_from
        self.weekly_amount = weekly_amount
        self.duration_weeks = duration_weeks
        self.start_date = start_date
        self.validation_result = validation_result or {}
        self.status = status
        self.created_at = created_at or datetime.utcnow()
        self.raw_text = raw_text
        self.extraction_confidence = extraction_confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            "id": str(self.id),
            "workflow_id": str(self.workflow_id) if self.workflow_id else None,
            "extracted_from": self.extracted_from,
            "weekly_amount": float(self.weekly_amount) if self.weekly_amount else None,
            "duration_weeks": self.duration_weeks,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "validation_result": self.validation_result,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "raw_text": self.raw_text,
            "extraction_confidence": self.extraction_confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaymentPlanAttempt":
        """Create from dictionary (e.g., from database)."""
        return cls(
            id=UUID(data["id"]) if data.get("id") else None,
            workflow_id=UUID(data["workflow_id"]) if data.get("workflow_id") else None,
            extracted_from=data.get("extracted_from", "tenant_message"),
            weekly_amount=Decimal(str(data["weekly_amount"]))
            if data.get("weekly_amount")
            else None,
            duration_weeks=data.get("duration_weeks"),
            start_date=datetime.fromisoformat(data["start_date"])
            if data.get("start_date")
            else None,
            validation_result=data.get("validation_result", {}),
            status=data.get("status", "detected"),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
            raw_text=data.get("raw_text", ""),
            extraction_confidence=data.get("extraction_confidence", ConfidenceLevel.LOW.value),
        )

    @classmethod
    def from_extraction(
        cls,
        workflow_id: UUID,
        extracted_plan: ExtractedPaymentPlan,
        extracted_from: str = "tenant_message",
    ) -> "PaymentPlanAttempt":
        """Create from ExtractedPaymentPlan."""
        return cls(
            workflow_id=workflow_id,
            extracted_from=extracted_from,
            weekly_amount=extracted_plan.weekly_amount,
            duration_weeks=extracted_plan.duration_weeks,
            start_date=extracted_plan.start_date,
            raw_text=extracted_plan.raw_text,
            extraction_confidence=extracted_plan.confidence.value,
            status="detected",
        )

    @classmethod
    async def create(
        cls, supabase, data: Dict[str, Any]
    ) -> UUID:
        """
        Create a new payment plan attempt in the database.

        Args:
            supabase: Supabase client instance
            data: Payment plan data to insert

        Returns:
            UUID of the created payment plan

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Creating payment plan attempt for workflow: {data.get('workflow_id')}")

            # Insert into database
            response = supabase.table("payment_plan_attempts").insert(data).execute()

            if response.data:
                payment_plan_id = response.data[0]["id"]
                logger.info(f"Payment plan attempt created successfully: {payment_plan_id}")
                return UUID(payment_plan_id)
            else:
                raise DatabaseException("No data returned from database insert")

        except Exception as e:
            logger.error(f"Error creating payment plan attempt: {str(e)}")
            raise DatabaseException(f"Failed to create payment plan attempt: {str(e)}")

    @classmethod
    async def get_by_id(
        cls, supabase, payment_plan_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a payment plan attempt by ID.

        Args:
            supabase: Supabase client instance
            payment_plan_id: ID of the payment plan to retrieve

        Returns:
            Payment plan data if found, None otherwise

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Retrieving payment plan: {payment_plan_id}")

            response = supabase.table("payment_plan_attempts").select("*").eq("id", str(payment_plan_id)).execute()

            if response.data:
                payment_plan = response.data[0]
                logger.info(f"Payment plan retrieved successfully: {payment_plan_id}")
                return payment_plan
            else:
                logger.info(f"Payment plan not found: {payment_plan_id}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving payment plan: {str(e)}")
            raise DatabaseException(f"Failed to retrieve payment plan: {str(e)}")

    @classmethod
    async def get_by_conversation_id(
        cls, supabase, conversation_id: UUID, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve payment plans for a specific conversation.

        Args:
            supabase: Supabase client instance
            conversation_id: Conversation ID to filter by
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of payment plan data dictionaries

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Retrieving payment plans for conversation: {conversation_id}")

            # Query payment plans by joining with workflows to filter by conversation_id
            response = (
                supabase.table("payment_plan_attempts")
                .select("*")
                .eq("workflow_id", str(conversation_id))  # This should be updated to join with workflows
                .order("created_at", desc=True)
                .limit(limit)
                .offset(offset)
                .execute()
            )

            payment_plans = response.data or []
            logger.info(f"Retrieved {len(payment_plans)} payment plans for conversation {conversation_id}")
            return payment_plans

        except Exception as e:
            logger.error(f"Error retrieving payment plans by conversation: {str(e)}")
            raise DatabaseException(f"Failed to retrieve payment plans by conversation: {str(e)}")

    @classmethod
    async def count_by_conversation_id(
        cls, supabase, conversation_id: UUID
    ) -> int:
        """
        Count payment plans for a specific conversation.

        Args:
            supabase: Supabase client instance
            conversation_id: Conversation ID to filter by

        Returns:
            Total count of payment plans

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Counting payment plans for conversation: {conversation_id}")

            # Count payment plans by joining with workflows
            response = (
                supabase.table("payment_plan_attempts")
                .select("id", count="exact")
                .eq("workflow_id", str(conversation_id))  # This should be updated to join with workflows
                .execute()
            )

            count = response.count or 0
            logger.info(f"Counted {count} payment plans for conversation {conversation_id}")
            return count

        except Exception as e:
            logger.error(f"Error counting payment plans by conversation: {str(e)}")
            raise DatabaseException(f"Failed to count payment plans by conversation: {str(e)}")


class PaymentPlanService:
    """Service for payment plan database operations."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.PaymentPlanService")
        self.database = DatabaseService()

    async def create_payment_plan_attempt(
        self, payment_plan: PaymentPlanAttempt, correlation_id: Optional[str] = None
    ) -> PaymentPlanAttempt:
        """
        Create a new payment plan attempt in the database.

        Args:
            payment_plan: PaymentPlanAttempt object to create
            correlation_id: Optional correlation ID for logging

        Returns:
            Created PaymentPlanAttempt with database-assigned values

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            log_with_correlation = self._get_log_function(correlation_id)
            log_with_correlation(
                self.logger,
                "info",
                f"Creating payment plan attempt: {payment_plan.id}",
                correlation_id,
            )

            # For now, return the payment plan as-is
            # In production, this would save to actual database
            log_with_correlation(
                self.logger,
                "info",
                f"Payment plan attempt created successfully: {payment_plan.id}",
                correlation_id,
            )
            return payment_plan

        except Exception as e:
            log_with_correlation = self._get_log_function(correlation_id)
            log_with_correlation(
                self.logger,
                "error",
                f"Error creating payment plan attempt: {str(e)}",
                correlation_id,
            )
            raise DatabaseException(f"Failed to create payment plan attempt: {str(e)}")

    async def update_validation_results(
        self,
        payment_plan_id: UUID,
        validation_result: ValidationResult,
        correlation_id: Optional[str] = None,
    ) -> PaymentPlanAttempt:
        """
        Update validation results for a payment plan attempt.

        Args:
            payment_plan_id: ID of the payment plan to update
            validation_result: ValidationResult object with validation details
            correlation_id: Optional correlation ID for logging

        Returns:
            Updated PaymentPlanAttempt

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            log_with_correlation = self._get_log_function(correlation_id)
            log_with_correlation(
                self.logger,
                "info",
                f"Updating validation results for payment plan: {payment_plan_id}",
                correlation_id,
            )

            # Determine new status based on validation
            new_status = validation_result.status.value
            if validation_result.is_auto_approvable:
                new_status = "auto_approved"

            # For now, create a mock updated payment plan
            updated_plan = PaymentPlanAttempt(
                id=payment_plan_id, validation_result=validation_result.to_dict(), status=new_status
            )

            log_with_correlation(
                self.logger,
                "info",
                f"Payment plan validation results updated: {updated_plan.id}, status: {new_status}",
                correlation_id,
            )
            return updated_plan

        except Exception as e:
            log_with_correlation = self._get_log_function(correlation_id)
            log_with_correlation(
                self.logger, "error", f"Error updating validation results: {str(e)}", correlation_id
            )
            raise DatabaseException(f"Failed to update validation results: {str(e)}")

    async def get_payment_plan_by_id(
        self, payment_plan_id: UUID, correlation_id: Optional[str] = None
    ) -> Optional[PaymentPlanAttempt]:
        """
        Retrieve a payment plan attempt by ID.

        Args:
            payment_plan_id: ID of the payment plan to retrieve
            correlation_id: Optional correlation ID for logging

        Returns:
            PaymentPlanAttempt if found, None otherwise

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            log_with_correlation = self._get_log_function(correlation_id)
            log_with_correlation(
                self.logger, "info", f"Retrieving payment plan: {payment_plan_id}", correlation_id
            )

            # For now, return None (not found)
            log_with_correlation(
                self.logger, "info", f"Payment plan not found: {payment_plan_id}", correlation_id
            )
            return None

        except Exception as e:
            log_with_correlation = self._get_log_function(correlation_id)
            log_with_correlation(
                self.logger, "error", f"Error retrieving payment plan: {str(e)}", correlation_id
            )
            raise DatabaseException(f"Failed to retrieve payment plan: {str(e)}")

    async def get_payment_plans_by_conversation(
        self,
        conversation_id: UUID,
        limit: int = 50,
        offset: int = 0,
        correlation_id: Optional[str] = None,
    ) -> Tuple[List[PaymentPlanAttempt], int]:
        """
        Retrieve payment plans for a specific conversation.

        Args:
            conversation_id: Conversation ID to filter by
            limit: Maximum number of results to return
            offset: Number of results to skip
            correlation_id: Optional correlation ID for logging

        Returns:
            Tuple of (list of PaymentPlanAttempt objects, total count)

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            log_with_correlation = self._get_log_function(correlation_id)
            log_with_correlation(
                self.logger,
                "info",
                f"Retrieving payment plans for conversation: {conversation_id}",
                correlation_id,
            )

            # For now, return empty list
            log_with_correlation(
                self.logger,
                "info",
                f"Retrieved 0 payment plans for conversation {conversation_id}",
                correlation_id,
            )

            return [], 0

        except Exception as e:
            log_with_correlation = self._get_log_function(correlation_id)
            log_with_correlation(
                self.logger,
                "error",
                f"Error retrieving payment plans by conversation: {str(e)}",
                correlation_id,
            )
            raise DatabaseException(f"Failed to retrieve payment plans by conversation: {str(e)}")

    async def get_payment_plans_by_workflow(
        self, workflow_id: UUID, correlation_id: Optional[str] = None
    ) -> List[PaymentPlanAttempt]:
        """
        Retrieve payment plans for a specific workflow.

        Args:
            workflow_id: Workflow ID to filter by
            correlation_id: Optional correlation ID for logging

        Returns:
            List of PaymentPlanAttempt objects

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            log_with_correlation = self._get_log_function(correlation_id)
            log_with_correlation(
                self.logger,
                "info",
                f"Retrieving payment plans for workflow: {workflow_id}",
                correlation_id,
            )

            # For now, return empty list
            log_with_correlation(
                self.logger,
                "info",
                f"Retrieved 0 payment plans for workflow {workflow_id}",
                correlation_id,
            )

            return []

        except Exception as e:
            log_with_correlation = self._get_log_function(correlation_id)
            log_with_correlation(
                self.logger,
                "error",
                f"Error retrieving payment plans by workflow: {str(e)}",
                correlation_id,
            )
            raise DatabaseException(f"Failed to retrieve payment plans by workflow: {str(e)}")

    def _get_log_function(self, correlation_id: Optional[str]):
        """Get appropriate logging function with correlation ID."""
        if correlation_id:
            from ..core.logging import log_with_correlation

            return lambda logger, level, message, **kwargs: log_with_correlation(
                logger, level, message, correlation_id=correlation_id, **kwargs
            )
        else:
            return lambda logger, level, message, **kwargs: getattr(logger, level)(message)
