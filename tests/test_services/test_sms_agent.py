"""
Tests for SMS Agent service client.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from app.services.sms_agent import SMSAgentClient
from app.core.exceptions import ServiceUnavailableError
from app.config import settings


class TestSMSAgentClient:
    """Test suite for SMSAgentClient."""

    @pytest.fixture
    def client(self):
        """Create an SMSAgentClient instance."""
        return SMSAgentClient()

    @pytest.fixture
    def sample_conversation_history(self):
        """Sample conversation history data."""
        return [
            {
                "id": "msg-1",
                "timestamp": "2024-01-01T10:00:00Z",
                "direction": "inbound",
                "content": "I can't pay my bill this month",
                "sender": "+1234567890",
            },
            {
                "id": "msg-2",
                "timestamp": "2024-01-01T10:05:00Z",
                "direction": "outbound",
                "content": "I understand. Let's discuss payment options.",
                "sender": "system",
            },
        ]

    @pytest.fixture
    def sample_conversation_dict_response(self):
        """Sample conversation data in dict format with messages key."""
        return {
            "messages": [
                {
                    "id": "msg-1",
                    "timestamp": "2024-01-01T10:00:00Z",
                    "direction": "inbound",
                    "content": "I can pay $200 per week",
                    "sender": "+1234567890",
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_get_conversation_history_list_response(
        self, client, sample_conversation_history
    ):
        """Test successful conversation history retrieval with list response."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = sample_conversation_history
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            # Call the method
            result = await client.get_conversation_history("+1234567890")

            # Verify the call
            mock_client.get.assert_called_once_with(
                f"{settings.sms_agent_url}/conversations/+1234567890"
            )

            # Verify the result
            assert result == sample_conversation_history
            assert isinstance(result, list)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_conversation_history_dict_with_messages(
        self, client, sample_conversation_dict_response
    ):
        """Test conversation history retrieval with dict response containing messages key."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_conversation_dict_response
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            # Call the method
            result = await client.get_conversation_history("+1234567890")

            # Verify the result
            assert result == sample_conversation_dict_response["messages"]
            assert isinstance(result, list)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_conversation_history_dict_with_conversations(self, client):
        """Test conversation history retrieval with dict response containing conversations key."""
        sample_data = {
            "conversations": [
                {
                    "id": "conv-1",
                    "content": "Test message",
                    "timestamp": "2024-01-01T10:00:00Z",
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = sample_data
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            # Call the method
            result = await client.get_conversation_history("+1234567890")

            # Verify the result
            assert result == sample_data["conversations"]
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_conversation_history_single_dict(self, client):
        """Test conversation history retrieval with single dict response."""
        single_message = {
            "id": "msg-1",
            "content": "Single message",
            "timestamp": "2024-01-01T10:00:00Z",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = single_message
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            # Call the method
            result = await client.get_conversation_history("+1234567890")

            # Verify the result
            assert result == [single_message]
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_conversation_history_empty_response(self, client):
        """Test conversation history retrieval with empty/non-list response."""
        mock_response = MagicMock()
        mock_response.json.return_value = None
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            # Call the method
            result = await client.get_conversation_history("+1234567890")

            # Verify the result
            assert result == []

    @pytest.mark.asyncio
    async def test_get_conversation_history_timeout(self, client):
        """Test conversation history retrieval with timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.TimeoutException("Request timeout")

            # Verify ServiceUnavailableError is raised
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await client.get_conversation_history("+1234567890")

            assert "Request timeout after 30 seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_conversation_history_connection_error(self, client):
        """Test conversation history retrieval with connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")

            # Verify ServiceUnavailableError is raised
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await client.get_conversation_history("+1234567890")

            assert "Connection error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_conversation_history_server_error(self, client):
        """Test conversation history retrieval with server error (5xx)."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Service Unavailable", request=MagicMock(), response=mock_response
            )
            mock_client.get.return_value = mock_response

            # Verify ServiceUnavailableError is raised
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await client.get_conversation_history("+1234567890")

            assert "Server error: 503" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_conversation_history_circuit_breaker_open(self, client):
        """Test conversation history retrieval when circuit breaker is open."""
        # Manually trigger circuit breaker to open state
        for _ in range(client.circuit_breaker.failure_threshold + 1):
            try:
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client_class.return_value.__aenter__.return_value = mock_client
                    mock_client.get.side_effect = httpx.ConnectError(
                        "Connection failed"
                    )
                    await client.get_conversation_history("+1234567890")
            except ServiceUnavailableError:
                pass

        # Now circuit breaker should be open
        with pytest.raises(ServiceUnavailableError) as exc_info:
            await client.get_conversation_history("+1234567890")

        assert "Circuit breaker is OPEN" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            result = await client.health_check()

            assert result is True
            mock_client.get.assert_called_once_with(f"{settings.sms_agent_url}/health")

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """Test health check failure."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")

            result = await client.health_check()

            assert result is False

    def test_get_circuit_breaker_status(self, client):
        """Test getting circuit breaker status."""
        status = client.get_circuit_breaker_status()

        # Verify structure of status response
        assert "service" in status
        assert "state" in status
        assert "failure_count" in status
        assert "failure_threshold" in status
        assert "is_available" in status

        assert status["service"] == "SMS Agent"
        assert status["failure_threshold"] == settings.sms_agent_failure_threshold

    @pytest.mark.asyncio
    async def test_get_conversation_history_unexpected_error(self, client):
        """Test conversation history retrieval with unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = Exception("Unexpected error")

            # Verify ServiceUnavailableError is raised
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await client.get_conversation_history("+1234567890")

            assert "Unexpected error: Unexpected error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_conversation_history_invalid_empty_number(self, client):
        """Test conversation history retrieval with empty phone number."""
        with pytest.raises(ValueError) as exc_info:
            await client.get_conversation_history("")

        assert "Phone number cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_conversation_history_invalid_none_number(self, client):
        """Test conversation history retrieval with None phone number."""
        with pytest.raises(ValueError) as exc_info:
            await client.get_conversation_history(None)

        assert "Phone number must be a string" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_conversation_history_invalid_format(self, client):
        """Test conversation history retrieval with invalid phone number format."""
        with pytest.raises(ValueError) as exc_info:
            await client.get_conversation_history("invalid-phone")

        assert "Phone number format is invalid" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_conversation_history_invalid_zero_start(self, client):
        """Test conversation history retrieval with phone number starting with zero."""
        with pytest.raises(ValueError) as exc_info:
            await client.get_conversation_history("01234567890")

        assert "Phone number format is invalid" in str(exc_info.value)
