"""
Tests for Payment Plan Validation Service

Tests business rule validation and auto-approval logic.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from app.services.payment_plan_service import (
    PaymentPlanValidator, ValidationStatus, ValidationError, ValidationResult
)
from app.utils.payment_plan_extraction import ExtractedPaymentPlan, ConfidenceLevel


class TestPaymentPlanValidator:
    """Test cases for PaymentPlanValidator class"""

    @pytest.fixture
    def validator(self):
        """Create PaymentPlanValidator instance for testing"""
        return PaymentPlanValidator()

    @pytest.fixture
    def valid_payment_plan(self):
        """Create a valid payment plan for testing"""
        return ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan: $100 per week for 8 weeks starting next Monday.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

    def test_validate_valid_payment_plan(self, validator, valid_payment_plan):
        """Test validation of a valid payment plan"""
        result = validator.validate_payment_plan(valid_payment_plan)

        assert result.is_valid is True
        assert result.is_auto_approvable is True
        assert result.status == ValidationStatus.AUTO_APPROVED
        assert len(result.errors) == 0
        assert "valid and eligible for auto-approval" in result.validation_summary

    def test_validate_amount_below_minimum(self, validator):
        """Test validation with amount below minimum"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('20'),  # Below $25 minimum
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan: $20 per week for 8 weeks.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is False
        assert result.is_auto_approvable is False
        assert result.status == ValidationStatus.INVALID
        assert len(result.errors) > 0
        assert any("below minimum" in error.message for error in result.errors)

    def test_validate_amount_above_maximum(self, validator):
        """Test validation with amount above maximum"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('1500'),  # Above $1000 maximum
            duration_weeks=4,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan: $1500 per week for 4 weeks.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("above maximum" in error.message for error in result.errors)

    def test_validate_duration_below_minimum(self, validator):
        """Test validation with duration below minimum"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=0,  # Below 1 week minimum
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan with invalid duration.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("below minimum" in error.message for error in result.errors)

    def test_validate_duration_above_maximum(self, validator):
        """Test validation with duration above maximum"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=15,  # Above 12 week maximum
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan: $100 per week for 15 weeks.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("above maximum" in error.message for error in result.errors)

    def test_validate_low_confidence_score(self, validator):
        """Test validation with low confidence score"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence_score=0.4,  # Below 0.6 minimum
                        raw_text="Unclear payment plan text.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("below minimum" in error.message for error in result.errors)

    def test_validate_start_date_too_far(self, validator):
        """Test validation with start date too far in future"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=45),  # Too far in future
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan starting far in future.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("too far ahead" in error.message for error in result.errors)

    def test_validate_start_date_in_past(self, validator):
        """Test validation with start date in the past"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=8,
            start_date=datetime.now() - timedelta(days=5),  # In the past
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan starting in past.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("cannot be in the past" in error.message for error in result.errors)

    def test_validate_no_start_date_warning(self, validator):
        """Test validation with no start date (should generate warning)"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=8,
            start_date=None,  # No start date
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan without start date.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("No start date specified" in warning.message for warning in result.warnings)

    def test_validate_short_duration_warning(self, validator):
        """Test validation with short duration (should generate warning)"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=2,  # Short duration
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan: $100 per week for 2 weeks.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("Short payment plan" in warning.message for warning in result.warnings)

    def test_validate_long_duration_warning(self, validator):
        """Test validation with long duration (should generate warning)"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=11,  # Long duration
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan: $100 per week for 11 weeks.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("Extended payment plan" in warning.message for warning in result.warnings)

    def test_validate_with_tenant_context_high_debt_to_income(self, validator):
        """Test validation with tenant context showing high debt-to-income ratio"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('500'),  # High payment amount
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan: $500 per week for 8 weeks.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        tenant_context = {
            "average_monthly_income": 1000  # $1000/month = ~$231/week
        }

        result = validator.validate_payment_plan(payment_plan, tenant_context)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("high compared to tenant's weekly income" in warning.message for warning in result.warnings)

    def test_validate_with_tenant_context_insufficient_payment(self, validator):
        """Test validation with tenant context showing insufficient payment for balance"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('25'),
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan: $25 per week for 8 weeks.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        tenant_context = {
            "total_balance": 5000  # $5000 balance, but payment plan only covers $200
        }

        result = validator.validate_payment_plan(payment_plan, tenant_context)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("insufficient to address outstanding balance" in warning.message for warning in result.warnings)

    def test_validate_with_existing_payment_plans_warning(self, validator):
        """Test validation with existing payment plans"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan: $100 per week for 8 weeks.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        tenant_context = {
            "existing_payment_plans": 2
        }

        result = validator.validate_payment_plan(payment_plan, tenant_context)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("existing payment plan" in warning.message for warning in result.warnings)

    def test_validate_with_payment_history_issues_warning(self, validator):
        """Test validation with poor payment history"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan: $100 per week for 8 weeks.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        tenant_context = {
            "payment_history": {
                "missed_payments": 5  # More than 2 missed payments
            }
        }

        result = validator.validate_payment_plan(payment_plan, tenant_context)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("history of missed payments" in warning.message for warning in result.warnings)

    def test_auto_approval_eligibility_high_confidence(self, validator):
        """Test auto-approval eligibility with high confidence"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('150'),
            duration_weeks=6,  # Within reasonable duration
            start_date=datetime.now() + timedelta(days=7),
            confidence_score=0.95,  # High confidence
                        raw_text="Clear payment plan with high confidence.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_auto_approvable is True
        assert result.status == ValidationStatus.AUTO_APPROVED

    def test_auto_approval_eligibility_low_confidence(self, validator):
        """Test auto-approval ineligibility with low confidence"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence_score=0.7,  # Below auto-approval threshold
                        raw_text="Payment plan with moderate confidence.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_auto_approvable is False
        assert result.status == ValidationStatus.VALID

    def test_needs_review_status_with_warnings(self, validator):
        """Test needs_review status when there are warnings"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=2,  # Short duration - generates warning
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan with warning condition.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.is_valid is True
        assert result.is_auto_approvable is False
        assert result.status == ValidationStatus.NEEDS_REVIEW
        assert len(result.warnings) > 0

    def test_validation_summary_generation(self, validator):
        """Test validation summary generation"""
        # Test auto-approved summary
        valid_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('150'),
            duration_weeks=6,
            start_date=datetime.now() + timedelta(days=7),
            confidence_score=0.95,
                        raw_text="Valid payment plan.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result1 = validator.validate_payment_plan(valid_plan)
        assert "auto-approval" in result1.validation_summary

        # Test needs review summary
        plan_with_warnings = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=2,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Plan with warnings.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result2 = validator.validate_payment_plan(plan_with_warnings)
        assert "review" in result2.validation_summary
        assert "warning" in result2.validation_summary

        # Test invalid summary
        invalid_plan = ExtractedPaymentPlan(
            weekly_amount=Decimal('10'),  # Too low
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Invalid payment plan.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result3 = validator.validate_payment_plan(invalid_plan)
        assert "invalid" in result3.validation_summary
        assert "error" in result3.validation_summary

    @pytest.mark.parametrize("amount,duration,confidence,expected_status", [
        (Decimal('50'), 4, 0.9, ValidationStatus.VALID),  # Valid but not auto-approvable
        (Decimal('150'), 6, 0.95, ValidationStatus.AUTO_APPROVED),  # Auto-approvable
        (Decimal('20'), 4, 0.9, ValidationStatus.INVALID),  # Amount too low
        (Decimal('100'), 15, 0.9, ValidationStatus.INVALID),  # Duration too long
        (Decimal('100'), 8, 0.4, ValidationStatus.INVALID),  # Confidence too low
    ])
    def test_validation_scenarios(self, validator, amount, duration, confidence, expected_status):
        """Test various validation scenarios"""
        payment_plan = ExtractedPaymentPlan(
            weekly_amount=amount,
            duration_weeks=duration,
            start_date=datetime.now() + timedelta(days=7),
            confidence_score=confidence,
                        raw_text="Test payment plan.",
            extraction_patterns=["amount: pattern", "duration: pattern"]
        )

        result = validator.validate_payment_plan(payment_plan)

        assert result.status == expected_status

    def test_edge_case_missing_required_fields(self, validator):
        """Test validation with missing required fields"""
        # Missing weekly amount
        payment_plan1 = ExtractedPaymentPlan(
            weekly_amount=None,
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan missing amount.",
            extraction_patterns=["duration: pattern"]
        )

        result1 = validator.validate_payment_plan(payment_plan1)
        assert result1.is_valid is False
        assert any("required" in error.message for error in result1.errors)

        # Missing duration
        payment_plan2 = ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=None,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
                        raw_text="Payment plan missing duration.",
            extraction_patterns=["amount: pattern"]
        )

        result2 = validator.validate_payment_plan(payment_plan2)
        assert result2.is_valid is False
        assert any("required" in error.message for error in result2.errors)