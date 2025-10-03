"""
Tests for Collections Monitor service client.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from app.services.collections_monitor import CollectionsMonitorClient
from app.core.exceptions import ServiceUnavailableError
from app.config import settings


class TestCollectionsMonitorClient:
    """Test suite for CollectionsMonitorClient."""

    @pytest.fixture
    def client(self):
        """Create a CollectionsMonitorClient instance."""
        return CollectionsMonitorClient()

    @pytest.fixture
    def sample_tenant_context(self):
        """Sample tenant context data."""
        return {
            "tenant_id": "12345",
            "name": "John Doe",
            "payment_history": [
                {"date": "2024-01-01", "amount": 500, "status": "paid"},
                {"date": "2024-02-01", "amount": 500, "status": "missed"},
            ],
            "language_preference": "en",
            "total_balance": 1500.0,
        }

    @pytest.mark.asyncio
    async def test_get_tenant_context_success(self, client, sample_tenant_context):
        """Test successful tenant context retrieval."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = sample_tenant_context
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            # Call the method
            result = await client.get_tenant_context("12345")

            # Verify the call
            mock_client.get.assert_called_once_with(
                f"{settings.monitor_url}/monitor/tenant/12345"
            )

            # Verify the result
            assert result == sample_tenant_context

    @pytest.mark.asyncio
    async def test_get_tenant_context_timeout(self, client):
        """Test tenant context retrieval with timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.TimeoutException("Request timeout")

            # Verify ServiceUnavailableError is raised
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await client.get_tenant_context("12345")

            assert "Request timeout after 60 seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_tenant_context_connection_error(self, client):
        """Test tenant context retrieval with connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")

            # Verify ServiceUnavailableError is raised
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await client.get_tenant_context("12345")

            assert "Connection error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_tenant_context_server_error(self, client):
        """Test tenant context retrieval with server error (5xx)."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Internal Server Error", request=MagicMock(), response=mock_response
            )
            mock_client.get.return_value = mock_response

            # Verify ServiceUnavailableError is raised
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await client.get_tenant_context("12345")

            assert "Server error: 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_tenant_context_client_error(self, client):
        """Test tenant context retrieval with client error (4xx)."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )
            mock_client.get.return_value = mock_response

            # Verify HTTPStatusError is re-raised as-is for 4xx errors
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_tenant_context("12345")

    @pytest.mark.asyncio
    async def test_get_tenant_context_circuit_breaker_open(self, client):
        """Test tenant context retrieval when circuit breaker is open."""
        # Manually trigger circuit breaker to open state
        for _ in range(client.circuit_breaker.failure_threshold + 1):
            try:
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client_class.return_value.__aenter__.return_value = mock_client
                    mock_client.get.side_effect = httpx.ConnectError(
                        "Connection failed"
                    )
                    await client.get_tenant_context("12345")
            except ServiceUnavailableError:
                pass

        # Now circuit breaker should be open
        with pytest.raises(ServiceUnavailableError) as exc_info:
            await client.get_tenant_context("12345")

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
            mock_client.get.assert_called_once_with(f"{settings.monitor_url}/health")

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """Test health check failure."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_non_200_status(self, client):
        """Test health check with non-200 status code."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

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

        assert status["service"] == "Collections Monitor"
        assert status["failure_threshold"] == settings.monitor_failure_threshold

    @pytest.mark.asyncio
    async def test_get_tenant_context_unexpected_error(self, client):
        """Test tenant context retrieval with unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = Exception("Unexpected error")

            # Verify ServiceUnavailableError is raised
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await client.get_tenant_context("12345")

            assert "Unexpected error: Unexpected error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_tenant_context_invalid_empty_id(self, client):
        """Test tenant context retrieval with empty tenant ID."""
        with pytest.raises(ValueError) as exc_info:
            await client.get_tenant_context("")

        assert "Tenant ID cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_tenant_context_invalid_none_id(self, client):
        """Test tenant context retrieval with None tenant ID."""
        with pytest.raises(ValueError) as exc_info:
            await client.get_tenant_context(None)

        assert "Tenant ID must be a string" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_tenant_context_invalid_characters(self, client):
        """Test tenant context retrieval with invalid characters."""
        with pytest.raises(ValueError) as exc_info:
            await client.get_tenant_context("tenant@123")

        assert "contains invalid characters" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_tenant_context_too_long(self, client):
        """Test tenant context retrieval with too long tenant ID."""
        long_id = "a" * 51  # 51 characters, exceeds limit of 50
        with pytest.raises(ValueError) as exc_info:
            await client.get_tenant_context(long_id)

        assert "contains invalid characters or is too long" in str(exc_info.value)
