"""
Tests for Payment Plan API Endpoints

Tests REST API endpoints for payment plan detection and validation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.schemas.payment_plan import PaymentPlanDetectedRequest
from app.utils.payment_plan_extraction import ExtractedPaymentPlan
from app.services.payment_plan_service import ValidationStatus


class TestPaymentPlanAPI:
    """Test cases for Payment Plan API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def sample_request_data(self):
        """Create sample payment plan detection request data"""
        return {
            "conversation_id": str(uuid4()),
            "tenant_id": "tenant_123",
            "message_content": "I can offer a payment plan of $100 per week for 8 weeks starting next Monday.",
            "ai_response": "I understand your situation. Based on your offer of $100 per week for 8 weeks, I can help set up this payment arrangement.",
            "tenant_context": {
                "average_monthly_income": 2000,
                "total_balance": 800
            }
        }

    @pytest.fixture
    def sample_payment_plan(self):
        """Create sample extracted payment plan"""
        from app.utils.payment_plan_extraction import ConfidenceLevel
        return ExtractedPaymentPlan(
            weekly_amount=Decimal('100'),
            duration_weeks=8,
            start_date=datetime.now() + timedelta(days=7),
            confidence=ConfidenceLevel.HIGH,
            raw_text="I can offer a payment plan of $100 per week for 8 weeks starting next Monday.",
            extraction_patterns=["amount: pattern", "duration: pattern", "start_date: pattern"]
        )

    def test_payment_plan_detected_success(self, client, sample_request_data, sample_payment_plan):
        """Test successful payment plan detection endpoint"""
        with patch('app.api.payment_plan.payment_extractor.extract_payment_plan') as mock_extract, \
             patch('app.api.payment_plan.payment_validator.validate_payment_plan') as mock_validate, \
             patch('app.api.payment_plan._get_or_create_workflow') as mock_workflow, \
             patch('app.api.payment_plan._store_payment_plan_attempt') as mock_store:

            # Setup mocks
            mock_extract.return_value = sample_payment_plan
            mock_validate.return_value = Mock(
                status=ValidationStatus.AUTO_APPROVED,
                is_valid=True,
                is_auto_approvable=True,
                errors=[],
                warnings=[],
                info=[],
                validation_summary="Payment plan is valid and eligible for auto-approval"
            )
            mock_workflow.return_value = uuid4()
            mock_store.return_value = uuid4()

            # Make request
            response = client.post("/orchestrate/payment-plan-detected", json=sample_request_data)

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["payment_plan"] is not None
            assert data["validation"] is not None
            assert data["payment_plan_id"] is not None
            assert data["workflow_id"] is not None
            assert data["payment_plan"]["weekly_amount"] == 100.0
            assert data["payment_plan"]["duration_weeks"] == 8
            assert data["payment_plan"]["confidence_score"] == 0.9
            assert data["validation"]["status"] == "auto_approved"
            assert data["validation"]["is_valid"] is True
            assert data["validation"]["is_auto_approvable"] is True

            # Verify mocks were called
            mock_extract.assert_called_once()
            mock_validate.assert_called_once()
            mock_workflow.assert_called_once()
            mock_store.assert_called_once()

    def test_payment_plan_detected_no_plan_found(self, client, sample_request_data):
        """Test payment plan detection when no plan is found"""
        with patch('app.api.payment_plan.payment_extractor.extract_payment_plan') as mock_extract, \
             patch('app.api.payment_plan.payment_extractor.extract_from_ai_response') as mock_extract_ai:

            # Setup mocks - no payment plan found
            mock_extract.return_value = None
            mock_extract_ai.return_value = None

            # Make request
            response = client.post("/orchestrate/payment-plan-detected", json=sample_request_data)

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is False
            assert data["payment_plan"] is None
            assert data["validation"] is None
            assert data["payment_plan_id"] is None
            assert data["workflow_id"] is None
            assert "No payment plan detected" in data["message"]

    def test_payment_plan_detected_validation_errors(self, client, sample_request_data, sample_payment_plan):
        """Test payment plan detection with validation errors"""
        with patch('app.api.payment_plan.payment_extractor.extract_payment_plan') as mock_extract, \
             patch('app.api.payment_plan.payment_validator.validate_payment_plan') as mock_validate, \
             patch('app.api.payment_plan._get_or_create_workflow') as mock_workflow, \
             patch('app.api.payment_plan._store_payment_plan_attempt') as mock_store:

            # Setup mocks - validation fails
            mock_extract.return_value = sample_payment_plan
            mock_validate.return_value = Mock(
                status=ValidationStatus.INVALID,
                is_valid=False,
                is_auto_approvable=False,
                errors=[
                    Mock(field="weekly_amount", message="Amount below minimum", severity="error", rule_code="AMOUNT_BELOW_MINIMUM")
                ],
                warnings=[],
                info=[],
                validation_summary="Payment plan is invalid due to 1 error(s)"
            )
            mock_workflow.return_value = uuid4()
            mock_store.return_value = uuid4()

            # Make request
            response = client.post("/orchestrate/payment-plan-detected", json=sample_request_data)

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True  # Processing succeeded, but validation failed
            assert data["payment_plan"] is not None
            assert data["validation"] is not None
            assert data["validation"]["status"] == "invalid"
            assert data["validation"]["is_valid"] is False
            assert len(data["validation"]["errors"]) == 1
            assert data["validation"]["errors"][0]["field"] == "weekly_amount"

    def test_payment_plan_detected_with_warnings(self, client, sample_request_data, sample_payment_plan):
        """Test payment plan detection with validation warnings"""
        with patch('app.api.payment_plan.payment_extractor.extract_payment_plan') as mock_extract, \
             patch('app.api.payment_plan.payment_validator.validate_payment_plan') as mock_validate, \
             patch('app.api.payment_plan._get_or_create_workflow') as mock_workflow, \
             patch('app.api.payment_plan._store_payment_plan_attempt') as mock_store:

            # Setup mocks - validation succeeds but with warnings
            mock_extract.return_value = sample_payment_plan
            mock_validate.return_value = Mock(
                status=ValidationStatus.NEEDS_REVIEW,
                is_valid=True,
                is_auto_approvable=False,
                errors=[],
                warnings=[
                    Mock(field="duration_weeks", message="Short payment plan", severity="warning", rule_code="SHORT_DURATION")
                ],
                info=[],
                validation_summary="Payment plan requires review due to 1 warning(s)"
            )
            mock_workflow.return_value = uuid4()
            mock_store.return_value = uuid4()

            # Make request
            response = client.post("/orchestrate/payment-plan-detected", json=sample_request_data)

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["payment_plan"] is not None
            assert data["validation"] is not None
            assert data["validation"]["status"] == "needs_review"
            assert data["validation"]["is_valid"] is True
            assert data["validation"]["is_auto_approvable"] is False
            assert len(data["validation"]["warnings"]) == 1

    def test_payment_plan_detected_invalid_request_data(self, client):
        """Test payment plan detection with invalid request data"""
        invalid_data = {
            "conversation_id": "invalid-uuid",  # Invalid UUID format
            "tenant_id": "",  # Empty tenant ID
            "message_content": ""  # Empty message content
        }

        response = client.post("/orchestrate/payment-plan-detected", json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_payment_plan_detected_missing_required_fields(self, client):
        """Test payment plan detection with missing required fields"""
        incomplete_data = {
            "conversation_id": str(uuid4())
            # Missing tenant_id and message_content
        }

        response = client.post("/orchestrate/payment-plan-detected", json=incomplete_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_payment_plan_detected_database_error(self, client, sample_request_data, sample_payment_plan):
        """Test payment plan detection with database error"""
        with patch('app.api.payment_plan.payment_extractor.extract_payment_plan') as mock_extract, \
             patch('app.api.payment_plan.payment_validator.validate_payment_plan') as mock_validate, \
             patch('app.api.payment_plan._get_or_create_workflow') as mock_workflow:

            # Setup mocks - workflow creation fails
            mock_extract.return_value = sample_payment_plan
            mock_validate.return_value = Mock(
                status=ValidationStatus.VALID,
                is_valid=True,
                is_auto_approvable=False,
                errors=[],
                warnings=[],
                info=[],
                validation_summary="Payment plan is valid"
            )
            mock_workflow.side_effect = Exception("Database connection failed")

            # Make request
            response = client.post("/orchestrate/payment-plan-detected", json=sample_request_data)

            # Should return 500 due to internal error
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_payment_plans_by_conversation(self, client):
        """Test getting payment plans by conversation ID"""
        conversation_id = str(uuid4())

        with patch('app.api.payment_plan.PaymentPlanAttempt.get_by_conversation_id') as mock_get, \
             patch('app.api.payment_plan.PaymentPlanAttempt.count_by_conversation_id') as mock_count:

            # Setup mocks
            mock_get.return_value = [
                {
                    "id": str(uuid4()),
                    "workflow_id": str(uuid4()),
                    "weekly_amount": 100.0,
                    "duration_weeks": 8,
                    "start_date": (datetime.now() + timedelta(days=7)).isoformat(),
                    "status": "auto_approved",
                    "extracted_from": "tenant_message",
                    "confidence_score": 0.9,
                    "created_at": datetime.now().isoformat(),
                    "validation_result": {"is_auto_approvable": True}
                }
            ]
            mock_count.return_value = 1

            # Make request
            response = client.get(f"/orchestrate/payment-plans/{conversation_id}")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_count"] == 1
            assert len(data["payment_plans"]) == 1
            assert data["payment_plans"][0]["weekly_amount"] == 100.0
            assert data["payment_plans"][0]["duration_weeks"] == 8

    def test_get_payment_plan_details_success(self, client):
        """Test getting payment plan details successfully"""
        payment_plan_id = str(uuid4())

        with patch('app.api.payment_plan.PaymentPlanAttempt.get_by_id') as mock_get:
            # Setup mock
            mock_get.return_value = {
                "id": payment_plan_id,
                "workflow_id": str(uuid4()),
                "weekly_amount": 150.0,
                "duration_weeks": 6,
                "start_date": (datetime.now() + timedelta(days=7)).isoformat(),
                "status": "auto_approved",
                "extracted_from": "ai_response",
                "confidence_score": 0.95,
                "created_at": datetime.now().isoformat(),
                "validation_result": {
                    "status": "auto_approved",
                    "is_valid": True,
                    "is_auto_approvable": True,
                    "errors": [],
                    "warnings": [],
                    "validation_summary": "Payment plan is valid and eligible for auto-approval"
                },
                "extraction_patterns": ["ai_structured: pattern"]
            }

            # Make request
            response = client.get(f"/orchestrate/payment-plans/{payment_plan_id}")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["payment_plan_id"] == payment_plan_id
            assert data["payment_plan"]["weekly_amount"] == 150.0
            assert data["payment_plan"]["duration_weeks"] == 6
            assert data["validation"]["status"] == "auto_approved"
            assert data["validation"]["is_auto_approvable"] is True

    def test_get_payment_plan_details_not_found(self, client):
        """Test getting payment plan details for non-existent plan"""
        payment_plan_id = str(uuid4())

        with patch('app.api.payment_plan.PaymentPlanAttempt.get_by_id') as mock_get:
            # Setup mock - payment plan not found
            mock_get.return_value = None

            # Make request
            response = client.get(f"/orchestrate/payment-plans/{payment_plan_id}")

            # Assertions
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_payment_plans_with_pagination(self, client):
        """Test getting payment plans with pagination parameters"""
        conversation_id = str(uuid4())

        with patch('app.api.payment_plan.PaymentPlanAttempt.get_by_conversation_id') as mock_get, \
             patch('app.api.payment_plan.PaymentPlanAttempt.count_by_conversation_id') as mock_count:

            # Setup mocks
            mock_get.return_value = []  # Empty list for simplicity
            mock_count.return_value = 0

            # Make request with pagination
            response = client.get(f"/orchestrate/payment-plans/{conversation_id}?limit=5&offset=10")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["limit"] == 5
            assert data["offset"] == 10
            assert data["total_count"] == 0

            # Verify mock was called with correct parameters
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            assert len(args) == 2  # supabase, conversation_id
            assert kwargs.get('limit') == 5
            assert kwargs.get('offset') == 10

    def test_payment_plan_detected_extracts_from_ai_response_fallback(self, client, sample_request_data):
        """Test that AI response is used for extraction when tenant message extraction fails"""
        with patch('app.api.payment_plan.payment_extractor.extract_payment_plan') as mock_extract, \
             patch('app.api.payment_plan.payment_extractor.extract_from_ai_response') as mock_extract_ai, \
             patch('app.api.payment_plan.payment_validator.validate_payment_plan') as mock_validate, \
             patch('app.api.payment_plan._get_or_create_workflow') as mock_workflow, \
             patch('app.api.payment_plan._store_payment_plan_attempt') as mock_store:

            # Setup mocks - tenant extraction fails, AI extraction succeeds
            mock_extract.return_value = None
            ai_payment_plan = ExtractedPaymentPlan(
                weekly_amount=Decimal('120'),
                duration_weeks=6,
                start_date=None,
                confidence_score=0.95,
                extracted_from="ai_response",
                original_text=sample_request_data["ai_response"],
                extraction_patterns=["ai_structured: pattern"]
            )
            mock_extract_ai.return_value = ai_payment_plan
            mock_validate.return_value = Mock(
                status=ValidationStatus.AUTO_APPROVED,
                is_valid=True,
                is_auto_approvable=True,
                errors=[],
                warnings=[],
                info=[],
                validation_summary="Payment plan is valid and eligible for auto-approval"
            )
            mock_workflow.return_value = uuid4()
            mock_store.return_value = uuid4()

            # Make request
            response = client.post("/orchestrate/payment-plan-detected", json=sample_request_data)

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["payment_plan"]["weekly_amount"] == 120.0
            assert data["payment_plan"]["duration_weeks"] == 6
            assert data["payment_plan"]["extracted_from"] == "ai_response"

            # Verify both extraction methods were tried
            mock_extract.assert_called_once()
            mock_extract_ai.assert_called_once()

    @pytest.mark.parametrize("message_content,ai_response,should_extract", [
        ("I can pay $100 per week for 8 weeks.", None, True),  # Valid in tenant message
        ("No payment plan mentioned", "PAYMENT_PLAN: weekly=150, weeks=6", True),  # Valid in AI response
        ("Just a regular message", "No payment plan here either", False),  # No payment plan
        ("", "", False),  # Empty messages
    ])
    def test_payment_plan_detection_scenarios(self, client, sample_request_data, message_content, ai_response, should_extract):
        """Test various payment plan detection scenarios"""
        # Update request data
        sample_request_data["message_content"] = message_content
        if ai_response is not None:
            sample_request_data["ai_response"] = ai_response
        else:
            sample_request_data.pop("ai_response", None)

        with patch('app.api.payment_plan.payment_extractor.extract_payment_plan') as mock_extract, \
             patch('app.api.payment_plan.payment_extractor.extract_from_ai_response') as mock_extract_ai, \
             patch('app.api.payment_plan.payment_validator.validate_payment_plan') as mock_validate, \
             patch('app.api.payment_plan._get_or_create_workflow') as mock_workflow, \
             patch('app.api.payment_plan._store_payment_plan_attempt') as mock_store:

            # Setup mocks based on scenario
            if should_extract:
                mock_extract.return_value = ExtractedPaymentPlan(
                    weekly_amount=Decimal('100'),
                    duration_weeks=8,
                    start_date=None,
                    confidence_score=0.8,
                    extracted_from="tenant_message",
                    original_text=message_content,
                    extraction_patterns=["pattern"]
                ) if message_content and "payment plan" in message_content.lower() else None

                if ai_response and "PAYMENT_PLAN:" in ai_response:
                    mock_extract_ai.return_value = ExtractedPaymentPlan(
                        weekly_amount=Decimal('150'),
                        duration_weeks=6,
                        start_date=None,
                        confidence_score=0.95,
                        extracted_from="ai_response",
                        original_text=ai_response,
                        extraction_patterns=["ai_structured"]
                    )

                mock_validate.return_value = Mock(
                    status=ValidationStatus.VALID,
                    is_valid=True,
                    is_auto_approvable=False,
                    errors=[],
                    warnings=[],
                    info=[],
                    validation_summary="Valid payment plan"
                )
                mock_workflow.return_value = uuid4()
                mock_store.return_value = uuid4()
            else:
                mock_extract.return_value = None
                mock_extract_ai.return_value = None

            # Make request
            response = client.post("/orchestrate/payment-plan-detected", json=sample_request_data)

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            if should_extract:
                assert data["success"] is True
                assert data["payment_plan"] is not None
            else:
                assert data["success"] is False
                assert data["payment_plan"] is None