"""
Tests for the approval workflow API endpoints.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.models.ai_response import AIResponseQueue
from app.api.approval import get_approval_service


class TestApprovalAPI:
    """Test cases for approval API endpoints."""

    @pytest.fixture
    def mock_approval_service(self):
        """Create mock approval service."""
        mock_service = MagicMock()
        mock_service.get_queue_entry.return_value = None
        mock_service.process_approval_action = AsyncMock(return_value=True)
        mock_service.get_pending_approvals = AsyncMock(return_value=[])
        mock_service.get_audit_logs.return_value = []
        mock_service.check_approval_timeouts = AsyncMock(return_value=[])
        return mock_service

    @pytest.fixture
    def client(self, mock_approval_service):
        """Create test client with mocked dependencies."""
        app.dependency_overrides[get_approval_service] = lambda: mock_approval_service
        with TestClient(app) as client:
            yield client
        app.dependency_overrides.clear()

    @pytest.fixture
    def sample_queue_id(self):
        """Create sample queue ID."""
        return uuid4()

    @pytest.fixture
    def sample_queue_entry(self, sample_queue_id):
        """Create sample queue entry."""
        return AIResponseQueue(
            id=sample_queue_id,
            workflow_id=uuid4(),
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="I need help with payment",
            ai_response="Thank you for your message. We can help arrange a payment plan.",
            confidence_score=Decimal("0.75"),
            status="pending",
            created_at=datetime.utcnow(),
        )

    def test_approve_response_success_approve(
        self, client, sample_queue_id, mock_approval_service
    ):
        """Test successful approval action - approve."""
        request_data = {
            "response_queue_id": str(sample_queue_id),
            "action": "approve",
            "manager_id": "manager_456",
        }

        # Configure the mock service
        mock_approval_service.get_queue_entry.return_value = AIResponseQueue(
            id=sample_queue_id,
            workflow_id=uuid4(),
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test",
            ai_response="Test response",
            confidence_score=Decimal("0.75"),
            status="pending",
        )

        response = client.post(
            "/api/v1/orchestrate/approve-response", json=request_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "approve"
        assert str(data["queue_id"]) == str(sample_queue_id)

        mock_approval_service.process_approval_action.assert_called_once_with(
            queue_id=sample_queue_id,
            action="approve",
            manager_id="manager_456",
            modified_text=None,
            escalation_reason=None,
        )

    def test_approve_response_success_modify(
        self, client, sample_queue_id, mock_approval_service
    ):
        """Test successful approval action - modify."""
        request_data = {
            "response_queue_id": str(sample_queue_id),
            "action": "modify",
            "manager_id": "manager_456",
            "modified_text": "Modified response text",
        }

        # Configure the mock service
        mock_approval_service.get_queue_entry.return_value = AIResponseQueue(
            id=sample_queue_id,
            workflow_id=uuid4(),
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test",
            ai_response="Test response",
            confidence_score=Decimal("0.75"),
            status="pending",
        )

        response = client.post(
            "/api/v1/orchestrate/approve-response", json=request_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "modify"
        assert data["final_response"] == "Modified response text"

        mock_approval_service.process_approval_action.assert_called_once_with(
            queue_id=sample_queue_id,
            action="modify",
            manager_id="manager_456",
            modified_text="Modified response text",
            escalation_reason=None,
        )

    def test_approve_response_success_escalate(
        self, client, sample_queue_id, mock_approval_service
    ):
        """Test successful approval action - escalate."""
        request_data = {
            "response_queue_id": str(sample_queue_id),
            "action": "escalate",
            "manager_id": "manager_456",
            "escalation_reason": "Tenant disputes amount owed",
        }

        # Configure the mock service
        mock_approval_service.get_queue_entry.return_value = AIResponseQueue(
            id=sample_queue_id,
            workflow_id=uuid4(),
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test",
            ai_response="Test response",
            confidence_score=Decimal("0.75"),
            status="pending",
        )

        response = client.post(
            "/api/v1/orchestrate/approve-response", json=request_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "escalate"
        assert data["final_response"] == "Test response"

        mock_approval_service.process_approval_action.assert_called_once_with(
            queue_id=sample_queue_id,
            action="escalate",
            manager_id="manager_456",
            modified_text=None,
            escalation_reason="Tenant disputes amount owed",
        )

    def test_approve_response_invalid_action(self, client, sample_queue_id):
        """Test approval action with invalid action."""
        request_data = {
            "response_queue_id": str(sample_queue_id),
            "action": "invalid_action",
            "manager_id": "manager_456",
        }

        response = client.post(
            "/api/v1/orchestrate/approve-response", json=request_data
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Invalid action" in data["detail"]["error"]
        assert data["detail"]["error_code"] == "INVALID_ACTION"

    def test_approve_response_missing_modified_text(self, client, sample_queue_id):
        """Test modify action without required modified text."""
        request_data = {
            "response_queue_id": str(sample_queue_id),
            "action": "modify",
            "manager_id": "manager_456",
        }

        response = client.post(
            "/api/v1/orchestrate/approve-response", json=request_data
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "modified_text is required" in data["detail"]["error"]
        assert data["detail"]["error_code"] == "MISSING_MODIFIED_TEXT"

    def test_approve_response_queue_not_found(
        self, client, sample_queue_id, mock_approval_service
    ):
        """Test approval action with non-existent queue ID."""
        request_data = {
            "response_queue_id": str(sample_queue_id),
            "action": "approve",
            "manager_id": "manager_456",
        }

        # Configure mock to return None (not found)
        mock_approval_service.get_queue_entry.return_value = None

        response = client.post(
            "/api/v1/orchestrate/approve-response", json=request_data
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"]["error"]
        assert data["detail"]["error_code"] == "QUEUE_ENTRY_NOT_FOUND"

    def test_approve_response_processing_failed(
        self, client, sample_queue_id, mock_approval_service
    ):
        """Test approval action when processing fails."""
        request_data = {
            "response_queue_id": str(sample_queue_id),
            "action": "approve",
            "manager_id": "manager_456",
        }

        # Configure mock service
        mock_approval_service.get_queue_entry.return_value = AIResponseQueue(
            id=sample_queue_id,
            workflow_id=uuid4(),
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test",
            ai_response="Test response",
            confidence_score=Decimal("0.75"),
            status="pending",
        )
        mock_approval_service.process_approval_action.return_value = False

        response = client.post(
            "/api/v1/orchestrate/approve-response", json=request_data
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Failed to process" in data["detail"]["error"]
        assert data["detail"]["error_code"] == "ACTION_PROCESSING_FAILED"

    def test_approve_response_invalid_uuid(self, client):
        """Test approval action with invalid UUID format."""
        request_data = {
            "response_queue_id": "invalid-uuid",
            "action": "approve",
            "manager_id": "manager_456",
        }

        response = client.post(
            "/api/v1/orchestrate/approve-response", json=request_data
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_pending_approvals_success(
        self, client, sample_queue_entry, mock_approval_service
    ):
        """Test successful retrieval of pending approvals."""
        mock_approval_service.get_pending_approvals.return_value = [sample_queue_entry]

        response = client.get("/api/v1/orchestrate/pending-approvals")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["pending_approvals"]) == 1
        assert data["pending_approvals"][0]["id"] == str(sample_queue_entry.id)
        assert data["pending_approvals"][0]["tenant_id"] == sample_queue_entry.tenant_id
        assert "waiting_time_hours" in data["pending_approvals"][0]

    def test_get_pending_approvals_empty(self, client):
        """Test retrieval when no pending approvals exist."""
        response = client.get("/api/v1/orchestrate/pending-approvals")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 0
        assert len(data["pending_approvals"]) == 0

    def test_get_pending_approvals_service_error(self, client, mock_approval_service):
        """Test pending approvals retrieval when service fails."""
        mock_approval_service.get_pending_approvals.side_effect = Exception(
            "Database error"
        )

        response = client.get("/api/v1/orchestrate/pending-approvals")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert data["detail"]["error_code"] == "RETRIEVAL_ERROR"

    def test_get_audit_logs_success(
        self, client, sample_queue_id, mock_approval_service
    ):
        """Test successful retrieval of audit logs."""
        from app.models.ai_response import ApprovalAuditLog

        audit_log = ApprovalAuditLog(
            response_queue_id=sample_queue_id,
            action="approve",
            original_response="Original response",
            final_response="Final response",
            approved_by="manager_123",
        )

        mock_approval_service.get_audit_logs.return_value = [audit_log]

        response = client.get("/api/v1/orchestrate/audit-logs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["audit_logs"]) == 1
        assert data["audit_logs"][0]["response_queue_id"] == str(sample_queue_id)
        assert data["audit_logs"][0]["action"] == "approve"
        assert data["audit_logs"][0]["approved_by"] == "manager_123"

    def test_get_audit_logs_with_queue_filter(
        self, client, sample_queue_id, mock_approval_service
    ):
        """Test retrieval of audit logs filtered by queue ID."""
        mock_approval_service.get_audit_logs.return_value = []

        response = client.get(
            f"/api/v1/orchestrate/audit-logs?queue_id={sample_queue_id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 0

        mock_approval_service.get_audit_logs.assert_called_once_with(sample_queue_id)

    def test_get_audit_logs_invalid_uuid(self, client):
        """Test audit logs retrieval with invalid UUID format."""
        response = client.get("/api/v1/orchestrate/audit-logs?queue_id=invalid-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_check_approval_timeouts_success(
        self, client, sample_queue_entry, mock_approval_service
    ):
        """Test successful approval timeout check."""
        mock_approval_service.check_approval_timeouts.return_value = [
            sample_queue_entry
        ]

        response = client.post("/api/v1/orchestrate/check-timeouts")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["pending_approvals"]) == 1
        assert data["pending_approvals"][0]["id"] == str(sample_queue_entry.id)

    def test_check_approval_timeouts_no_timeouts(self, client):
        """Test timeout check when no entries have timed out."""
        response = client.post("/api/v1/orchestrate/check-timeouts")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 0
        assert len(data["pending_approvals"]) == 0

    def test_check_approval_timeouts_service_error(self, client, mock_approval_service):
        """Test timeout check when service fails."""
        mock_approval_service.check_approval_timeouts.side_effect = Exception(
            "Service error"
        )

        response = client.post("/api/v1/orchestrate/check-timeouts")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert data["detail"]["error_code"] == "TIMEOUT_CHECK_ERROR"

    def test_approve_response_missing_required_fields(self, client):
        """Test approval action with missing required fields."""
        request_data = {
            "action": "approve"
            # Missing response_queue_id and manager_id
        }

        response = client.post(
            "/api/v1/orchestrate/approve-response", json=request_data
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
