"""
Tests for workflow API endpoints.
"""
import pytest
from uuid import uuid4
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from app.main import app
from app.models.workflow import WorkflowStatus, WorkflowType, StepType, StepStatus
from app.schemas.workflow import WorkflowStatusResponse, WorkflowStepResponse


client = TestClient(app)


@pytest.fixture
def mock_workflow_service():
    """Mock workflow service fixture."""
    with patch('app.api.workflow.workflow_service') as mock:
        yield mock


@pytest.fixture
def sample_workflow_status_response():
    """Sample workflow status response fixture."""
    return WorkflowStatusResponse(
        conversation_id=uuid4(),
        workflow_id=uuid4(),
        status=WorkflowStatus.PROCESSING,
        started_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
        tenant_id="tenant_123",
        phone_number="+1234567890",
        workflow_type=WorkflowType.SMS_PROCESSING,
        current_step="ai_processing",
        steps_completed=2,
        total_steps=5,
        workflow_steps=[
            WorkflowStepResponse(
                id=uuid4(),
                step_name="sms_received",
                step_type=StepType.API_CALL,
                status=StepStatus.COMPLETED,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                duration_ms=150
            )
        ],
        metadata={"ai_confidence": 0.85}
    )


class TestWorkflowStatusEndpoint:
    """Test GET /orchestrate/workflow/{conversation_id}/status endpoint."""

    def test_get_workflow_status_success(self, mock_workflow_service, sample_workflow_status_response):
        """Test successful workflow status retrieval."""
        conversation_id = sample_workflow_status_response.conversation_id

        mock_workflow_service.get_workflow_status = AsyncMock(
            return_value=sample_workflow_status_response
        )

        response = client.get(f"/orchestrate/workflow/{conversation_id}/status")

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["conversation_id"] == str(conversation_id)
        assert response_data["status"] == WorkflowStatus.PROCESSING.value
        assert response_data["tenant_id"] == "tenant_123"
        assert response_data["steps_completed"] == 2
        assert len(response_data["workflow_steps"]) == 1

        mock_workflow_service.get_workflow_status.assert_called_once_with(conversation_id)

    def test_get_workflow_status_not_found(self, mock_workflow_service):
        """Test workflow status retrieval for non-existent conversation."""
        conversation_id = uuid4()

        mock_workflow_service.get_workflow_status = AsyncMock(return_value=None)

        response = client.get(f"/orchestrate/workflow/{conversation_id}/status")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        mock_workflow_service.get_workflow_status.assert_called_once_with(conversation_id)

    def test_get_workflow_status_invalid_uuid(self):
        """Test workflow status retrieval with invalid conversation ID."""
        invalid_conversation_id = "invalid-uuid"

        response = client.get(f"/orchestrate/workflow/{invalid_conversation_id}/status")

        assert response.status_code == 422  # Validation error

    def test_get_workflow_status_server_error(self, mock_workflow_service):
        """Test workflow status retrieval with server error."""
        conversation_id = uuid4()

        mock_workflow_service.get_workflow_status = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        response = client.get(f"/orchestrate/workflow/{conversation_id}/status")

        assert response.status_code == 500
        assert "internal server error" in response.json()["detail"].lower()

        mock_workflow_service.get_workflow_status.assert_called_once_with(conversation_id)

    def test_get_workflow_status_with_various_statuses(self, mock_workflow_service):
        """Test workflow status retrieval with different workflow statuses."""
        conversation_id = uuid4()

        for status in WorkflowStatus:
            workflow_response = WorkflowStatusResponse(
                conversation_id=conversation_id,
                workflow_id=uuid4(),
                status=status,
                started_at=datetime.utcnow(),
                last_updated=datetime.utcnow(),
                tenant_id="tenant_123",
                phone_number="+1234567890",
                workflow_type=WorkflowType.SMS_PROCESSING,
                steps_completed=1,
                total_steps=5,
                workflow_steps=[]
            )

            mock_workflow_service.get_workflow_status = AsyncMock(return_value=workflow_response)

            response = client.get(f"/orchestrate/workflow/{conversation_id}/status")

            assert response.status_code == 200
            assert response.json()["status"] == status.value

    def test_get_workflow_status_with_workflow_steps(self, mock_workflow_service):
        """Test workflow status retrieval with multiple workflow steps."""
        conversation_id = uuid4()

        workflow_steps = [
            WorkflowStepResponse(
                id=uuid4(),
                step_name="sms_received",
                step_type=StepType.API_CALL,
                status=StepStatus.COMPLETED,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                duration_ms=150
            ),
            WorkflowStepResponse(
                id=uuid4(),
                step_name="ai_processing",
                step_type=StepType.AI_PROCESSING,
                status=StepStatus.STARTED,
                started_at=datetime.utcnow(),
                duration_ms=None
            ),
            WorkflowStepResponse(
                id=uuid4(),
                step_name="error_handling",
                step_type=StepType.DATABASE_OPERATION,
                status=StepStatus.FAILED,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                duration_ms=50,
                error_details={"error": "Service timeout"}
            )
        ]

        workflow_response = WorkflowStatusResponse(
            conversation_id=conversation_id,
            workflow_id=uuid4(),
            status=WorkflowStatus.FAILED,
            started_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            tenant_id="tenant_123",
            phone_number="+1234567890",
            workflow_type=WorkflowType.SMS_PROCESSING,
            current_step="ai_processing",
            steps_completed=1,
            total_steps=5,
            workflow_steps=workflow_steps,
            error_message="AI processing failed due to timeout",
            metadata={"failure_reason": "timeout"}
        )

        mock_workflow_service.get_workflow_status = AsyncMock(return_value=workflow_response)

        response = client.get(f"/orchestrate/workflow/{conversation_id}/status")

        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["workflow_steps"]) == 3
        assert response_data["workflow_steps"][0]["status"] == StepStatus.COMPLETED.value
        assert response_data["workflow_steps"][1]["status"] == StepStatus.STARTED.value
        assert response_data["workflow_steps"][2]["status"] == StepStatus.FAILED.value
        assert response_data["error_message"] is not None


