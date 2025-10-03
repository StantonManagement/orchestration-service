"""
Tests for Payment Plan Extraction Utility

Tests extraction patterns and confidence scoring for payment plans.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from app.utils.payment_plan_extraction import (
    PaymentPlanExtractor, ExtractedPaymentPlan
)


class TestPaymentPlanExtractor:
    """Test cases for PaymentPlanExtractor class"""

    @pytest.fixture
    def extractor(self):
        """Create PaymentPlanExtractor instance for testing"""
        return PaymentPlanExtractor()

    def test_extract_simple_payment_plan(self, extractor):
        """Test extraction of simple payment plan format"""
        text = "I can offer a payment plan of $100 per week for 8 weeks starting next Monday."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        assert payment_plan.weekly_amount == Decimal('100')
        assert payment_plan.duration_weeks == 8
        assert payment_plan.confidence.value in ['low', 'medium', 'high']
        assert 'combined:' in str(payment_plan.extraction_patterns)

    def test_extract_dollar_amount_only(self, extractor):
        """Test extraction with just dollar sign and amount"""
        text = "I can pay $50 weekly for 4 weeks as part of a payment arrangement."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        assert payment_plan.weekly_amount == Decimal('50')
        assert payment_plan.duration_weeks == 4

    def test_extract_dollars_text_format(self, extractor):
        """Test extraction with 'dollars' text format"""
        text = "I propose paying 75 dollars per week for 6 weeks as a payment plan."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        assert payment_plan.weekly_amount == Decimal('75')
        assert payment_plan.duration_weeks == 6

    def test_extract_months_duration(self, extractor):
        """Test extraction with duration in months"""
        text = "I can make monthly payments of $200 for 2 months as a payment plan."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        assert payment_plan.weekly_amount == Decimal('200')
        # 2 months should be converted to 8 weeks (approximate)
        assert payment_plan.duration_weeks == 8

    def test_extract_with_start_date(self, extractor):
        """Test extraction with start date"""
        text = "I want to start a payment plan of $80 per week for 10 weeks starting Friday."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        assert payment_plan.weekly_amount == Decimal('80')
        assert payment_plan.duration_weeks == 10
        assert payment_plan.start_date is not None
        assert payment_plan.confidence_score > 0.8

    def test_extract_tomorrow_start(self, extractor):
        """Test extraction with 'tomorrow' start date"""
        text = "I'll start a payment plan tomorrow, paying $60 per week for 5 weeks."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        assert payment_plan.start_date is not None
        expected_date = datetime.now() + timedelta(days=1)
        assert payment_plan.start_date.date() == expected_date.date()

    def test_low_confidence_extraction(self, extractor):
        """Test extraction with low confidence (missing keywords)"""
        text = "I can pay 100 for 8 weeks."

        payment_plan = extractor.extract_payment_plan(text)

        # Should not extract due to missing payment plan keywords
        assert payment_plan is None

    def test_amount_out_of_range(self, extractor):
        """Test that amounts outside reasonable range are rejected"""
        text = "I can pay $10 per week for 20 weeks as a payment plan."

        payment_plan = extractor.extract_payment_plan(text)

        # Should not extract due to amount below minimum
        assert payment_plan is None

    def test_duration_out_of_range(self, extractor):
        """Test that durations outside reasonable range are rejected"""
        text = "I can pay $100 per week for 15 weeks as a payment plan."

        payment_plan = extractor.extract_payment_plan(text)

        # Should not extract due to duration above maximum
        assert payment_plan is None

    def test_no_payment_plan_keywords(self, extractor):
        """Test text without payment plan keywords"""
        text = "I will call you next week to discuss my account."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is None

    def test_multiple_amounts(self, extractor):
        """Test extraction with multiple amounts in text"""
        text = "I owe $500 but can pay $100 per week for 5 weeks in a payment plan."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        # Should extract the weekly amount, not the total balance
        assert payment_plan.weekly_amount == Decimal('100')
        assert payment_plan.duration_weeks == 5

    def test_bucks_informal_format(self, extractor):
        """Test extraction with informal 'bucks' format"""
        text = "I can pay 50 bucks per week for 4 weeks as a payment plan."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        assert payment_plan.weekly_amount == Decimal('50')

    def test_fractional_amount(self, extractor):
        """Test extraction with fractional amount"""
        text = "I can pay $75.50 per week for 6 weeks in a payment plan."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        assert payment_plan.weekly_amount == Decimal('75.50')

    def test_confidence_scoring(self, extractor):
        """Test confidence score calculation"""
        # High confidence: structured format with all components
        text1 = "I propose a payment plan: $100 per week for 8 weeks starting next Monday."
        plan1 = extractor.extract_payment_plan(text1)

        # Medium confidence: missing start date
        text2 = "I can do a payment plan of $80 per week for 6 weeks."
        plan2 = extractor.extract_payment_plan(text2)

        # Lower confidence: less structured format
        text3 = "Payment arrangement: 75 dollars weekly for 5 weeks."
        plan3 = extractor.extract_payment_plan(text3)

        assert plan1.confidence_score > plan2.confidence_score
        assert plan2.confidence_score > plan3.confidence_score

    def test_extract_from_ai_response_structured(self, extractor):
        """Test extraction from AI response with structured format"""
        ai_response = "Based on your situation, I recommend: PAYMENT_PLAN: weekly=150, weeks=8"

        payment_plan = extractor.extract_from_ai_response(ai_response)

        assert payment_plan is not None
        assert payment_plan.weekly_amount == Decimal('150')
        assert payment_plan.duration_weeks == 8
        assert payment_plan.raw_text is not None
        assert payment_plan.confidence_score >= 0.9  # High confidence for structured AI

    def test_extract_from_ai_response_unstructured(self, extractor):
        """Test extraction from AI response without structured format"""
        ai_response = "I can offer you a payment plan of $120 per week for 6 weeks. This arrangement will help you manage your payments."

        payment_plan = extractor.extract_from_ai_response(ai_response)

        assert payment_plan is not None
        assert payment_plan.weekly_amount == Decimal('120')
        assert payment_plan.duration_weeks == 6
        assert payment_plan.raw_text is not None

    def test_extract_from_ai_response_no_plan(self, extractor):
        """Test AI response without payment plan"""
        ai_response = "I understand your situation. Let me know if you need any assistance with your account."

        payment_plan = extractor.extract_from_ai_response(ai_response)

        assert payment_plan is None

    def test_start_date_day_of_week(self, extractor):
        """Test extraction with specific day of week"""
        # Test with different days
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

        for day in days:
            text = f"I'll start my payment plan of $90 per week for 7 weeks on {day}."
            payment_plan = extractor.extract_payment_plan(text)

            assert payment_plan is not None
            assert payment_plan.start_date is not None
            # Start date should be in the future
            assert payment_plan.start_date.date() >= datetime.now().date()

    def test_extraction_patterns_recorded(self, extractor):
        """Test that extraction patterns are properly recorded"""
        text = "Payment plan: $100 per week for 8 weeks starting tomorrow."

        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        assert len(payment_plan.extraction_patterns) >= 2
        assert any('amount:' in pattern for pattern in payment_plan.extraction_patterns)
        assert any('duration:' in pattern for pattern in payment_plan.extraction_patterns)

    @pytest.mark.parametrize("text,expected_amount,expected_duration", [
        ("$50 weekly for 4 weeks payment plan", Decimal('50'), 4),
        ("75 dollars per week for 6 weeks arrangement", Decimal('75'), 6),
        ("$100/week for 8 weeks payment plan", Decimal('100'), 8),
        ("Pay $80 each week for 5 weeks", Decimal('80'), 5),
    ])
    def test_various_payment_plan_formats(self, extractor, text, expected_amount, expected_duration):
        """Test various payment plan text formats"""
        payment_plan = extractor.extract_payment_plan(text)

        assert payment_plan is not None
        assert payment_plan.weekly_amount == expected_amount
        assert payment_plan.duration_weeks == expected_duration

    def test_edge_case_empty_text(self, extractor):
        """Test extraction from empty text"""
        payment_plan = extractor.extract_payment_plan("")
        assert payment_plan is None

    def test_edge_case_none_text(self, extractor):
        """Test extraction from None text"""
        with pytest.raises(AttributeError):
            extractor.extract_payment_plan(None)