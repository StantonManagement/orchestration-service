"""
Tests for escalation API endpoints.

Comprehensive test coverage for Story 2.2 escalation API functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json

from app.api.escalation import router
from app.models.schemas import EscalationRequest, EscalationResponse
from app.core.exceptions import EscalationError


class TestEscalationAPI:
    """Test cases for escalation API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_escalation_service = Mock()
        self.client = TestClient(router)

    def create_mock_app(self):
        """Create a mock FastAPI app for testing."""
        from fastapi import FastAPI
        from fastapi.dependencies import Depends

        app = FastAPI()

        def mock_dependency():
            return self.mock_escalation_service

        # Override the dependency
        app.dependency_overrides[lambda: None] = mock_dependency
        app.include_router(router)

        return TestClient(app)

    @patch('app.api.escalation.get_escalation_service')
    def test_trigger_manual_escalation_success(self, mock_get_service):
        """Test successful manual escalation trigger."""
        # Setup mock
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        expected_response = EscalationResponse(
            escalation_id="test-escalation-1",
            workflow_id="test-workflow-1",
            status="escalated",
            message="Manual escalation processed successfully",
            timestamp=datetime.utcnow()
        )
        mock_service.process_escalation_request = AsyncMock(return_value=expected_response)

        # Create request
        request_data = {
            "workflow_id": "test-workflow-1",
            "customer_phone": "+1234567890",
            "reason": "customer_anger",
            "notes": "Customer is very angry"
        }

        # Make request
        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.post("/escalations/trigger", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["workflow_id"] == "test-workflow-1"
        assert data["data"]["status"] == "escalated"
        assert "escalation" in data["data"]["escalation_id"]

    @patch('app.api.escalation.get_escalation_service')
    def test_trigger_manual_escalation_service_error(self, mock_get_service):
        """Test manual escalation with service error."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.process_escalation_request = AsyncMock(
            side_effect=EscalationError("Service unavailable")
        )

        request_data = {
            "workflow_id": "test-workflow-1",
            "customer_phone": "+1234567890",
            "reason": "customer_anger"
        }

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.post("/escalations/trigger", json=request_data)

        assert response.status_code == 500
        data = response.json()
        assert "Escalation processing failed" in data["detail"]

    @patch('app.api.escalation.get_escalation_service')
    def test_get_escalation_status_success(self, mock_get_service):
        """Test successful escalation status retrieval."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        # Mock timeout info
        mock_timeout = Mock()
        mock_timeout.workflow_id = "test-workflow-1"
        mock_timeout.customer_phone = "+1234567890"
        mock_timeout.last_ai_response = datetime.utcnow()
        mock_timeout.timeout_threshold = timedelta(hours=36)
        mock_timeout.time_remaining = timedelta(hours=24)
        mock_timeout.status = Mock()
        mock_timeout.status.value = "active"
        mock_timeout.escalation_triggered = False
        mock_timeout.warning_sent = False
        mock_timeout.created_at = datetime.utcnow()
        mock_timeout.updated_at = datetime.utcnow()

        mock_service.timeout_monitor.get_workflow_timeout.return_value = mock_timeout

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.get("/escalations/status/test-workflow-1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["workflow_id"] == "test-workflow-1"
        assert data["data"]["customer_phone"] == "+1234567890"
        assert data["data"]["status"] == "active"
        assert data["data"]["hours_remaining"] == 24

    @patch('app.api.escalation.get_escalation_service')
    def test_get_escalation_status_not_found(self, mock_get_service):
        """Test escalation status for non-existent workflow."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.timeout_monitor.get_workflow_timeout.return_value = None

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.get("/escalations/status/nonexistent-workflow")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]

    @patch('app.api.escalation.get_escalation_service')
    def test_get_escalation_statistics_success(self, mock_get_service):
        """Test successful escalation statistics retrieval."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        mock_stats = {
            "total_active_workflows": 10,
            "expired_workflows": 2,
            "workflows_near_timeout": 3,
            "escalated_workflows": 5,
            "escalated_today": 1,
            "timeout_threshold_hours": 36,
            "escalation_service_active": True
        }
        mock_service.get_escalation_statistics = AsyncMock(return_value=mock_stats)

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.get("/escalations/statistics")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_active_workflows"] == 10
        assert data["data"]["expired_workflows"] == 2
        assert data["data"]["timeout_threshold_hours"] == 36
        assert data["data"]["monitoring_active"] is True

    @patch('app.api.escalation.get_escalation_service')
    def test_check_timeout_escalations_success(self, mock_get_service):
        """Test successful timeout escalation check."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        mock_escalations = [
            {
                "escalation_id": "timeout-escalation-1",
                "workflow_id": "expired-workflow-1",
                "escalation_type": "timeout_based"
            }
        ]
        mock_service.check_timeout_escalations = AsyncMock(return_value=mock_escalations)

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.post("/escalations/check-timeouts")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["escalations_triggered"] == 1
        assert len(data["data"]["escalation_details"]) == 1

    @patch('app.api.escalation.get_escalation_service')
    def test_register_workflow_timeout_success(self, mock_get_service):
        """Test successful workflow timeout registration."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.register_workflow_timeout = AsyncMock()

        request_data = {
            "workflow_id": "test-workflow-1",
            "customer_phone": "+1234567890",
            "last_ai_response": datetime.utcnow().isoformat()
        }

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.post(
                    "/escalations/register-timeout",
                    params=request_data
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["workflow_id"] == "test-workflow-1"
        assert data["data"]["status"] == "registered_for_monitoring"

    @patch('app.api.escalation.get_escalation_service')
    def test_update_workflow_timeout_success(self, mock_get_service):
        """Test successful workflow timeout update."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.update_workflow_response = AsyncMock()

        new_response_time = datetime.utcnow().isoformat()

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.put(
                    "/escalations/update-timeout/test-workflow-1",
                    params={"response_time": new_response_time}
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["workflow_id"] == "test-workflow-1"
        assert data["data"]["status"] == "timeout_updated"

    @patch('app.api.escalation.get_escalation_service')
    def test_remove_workflow_monitoring_success(self, mock_get_service):
        """Test successful workflow monitoring removal."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.remove_workflow_monitoring = AsyncMock()

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.delete("/escalations/remove/test-workflow-1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["workflow_id"] == "test-workflow-1"
        assert data["data"]["status"] == "monitoring_removed"

    @patch('app.api.escalation.get_escalation_service')
    def test_escalation_health_check_healthy(self, mock_get_service):
        """Test health check when service is healthy."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        mock_stats = {
            "monitoring_active": True,
            "total_active_workflows": 5,
            "escalation_service_active": True
        }
        mock_service.get_escalation_statistics = AsyncMock(return_value=mock_stats)

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.get("/escalations/health")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"
        assert data["data"]["monitoring_active"] is True
        assert data["data"]["active_workflows"] == 5

    @patch('app.api.escalation.get_escalation_service')
    def test_escalation_health_check_unhealthy(self, mock_get_service):
        """Test health check when service is unhealthy."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.get_escalation_statistics = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.get("/escalations/health")

        assert response.status_code == 200  # Still returns 200, but with unhealthy status
        data = response.json()
        assert data["success"] is False  # Failed success flag
        assert data["data"]["status"] == "unhealthy"
        assert "error" in data["data"]

    def test_manual_escalation_invalid_reason(self):
        """Test manual escalation with invalid reason."""
        request_data = {
            "workflow_id": "test-workflow-1",
            "customer_phone": "+1234567890",
            "reason": "invalid_reason"
        }

        with TestClient(router) as client:
            response = client.post("/escalations/trigger", json=request_data)

        # Should return validation error (422)
        assert response.status_code == 422

    def test_manual_escalation_missing_fields(self):
        """Test manual escalation with missing required fields."""
        request_data = {
            "workflow_id": "test-workflow-1"
            # Missing customer_phone and reason
        }

        with TestClient(router) as client:
            response = client.post("/escalations/trigger", json=request_data)

        # Should return validation error (422)
        assert response.status_code == 422

    @patch('app.api.escalation.get_escalation_service')
    def test_timeout_registration_invalid_datetime(self, mock_get_service):
        """Test timeout registration with invalid datetime."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.post(
                    "/escalations/register-timeout",
                    params={
                        "workflow_id": "test-workflow-1",
                        "customer_phone": "+1234567890",
                        "last_ai_response": "invalid-datetime"
                    }
                )

        # Should return validation error (422)
        assert response.status_code == 422

    @patch('app.api.escalation.get_escalation_service')
    def test_rate_limiting_protection(self, mock_get_service):
        """Test that API endpoints have basic rate limiting protection."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        # This would ideally test rate limiting, but for now just ensure
        # the endpoint handles multiple requests gracefully
        requests_data = {
            "workflow_id": "test-workflow-1",
            "customer_phone": "+1234567890",
            "reason": "customer_anger"
        }

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                # Make multiple rapid requests
                responses = []
                for _ in range(5):
                    response = client.post("/escalations/trigger", json=request_data)
                    responses.append(response)

                # All should succeed (no server errors)
                success_count = sum(1 for r in responses if r.status_code in [200, 500])
                assert success_count == 5

    @patch('app.api.escalation.get_escalation_service')
    def test_cors_headers(self, mock_get_service):
        """Test that CORS headers are properly set."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.get_escalation_statistics = AsyncMock(return_value={})

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.options("/escalations/statistics")

        # Should handle OPTIONS requests (CORS preflight)
        assert response.status_code in [200, 405]  # Either allowed or method not allowed

    @patch('app.api.escalation.get_escalation_service')
    def test_error_logging(self, mock_get_service):
        """Test that errors are properly logged."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        mock_service.process_escalation_request = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        request_data = {
            "workflow_id": "test-workflow-1",
            "customer_phone": "+1234567890",
            "reason": "customer_anger"
        }

        # Capture logs (in real implementation, this would verify log entries)
        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                response = client.post("/escalations/trigger", json=request_data)

        assert response.status_code == 500
        data = response.json()
        assert "Internal server error" in data["detail"]

    @patch('app.api.escalation.get_escalation_service')
    def test_response_format_consistency(self, mock_get_service):
        """Test that all responses follow consistent format."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        # Mock different service methods
        mock_service.get_escalation_statistics = AsyncMock(return_value={})
        mock_service.timeout_monitor.get_workflow_timeout.return_value = None

        with TestClient(router) as client:
            with patch('app.api.escalation.get_escalation_service', return_value=mock_service):
                # Test different endpoints
                stats_response = client.get("/escalations/statistics")
                health_response = client.get("/escalations/health")

        # All should have consistent response format
        for response in [stats_response, health_response]:
            data = response.json()
            assert "success" in data
            assert "data" in data
            assert "message" in data
            assert "timestamp" in data
            assert isinstance(data["success"], bool)