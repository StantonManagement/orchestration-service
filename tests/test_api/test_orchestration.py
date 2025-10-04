"""
Tests for the SMS orchestration endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
import uuid
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from app.models.schemas import EscalationRequest, RetryRequest
from app.services.escalation_service import EscalationService


class TestReceiveSMSEndpoint:
    """Test cases for the SMS reception endpoint."""

    def test_receive_sms_success(
        self,
        client: TestClient,
        api_prefix: str,
        sample_sms_data: dict,
        sample_headers: dict,
    ):
        """Test successful SMS reception with valid data."""
        response = client.post(
            f"{api_prefix}/orchestrate/sms-received",
            json=sample_sms_data,
            headers=sample_headers,
        )

        assert response.status_code == 201
        data = response.json()

        # Check response structure
        assert data["status"] == "processed"
        assert data["conversation_id"] == sample_sms_data["conversation_id"]
        assert "workflow_id" in data
        assert "timestamp" in data

        # Check workflow ID format
        workflow_id = data["workflow_id"]
        assert workflow_id.startswith("workflow-")
        # Should be a valid UUID after the prefix
        uuid_part = workflow_id[9:]  # Remove "workflow-" prefix
        assert len(uuid_part) == 36  # Standard UUID string length

    def test_receive_sms_without_correlation_id(
        self, client: TestClient, api_prefix: str, sample_sms_data: dict
    ):
        """Test SMS reception without correlation ID header."""
        headers = {"Content-Type": "application/json"}
        response = client.post(
            f"{api_prefix}/orchestrate/sms-received",
            json=sample_sms_data,
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "processed"

    @pytest.mark.asyncio
    async def test_receive_sms_async(
        self, async_client: AsyncClient, api_prefix: str, sample_sms_data: dict
    ):
        """Test SMS reception with async client."""
        response = await async_client.post(
            f"{api_prefix}/orchestrate/sms-received", json=sample_sms_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "processed"
        assert data["conversation_id"] == sample_sms_data["conversation_id"]

    def test_receive_sms_validation_errors(
        self,
        client: TestClient,
        api_prefix: str,
        sample_invalid_sms_data: dict,
        sample_headers: dict,
    ):
        """Test SMS reception with invalid data."""
        response = client.post(
            f"{api_prefix}/orchestrate/sms-received",
            json=sample_invalid_sms_data,
            headers=sample_headers,
        )

        assert response.status_code == 422
        data = response.json()

        # Should have validation error details
        assert "detail" in data
        assert isinstance(data["detail"], list)

        # Check that specific validation errors are present
        error_fields = [error.get("loc", [])[-1] for error in data["detail"]]

        # Should have errors for the invalid fields
        assert "tenant_id" in error_fields
        assert "phone_number" in error_fields
        assert "content" in error_fields
        assert "conversation_id" in error_fields

    def test_receive_sms_missing_required_fields(
        self, client: TestClient, api_prefix: str, sample_headers: dict
    ):
        """Test SMS reception with missing required fields."""
        incomplete_data = {
            "tenant_id": "12345"
            # Missing phone_number, content, conversation_id
        }

        response = client.post(
            f"{api_prefix}/orchestrate/sms-received",
            json=incomplete_data,
            headers=sample_headers,
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_receive_sms_invalid_phone_number(
        self,
        client: TestClient,
        api_prefix: str,
        sample_sms_data: dict,
        sample_headers: dict,
    ):
        """Test SMS reception with invalid phone number."""
        invalid_data = sample_sms_data.copy()
        invalid_data["phone_number"] = "invalid-phone"

        response = client.post(
            f"{api_prefix}/orchestrate/sms-received",
            json=invalid_data,
            headers=sample_headers,
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_receive_sms_invalid_conversation_id_format(
        self,
        client: TestClient,
        api_prefix: str,
        sample_sms_data: dict,
        sample_headers: dict,
    ):
        """Test SMS reception with invalid conversation ID format."""
        invalid_data = sample_sms_data.copy()
        invalid_data["conversation_id"] = "a"  # Too short and not valid

        response = client.post(
            f"{api_prefix}/orchestrate/sms-received",
            json=invalid_data,
            headers=sample_headers,
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_receive_sms_valid_uuid_conversation_id(
        self,
        client: TestClient,
        api_prefix: str,
        sample_sms_data: dict,
        sample_headers: dict,
    ):
        """Test SMS reception with valid UUID conversation ID."""
        valid_uuid = str(uuid.uuid4())
        valid_data = sample_sms_data.copy()
        valid_data["conversation_id"] = valid_uuid

        response = client.post(
            f"{api_prefix}/orchestrate/sms-received",
            json=valid_data,
            headers=sample_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["conversation_id"] == valid_uuid

    def test_receive_sms_different_phone_formats(
        self,
        client: TestClient,
        api_prefix: str,
        sample_sms_data: dict,
        sample_headers: dict,
    ):
        """Test SMS reception with different valid phone number formats."""
        valid_phone_numbers = [
            "+1234567890",
            "+1-234-567-8901",
            "+1 (234) 567-8901",
            "+44 20 7123 4567",
        ]

        for phone_number in valid_phone_numbers:
            test_data = sample_sms_data.copy()
            test_data["phone_number"] = phone_number
            test_data[
                "conversation_id"
            ] = f"test-{uuid.uuid4()}"  # Unique conversation ID

            response = client.post(
                f"{api_prefix}/orchestrate/sms-received",
                json=test_data,
                headers=sample_headers,
            )

            assert response.status_code == 201
            data = response.json()
            assert data["status"] == "processed"

    def test_receive_sms_empty_request_body(
        self, client: TestClient, api_prefix: str, sample_headers: dict
    ):
        """Test SMS reception with empty request body."""
        response = client.post(
            f"{api_prefix}/orchestrate/sms-received", json={}, headers=sample_headers
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_receive_sms_invalid_json(
        self, client: TestClient, api_prefix: str, sample_headers: dict
    ):
        """Test SMS reception with invalid JSON."""
        response = client.post(
            f"{api_prefix}/orchestrate/sms-received",
            data="invalid json",
            headers=sample_headers,
        )

        assert response.status_code == 422

    def test_receive_sms_response_timestamp_format(
        self,
        client: TestClient,
        api_prefix: str,
        sample_sms_data: dict,
        sample_headers: dict,
    ):
        """Test that response timestamp is in valid ISO format."""
        response = client.post(
            f"{api_prefix}/orchestrate/sms-received",
            json=sample_sms_data,
            headers=sample_headers,
        )

        assert response.status_code == 201
        data = response.json()

        # Should be able to parse the timestamp
        timestamp_str = data["timestamp"]
        parsed_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Should be recent (within last minute)
        now = datetime.utcnow()
        time_diff = now.replace(tzinfo=None) - parsed_timestamp.replace(tzinfo=None)
        assert time_diff.total_seconds() < 60


@pytest.fixture
def mock_escalation_service():
    """Mock escalation service fixture."""
    with patch('app.api.orchestration.get_escalation_service') as mock:
        yield mock


@pytest.fixture
def mock_workflow_service():
    """Mock workflow service fixture."""
    with patch('app.api.orchestration.workflow_service') as mock:
        yield mock


@pytest.fixture
def mock_db_service():
    """Mock database service fixture."""
    with patch('app.api.orchestration.db_service') as mock:
        yield mock


@pytest.fixture
def sample_escalation_request():
    """Sample escalation request fixture."""
    return {
        "conversation_id": str(uuid.uuid4()),
        "workflow_id": str(uuid.uuid4()),
        "escalation_type": "manual",
        "reason": "Customer requested supervisor",
        "severity": "high",
        "escalated_by": "manager_123",
        "customer_phone": "+1234567890",
        "metadata": {"previous_attempts": 2}
    }


@pytest.fixture
def sample_retry_request():
    """Sample retry request fixture."""
    return {
        "reason": "Service temporarily unavailable",
        "force_retry": False,
        "recovery_strategy": "wait_and_retry",
        "notes": "Customer service confirmed issue resolved"
    }


class TestEscalationEndpoint:
    """Test POST /orchestrate/escalate endpoint."""

    def test_escalate_conversation_success(
        self, client: TestClient, mock_escalation_service, sample_escalation_request
    ):
        """Test successful conversation escalation."""
        escalation_service_instance = Mock(spec=EscalationService)
        escalation_service_instance.create_escalation = AsyncMock(return_value=Mock(
            escalation_id=uuid.uuid4(),
            escalated_at=datetime.utcnow()
        ))
        mock_escalation_service.return_value = escalation_service_instance

        response = client.post("/orchestrate/escalate", json=sample_escalation_request)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert "escalation_id" in response_data
        assert response_data["conversation_id"] == sample_escalation_request["conversation_id"]
        assert response_data["status"] == "escalated_processed"
        assert "escalated_at" in response_data

    def test_escalate_conversation_service_error(
        self, client: TestClient, mock_escalation_service, sample_escalation_request
    ):
        """Test escalation with service error."""
        mock_escalation_service.return_value = Mock(spec=EscalationService)
        mock_escalation_service.return_value.create_escalation = AsyncMock(
            side_effect=Exception("Service unavailable")
        )

        response = client.post("/orchestrate/escalate", json=sample_escalation_request)

        assert response.status_code == 500
        assert "Failed to process escalation" in response.json()["detail"]

    def test_escalate_conversation_with_correlation_id(
        self, client: TestClient, mock_escalation_service, sample_escalation_request
    ):
        """Test escalation with correlation ID header."""
        escalation_service_instance = Mock(spec=EscalationService)
        escalation_service_instance.create_escalation = AsyncMock(return_value=Mock(
            escalation_id=uuid.uuid4(),
            escalated_at=datetime.utcnow()
        ))
        mock_escalation_service.return_value = escalation_service_instance

        headers = {"X-Correlation-ID": "test-correlation-123"}
        response = client.post("/orchestrate/escalate", json=sample_escalation_request, headers=headers)

        assert response.status_code == 200


class TestRetryEndpoint:
    """Test POST /orchestrate/retry/{workflow_id} endpoint."""

    def test_retry_workflow_success(
        self, client: TestClient, mock_db_service, mock_workflow_service, sample_retry_request
    ):
        """Test successful workflow retry."""
        workflow_id = str(uuid.uuid4())

        mock_db_service.get_workflow = AsyncMock(return_value={
            "id": workflow_id,
            "status": "failed",
            "conversation_id": str(uuid.uuid4())
        })

        mock_workflow_service.create_workflow_step = AsyncMock(return_value=str(uuid.uuid4()))

        response = client.post(f"/orchestrate/retry/{workflow_id}", json=sample_retry_request)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["workflow_id"] == workflow_id
        assert response_data["status"] == "retry_initiated"
        assert "retry_attempted_at" in response_data
        assert "message" in response_data

    def test_retry_workflow_invalid_uuid(self, client: TestClient, sample_retry_request):
        """Test retry with invalid workflow ID format."""
        response = client.post("/orchestrate/retry/invalid-uuid", json=sample_retry_request)

        assert response.status_code == 400
        assert "Invalid workflow ID format" in response.json()["detail"]

    def test_retry_workflow_not_found(
        self, client: TestClient, mock_db_service, sample_retry_request
    ):
        """Test retry for non-existent workflow."""
        workflow_id = str(uuid.uuid4())
        mock_db_service.get_workflow = AsyncMock(return_value=None)

        response = client.post(f"/orchestrate/retry/{workflow_id}", json=sample_retry_request)

        assert response.status_code == 404
        assert "Workflow not found" in response.json()["detail"]

    def test_retry_workflow_wrong_status(
        self, client: TestClient, mock_db_service, sample_retry_request
    ):
        """Test retry for workflow in non-retryable status."""
        workflow_id = str(uuid.uuid4())
        mock_db_service.get_workflow = AsyncMock(return_value={
            "id": workflow_id,
            "status": "completed",
            "conversation_id": str(uuid.uuid4())
        })

        response = client.post(f"/orchestrate/retry/{workflow_id}", json=sample_retry_request)

        assert response.status_code == 400
        assert "Cannot retry workflow in status: completed" in response.json()["detail"]

    def test_retry_workflow_force_retry(
        self, client: TestClient, mock_db_service, mock_workflow_service, sample_retry_request
    ):
        """Test force retry for workflow in non-retryable status."""
        sample_retry_request["force_retry"] = True
        workflow_id = str(uuid.uuid4())

        mock_db_service.get_workflow = AsyncMock(return_value={
            "id": workflow_id,
            "status": "completed",  # Normally not retryable
            "conversation_id": str(uuid.uuid4())
        })

        mock_db_service.update_workflow_status = AsyncMock(return_value=None)
        mock_workflow_service.create_workflow_step = AsyncMock(return_value=str(uuid.uuid4()))

        response = client.post(f"/orchestrate/retry/{workflow_id}", json=sample_retry_request)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
