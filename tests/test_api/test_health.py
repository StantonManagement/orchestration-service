"""
Tests for the health check endpoints.
"""
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
import time

from app.config import settings


class TestHealthEndpoint:
    """Test cases for the basic health endpoint."""

    def test_health_check_success(self, client: TestClient, api_prefix: str):
        """Test that the health endpoint returns successful response."""
        response = client.get(f"{api_prefix}/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["version"] == settings.version
        assert data["service_name"] == settings.app_name
        assert "uptime_seconds" in data
        assert "timestamp" in data
        assert isinstance(data["uptime_seconds"], float)
        assert data["uptime_seconds"] >= 0

    def test_health_check_with_correlation_id(
        self, client: TestClient, api_prefix: str, sample_headers: dict
    ):
        """Test health endpoint with correlation ID header."""
        response = client.get(f"{api_prefix}/health", headers=sample_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_response_structure(self, client: TestClient, api_prefix: str):
        """Test that health response has correct structure."""
        response = client.get(f"{api_prefix}/health")

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        required_fields = [
            "status",
            "version",
            "uptime_seconds",
            "timestamp",
            "service_name",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Check data types
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["uptime_seconds"], float)
        assert isinstance(data["service_name"], str)
        assert isinstance(data["timestamp"], str)


class TestDetailedHealthEndpoint:
    """Test cases for the detailed health endpoint."""

    def test_detailed_health_check_success(self, client: TestClient, api_prefix: str):
        """Test that the detailed health endpoint returns successful response."""
        response = client.get(f"{api_prefix}/health/detailed")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] in ["healthy", "unhealthy"]
        assert data["version"] == settings.version
        assert data["service_name"] == settings.app_name
        assert "uptime_seconds" in data
        assert "timestamp" in data
        assert "checks" in data

    def test_detailed_health_check_checks_structure(
        self, client: TestClient, api_prefix: str
    ):
        """Test that detailed health response includes system checks."""
        response = client.get(f"{api_prefix}/health/detailed")

        assert response.status_code == 200
        data = response.json()

        checks = data["checks"]
        assert isinstance(checks, dict)

        # Should include basic checks (even if not implemented yet)
        expected_checks = ["database", "external_services", "memory"]
        for check in expected_checks:
            assert check in checks, f"Missing expected check: {check}"
            assert isinstance(checks[check], str)

    def test_detailed_health_with_correlation_id(
        self, client: TestClient, api_prefix: str, sample_headers: dict
    ):
        """Test detailed health endpoint with correlation ID header."""
        response = client.get(f"{api_prefix}/health/detailed", headers=sample_headers)

        assert response.status_code == 200
        data = response.json()
        assert "checks" in data
        assert data["service_name"] == settings.app_name

    def test_health_uptime_increases(self, client: TestClient, api_prefix: str):
        """Test that uptime increases between requests."""
        # First request
        response1 = client.get(f"{api_prefix}/health")
        assert response1.status_code == 200
        uptime1 = response1.json()["uptime_seconds"]

        # Small delay
        time.sleep(0.1)

        # Second request
        response2 = client.get(f"{api_prefix}/health")
        assert response2.status_code == 200
        uptime2 = response2.json()["uptime_seconds"]

        # Uptime should have increased
        assert uptime2 > uptime1
        assert uptime2 - uptime1 >= 0.1  # At least the delay we added


class TestDependenciesHealthEndpoint:
    """Test cases for the dependencies health endpoint."""

    def test_dependencies_health_check_success(
        self, client: TestClient, api_prefix: str, mocker
    ):
        """Test successful dependencies health check."""
        # Mock successful health checks
        mock_collections_client = AsyncMock()
        mock_collections_client.health_check.return_value = True

        mock_sms_client = AsyncMock()
        mock_sms_client.health_check.return_value = True

        mocker.patch(
            "app.services.collections_monitor.CollectionsMonitorClient",
            return_value=mock_collections_client,
        )
        mocker.patch(
            "app.services.sms_agent.SMSAgentClient", return_value=mock_sms_client
        )

        response = client.get(f"{api_prefix}/health/dependencies")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        expected_fields = [
            "collections_monitor",
            "sms_agent",
            "notification_service",
            "supabase",
            "openai",
        ]
        for field in expected_fields:
            assert field in data

        # Check values
        assert data["collections_monitor"] is True
        assert data["sms_agent"] is True
        assert data["notification_service"] is False  # Not implemented
        assert data["supabase"] is False  # Not implemented
        assert data["openai"] is False  # Not implemented

    def test_dependencies_health_check_partial_failure(
        self, client: TestClient, api_prefix: str, mocker
    ):
        """Test dependencies health check with one service down."""
        # Mock the health check methods directly on the client classes
        mock_collections_health = AsyncMock(return_value=True)
        mock_sms_health = AsyncMock(return_value=False)

        # Patch the health_check method after instance creation
        mocker.patch(
            "app.services.collections_monitor.CollectionsMonitorClient.health_check",
            mock_collections_health,
        )
        mocker.patch(
            "app.services.sms_agent.SMSAgentClient.health_check",
            mock_sms_health,
        )

        response = client.get(f"{api_prefix}/health/dependencies")

        assert response.status_code == 200
        data = response.json()

        assert data["collections_monitor"] is True
        assert data["sms_agent"] is False

    def test_dependencies_health_check_exception_handling(
        self, client: TestClient, api_prefix: str, mocker
    ):
        """Test dependencies health check with service exceptions."""
        # Mock exceptions during health checks
        mock_collections_health = AsyncMock(side_effect=Exception("Connection failed"))
        mock_sms_health = AsyncMock(return_value=True)

        # Patch the health_check method after instance creation
        mocker.patch(
            "app.services.collections_monitor.CollectionsMonitorClient.health_check",
            mock_collections_health,
        )
        mocker.patch(
            "app.services.sms_agent.SMSAgentClient.health_check",
            mock_sms_health,
        )

        response = client.get(f"{api_prefix}/health/dependencies")

        assert response.status_code == 200
        data = response.json()

        # Should handle exceptions gracefully and mark service as unhealthy
        assert data["collections_monitor"] is False
        assert data["sms_agent"] is True

    def test_dependencies_health_with_correlation_id(
        self, client: TestClient, api_prefix: str, sample_headers: dict, mocker
    ):
        """Test dependencies health endpoint with correlation ID."""
        mock_collections_client = AsyncMock()
        mock_collections_client.health_check.return_value = True

        mock_sms_client = AsyncMock()
        mock_sms_client.health_check.return_value = True

        mocker.patch(
            "app.services.collections_monitor.CollectionsMonitorClient",
            return_value=mock_collections_client,
        )
        mocker.patch(
            "app.services.sms_agent.SMSAgentClient", return_value=mock_sms_client
        )

        response = client.get(
            f"{api_prefix}/health/dependencies", headers=sample_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestDependenciesHealthDetailedEndpoint:
    """Test cases for the detailed dependencies health endpoint."""

    def test_dependencies_detailed_health_check_success(
        self, client: TestClient, api_prefix: str, mocker
    ):
        """Test successful detailed dependencies health check."""
        # Mock collections monitor
        mock_collections_client = AsyncMock()
        mock_collections_client.health_check.return_value = True
        mock_collections_client.get_circuit_breaker_status.return_value = {
            "service": "Collections Monitor",
            "state": "closed",
            "failure_count": 0,
            "failure_threshold": 5,
            "is_available": True,
        }

        # Mock SMS agent
        mock_sms_client = AsyncMock()
        mock_sms_client.health_check.return_value = True
        mock_sms_client.get_circuit_breaker_status.return_value = {
            "service": "SMS Agent",
            "state": "closed",
            "failure_count": 0,
            "failure_threshold": 3,
            "is_available": True,
        }

        mocker.patch(
            "app.services.collections_monitor.CollectionsMonitorClient",
            return_value=mock_collections_client,
        )
        mocker.patch(
            "app.services.sms_agent.SMSAgentClient", return_value=mock_sms_client
        )

        response = client.get(f"{api_prefix}/health/dependencies/detailed")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "collections_monitor" in data
        assert "sms_agent" in data
        assert "notification_service" in data
        assert "supabase" in data
        assert "openai" in data

        # Check implemented services
        collections_data = data["collections_monitor"]
        assert collections_data["healthy"] is True
        assert "circuit_breaker" in collections_data
        assert collections_data["circuit_breaker"]["service"] == "Collections Monitor"

        sms_data = data["sms_agent"]
        assert sms_data["healthy"] is True
        assert "circuit_breaker" in sms_data
        assert sms_data["circuit_breaker"]["service"] == "SMS Agent"

        # Check non-implemented services
        assert data["notification_service"]["healthy"] is False
        assert data["notification_service"]["status"] == "not_implemented"
        assert data["supabase"]["healthy"] is False
        assert data["supabase"]["status"] == "not_implemented"
        assert data["openai"]["healthy"] is False
        assert data["openai"]["status"] == "not_implemented"

    def test_dependencies_detailed_health_check_circuit_breaker_open(
        self, client: TestClient, api_prefix: str, mocker
    ):
        """Test detailed dependencies health check with open circuit breaker."""
        # Mock collections monitor with open circuit breaker
        mock_collections_health = AsyncMock(return_value=False)
        mock_collections_status = mocker.Mock(
            return_value={
                "service": "Collections Monitor",
                "state": "open",
                "failure_count": 6,
                "failure_threshold": 5,
                "is_available": False,
            }
        )

        # Mock SMS agent
        mock_sms_health = AsyncMock(return_value=True)
        mock_sms_status = mocker.Mock(
            return_value={
                "service": "SMS Agent",
                "state": "closed",
                "failure_count": 0,
                "failure_threshold": 3,
                "is_available": True,
            }
        )

        # Patch the methods after instance creation
        mocker.patch(
            "app.services.collections_monitor.CollectionsMonitorClient.health_check",
            mock_collections_health,
        )
        mocker.patch(
            "app.services.collections_monitor.CollectionsMonitorClient.get_circuit_breaker_status",
            mock_collections_status,
        )
        mocker.patch(
            "app.services.sms_agent.SMSAgentClient.health_check",
            mock_sms_health,
        )
        mocker.patch(
            "app.services.sms_agent.SMSAgentClient.get_circuit_breaker_status",
            mock_sms_status,
        )

        response = client.get(f"{api_prefix}/health/dependencies/detailed")

        assert response.status_code == 200
        data = response.json()

        collections_data = data["collections_monitor"]
        assert collections_data["healthy"] is False
        assert collections_data["circuit_breaker"]["state"] == "open"
        assert collections_data["circuit_breaker"]["is_available"] is False

        sms_data = data["sms_agent"]
        assert sms_data["healthy"] is True
        assert sms_data["circuit_breaker"]["state"] == "closed"
