"""
Payment Plan Validation Service

Validates payment plans against business rules and provides detailed validation reports.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from app.utils.payment_plan_extraction import ExtractedPaymentPlan, ConfidenceLevel

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    NEEDS_REVIEW = "needs_review"
    AUTO_APPROVED = "auto_approved"


@dataclass
class ValidationError:
    """Individual validation error with severity"""

    field: str
    message: str
    severity: str  # "error", "warning", "info"
    rule_code: str


@dataclass
class ValidationResult:
    """Complete validation result with detailed reporting"""

    status: ValidationStatus
    is_valid: bool
    is_auto_approvable: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    info: List[ValidationError]
    confidence_adjustment: float  # How much confidence was reduced due to validation
    validation_summary: str


class PaymentPlanValidator:
    """Validates payment plans against business rules"""

    # Business rule constants
    MIN_WEEKLY_PAYMENT = Decimal("25.00")
    MAX_WEEKLY_PAYMENT = Decimal("1000.00")
    MIN_DURATION_WEEKS = 1
    MAX_DURATION_WEEKS = 12
    MIN_CONFIDENCE_SCORE = 0.6
    AUTO_APPROVAL_CONFIDENCE = 0.85

    # Reasonable start date constraints
    MAX_START_DATE_DAYS_FUTURE = 30
    MIN_START_DATE_DAYS_FUTURE = 1

    def __init__(self):
        """Initialize validator with default business rules"""
        self.validation_rules = self._initialize_validation_rules()

    def _initialize_validation_rules(self) -> Dict[str, Dict]:
        """Initialize validation rule definitions"""
        return {
            "weekly_amount": {
                "min": self.MIN_WEEKLY_PAYMENT,
                "max": self.MAX_WEEKLY_PAYMENT,
                "required": True,
                "error_code": "AMOUNT_OUT_OF_RANGE",
            },
            "duration_weeks": {
                "min": self.MIN_DURATION_WEEKS,
                "max": self.MAX_DURATION_WEEKS,
                "required": True,
                "error_code": "DURATION_OUT_OF_RANGE",
            },
            "confidence_score": {
                "min": self.MIN_CONFIDENCE_SCORE,
                "required": True,
                "error_code": "LOW_CONFIDENCE",
            },
            "start_date": {
                "min_days": self.MIN_START_DATE_DAYS_FUTURE,
                "max_days": self.MAX_START_DATE_DAYS_FUTURE,
                "required": False,
                "error_code": "START_DATE_UNREASONABLE",
            },
        }

    def validate_payment_plan(
        self, payment_plan: ExtractedPaymentPlan, tenant_context: Optional[Dict] = None
    ) -> ValidationResult:
        """
        Validate payment plan against business rules

        Args:
            payment_plan: Extracted payment plan to validate
            tenant_context: Optional tenant data for contextual validation

        Returns:
            ValidationResult with detailed validation information
        """
        logger.info(
            f"Validating payment plan: ${payment_plan.weekly_amount}/week for {payment_plan.duration_weeks} weeks"
        )

        errors = []
        warnings = []
        info = []

        confidence_adjustment = 0.0

        # Validate weekly amount
        amount_errors, amount_warnings = self._validate_weekly_amount(
            payment_plan.weekly_amount, tenant_context
        )
        errors.extend(amount_errors)
        warnings.extend(amount_warnings)

        # Validate duration
        duration_errors, duration_warnings = self._validate_duration_weeks(
            payment_plan.duration_weeks
        )
        errors.extend(duration_errors)
        warnings.extend(duration_warnings)

        # Validate confidence score
        confidence_errors = self._validate_confidence_score(payment_plan.confidence.value)
        errors.extend(confidence_errors)

        # Validate start date
        start_date_errors, start_date_warnings = self._validate_start_date(payment_plan.start_date)
        errors.extend(start_date_errors)
        warnings.extend(start_date_warnings)

        # Contextual validation if tenant data is available
        if tenant_context:
            contextual_errors, contextual_warnings = self._validate_against_tenant_context(
                payment_plan, tenant_context
            )
            errors.extend(contextual_errors)
            warnings.extend(contextual_warnings)

        # Determine validation status
        is_valid = len(errors) == 0
        is_auto_approvable = self._check_auto_approval_eligibility(
            payment_plan, errors, warnings, confidence_adjustment
        )

        status = self._determine_validation_status(is_valid, is_auto_approvable, warnings)

        # Create validation summary
        validation_summary = self._create_validation_summary(
            status, len(errors), len(warnings), is_auto_approvable
        )

        logger.info(
            f"Validation complete: status={status.value}, valid={is_valid}, auto_approvable={is_auto_approvable}"
        )

        return ValidationResult(
            status=status,
            is_valid=is_valid,
            is_auto_approvable=is_auto_approvable,
            errors=errors,
            warnings=warnings,
            info=info,
            confidence_adjustment=confidence_adjustment,
            validation_summary=validation_summary,
        )

    def _validate_weekly_amount(
        self, amount: Optional[Decimal], tenant_context: Optional[Dict]
    ) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Validate weekly payment amount"""
        errors = []
        warnings = []

        if amount is None:
            errors.append(
                ValidationError(
                    field="weekly_amount",
                    message="Weekly payment amount is required",
                    severity="error",
                    rule_code="AMOUNT_REQUIRED",
                )
            )
            return errors, warnings

        # Check minimum amount
        if amount < self.MIN_WEEKLY_PAYMENT:
            errors.append(
                ValidationError(
                    field="weekly_amount",
                    message=f"Weekly payment ${amount} is below minimum ${self.MIN_WEEKLY_PAYMENT}",
                    severity="error",
                    rule_code="AMOUNT_BELOW_MINIMUM",
                )
            )

        # Check maximum amount
        if amount > self.MAX_WEEKLY_PAYMENT:
            errors.append(
                ValidationError(
                    field="weekly_amount",
                    message=f"Weekly payment ${amount} is above maximum ${self.MAX_WEEKLY_PAYMENT}",
                    severity="error",
                    rule_code="AMOUNT_ABOVE_MAXIMUM",
                )
            )

        # Contextual validation
        if tenant_context:
            amount_warnings.extend(self._validate_amount_context(amount, tenant_context))

        return errors, warnings

    def _validate_amount_context(
        self, amount: Decimal, tenant_context: Dict
    ) -> List[ValidationError]:
        """Validate amount against tenant context"""
        warnings = []

        # Check against tenant's typical payment amounts
        if "average_monthly_income" in tenant_context:
            monthly_income = Decimal(str(tenant_context["average_monthly_income"]))
            weekly_income = monthly_income / Decimal("4.33")  # Average weeks per month

            if amount > weekly_income * Decimal("0.3"):  # More than 30% of weekly income
                warnings.append(
                    ValidationError(
                        field="weekly_amount",
                        message=f"Weekly payment ${amount} is high compared to tenant's weekly income ${weekly_income:.2f}",
                        severity="warning",
                        rule_code="HIGH_DEBT_TO_INCOME",
                    )
                )

        # Check against outstanding balance
        if "total_balance" in tenant_context:
            total_balance = Decimal(str(tenant_context["total_balance"]))
            total_payment = amount * Decimal("12")  # Assume max duration

            if total_payment < total_balance * Decimal("0.1"):  # Less than 10% of balance
                warnings.append(
                    ValidationError(
                        field="weekly_amount",
                        message=f"Payment plan may be insufficient to address outstanding balance",
                        severity="warning",
                        rule_code="INSUFFICIENT_PAYMENT",
                    )
                )

        return warnings

    def _validate_duration_weeks(
        self, duration_weeks: Optional[int]
    ) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Validate payment plan duration"""
        errors = []
        warnings = []

        if duration_weeks is None:
            errors.append(
                ValidationError(
                    field="duration_weeks",
                    message="Payment plan duration is required",
                    severity="error",
                    rule_code="DURATION_REQUIRED",
                )
            )
            return errors, warnings

        # Check minimum duration
        if duration_weeks < self.MIN_DURATION_WEEKS:
            errors.append(
                ValidationError(
                    field="duration_weeks",
                    message=f"Duration {duration_weeks} weeks is below minimum {self.MIN_DURATION_WEEKS} weeks",
                    severity="error",
                    rule_code="DURATION_BELOW_MINIMUM",
                )
            )

        # Check maximum duration
        if duration_weeks > self.MAX_DURATION_WEEKS:
            errors.append(
                ValidationError(
                    field="duration_weeks",
                    message=f"Duration {duration_weeks} weeks exceeds maximum {self.MAX_DURATION_WEEKS} weeks",
                    severity="error",
                    rule_code="DURATION_ABOVE_MAXIMUM",
                )
            )

        # Warn about very short payment plans
        if duration_weeks <= 2:
            warnings.append(
                ValidationError(
                    field="duration_weeks",
                    message=f"Short payment plan ({duration_weeks} weeks) may indicate temporary arrangement",
                    severity="warning",
                    rule_code="SHORT_DURATION",
                )
            )

        # Warn about very long payment plans
        if duration_weeks >= 10:
            warnings.append(
                ValidationError(
                    field="duration_weeks",
                    message=f"Extended payment plan ({duration_weeks} weeks) requires additional review",
                    severity="warning",
                    rule_code="LONG_DURATION",
                )
            )

        return errors, warnings

    def _validate_confidence_score(self, confidence: ConfidenceLevel) -> List[ValidationError]:
        """Validate extraction confidence score"""
        errors = []

        # For now, treat MEDIUM and HIGH as acceptable confidence levels
        if confidence == ConfidenceLevel.LOW:
            errors.append(
                ValidationError(
                    field="confidence",
                    message=f"Confidence level {confidence.value} is too low for reliable processing",
                    severity="error",
                    rule_code="LOW_CONFIDENCE",
                )
            )

        return errors

    def _validate_start_date(
        self, start_date: Optional[datetime]
    ) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Validate payment plan start date"""
        errors = []
        warnings = []

        if start_date is None:
            # Start date is optional but helpful
            warnings.append(
                ValidationError(
                    field="start_date",
                    message="No start date specified - will assume immediate start",
                    severity="info",
                    rule_code="NO_START_DATE",
                )
            )
            return errors, warnings

        now = datetime.now()
        days_until_start = (start_date.date() - now.date()).days

        # Check if start date is too soon
        if days_until_start < self.MIN_START_DATE_DAYS_FUTURE:
            warnings.append(
                ValidationError(
                    field="start_date",
                    message="Start date is very soon - ensure tenant has time to prepare",
                    severity="warning",
                    rule_code="IMMEDIATE_START",
                )
            )

        # Check if start date is too far in future
        if days_until_start > self.MAX_START_DATE_DAYS_FUTURE:
            errors.append(
                ValidationError(
                    field="start_date",
                    message=f"Start date {days_until_start} days in future is too far ahead",
                    severity="error",
                    rule_code="START_DATE_TOO_FAR",
                )
            )

        # Check if start date is in the past
        if start_date.date() < now.date():
            errors.append(
                ValidationError(
                    field="start_date",
                    message="Start date cannot be in the past",
                    severity="error",
                    rule_code="PAST_START_DATE",
                )
            )

        return errors, warnings

    def _validate_against_tenant_context(
        self, payment_plan: ExtractedPaymentPlan, tenant_context: Dict
    ) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Validate payment plan against tenant-specific context"""
        errors = []
        warnings = []

        # Check if tenant has existing payment plans
        if "existing_payment_plans" in tenant_context:
            existing_plans = tenant_context["existing_payment_plans"]
            if existing_plans > 0:
                warnings.append(
                    ValidationError(
                        field="tenant_context",
                        message=f"Tenant has {existing_plans} existing payment plan(s) - review compatibility",
                        severity="warning",
                        rule_code="EXISTING_PAYMENT_PLANS",
                    )
                )

        # Check payment history
        if "payment_history" in tenant_context:
            payment_history = tenant_context["payment_history"]
            if payment_history.get("missed_payments", 0) > 2:
                warnings.append(
                    ValidationError(
                        field="tenant_context",
                        message="Tenant has history of missed payments - review plan feasibility",
                        severity="warning",
                        rule_code="PAYMENT_HISTORY_CONCERNS",
                    )
                )

        return errors, warnings

    def _check_auto_approval_eligibility(
        self,
        payment_plan: ExtractedPaymentPlan,
        errors: List[ValidationError],
        warnings: List[ValidationError],
        confidence_adjustment: float,
    ) -> bool:
        """Check if payment plan is eligible for auto-approval"""
        # Must have no errors
        if errors:
            return False

        # Must have high confidence level
        if payment_plan.confidence != ConfidenceLevel.HIGH:
            return False

        # Must have reasonable terms
        if (
            payment_plan.weekly_amount
            and payment_plan.duration_weeks
            and payment_plan.weekly_amount >= Decimal("50.00")
            and payment_plan.duration_weeks <= 8  # Reasonable amount
        ):  # Reasonable duration
            return True

        return False

    def _determine_validation_status(
        self, is_valid: bool, is_auto_approvable: bool, warnings: List[ValidationError]
    ) -> ValidationStatus:
        """Determine overall validation status"""
        if not is_valid:
            return ValidationStatus.INVALID

        if is_auto_approvable:
            return ValidationStatus.AUTO_APPROVED

        if warnings:
            return ValidationStatus.NEEDS_REVIEW

        return ValidationStatus.VALID

    def _create_validation_summary(
        self, status: ValidationStatus, error_count: int, warning_count: int, auto_approvable: bool
    ) -> str:
        """Create human-readable validation summary"""
        if status == ValidationStatus.AUTO_APPROVED:
            return f"Payment plan is valid and eligible for auto-approval"
        elif status == ValidationStatus.VALID:
            return f"Payment plan is valid and ready for review"
        elif status == ValidationStatus.NEEDS_REVIEW:
            return f"Payment plan requires review due to {warning_count} warning(s)"
        else:
            return f"Payment plan is invalid due to {error_count} error(s)"