class TestWorkflowListEndpoint:
    """Test GET /orchestrate/workflows endpoint."""

    def test_list_workflows_empty(self, mock_workflow_service):
        """Test listing workflows when no workflows exist."""
        response = client.get("/orchestrate/workflows")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_workflows_server_error(self, mock_workflow_service):
        """Test listing workflows with server error."""
        with patch('app.api.workflow.logger') as mock_logger:
            # Simulate logger error during endpoint execution
            mock_logger.error.side_effect = Exception("Logger error")

            response = client.get("/orchestrate/workflows")

            assert response.status_code == 500
            assert "internal server error" in response.json()["detail"].lower()


class TestWorkflowAPILogging:
    """Test workflow API logging behavior."""

    def test_workflow_status_logging(self, mock_workflow_service, sample_workflow_status_response):
        """Test that workflow status endpoint logs appropriately."""
        conversation_id = sample_workflow_status_response.conversation_id

        mock_workflow_service.get_workflow_status = AsyncMock(
            return_value=sample_workflow_status_response
        )

        with patch('app.api.workflow.logger') as mock_logger:
            response = client.get(f"/orchestrate/workflow/{conversation_id}/status")

            assert response.status_code == 200
            mock_logger.info.assert_called()

            # Check that log message contains expected parameters
            log_call_args = mock_logger.info.call_args
            assert "conversation_id" in log_call_args[1]
            assert "workflow_id" in log_call_args[1]
            assert "status" in log_call_args[1]
            assert "steps_completed" in log_call_args[1]

    def test_workflow_status_error_logging(self, mock_workflow_service):
        """Test that workflow status endpoint logs errors appropriately."""
        conversation_id = uuid4()

        mock_workflow_service.get_workflow_status = AsyncMock(
            side_effect=Exception("Database error")
        )

        with patch('app.api.workflow.logger') as mock_logger:
            response = client.get(f"/orchestrate/workflow/{conversation_id}/status")

            assert response.status_code == 500
            mock_logger.error.assert_called()

            # Check that error log contains expected parameters
            log_call_args = mock_logger.error.call_args
            assert conversation_id in log_call_args[0][0]  # Conversation ID in error message