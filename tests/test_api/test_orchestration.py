"""
Tests for the SMS orchestration endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
import uuid
from datetime import datetime


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
