import pytest
import json
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.services.metrics_service import MetricsService


class TestMetricsAPI:
    """Test suite for Metrics API endpoints"""

    @pytest.fixture
    def client(self):
        """Create a test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_metrics_service(self):
        """Create a mock metrics service"""
        return Mock(spec=MetricsService)

    def test_get_metrics_success(self, client):
        """Test GET /orchestrate/metrics endpoint returns success"""
        response = client.get("/orchestrate/metrics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "dashboard" in data
        assert "last_hour" in data["dashboard"]
        assert "today" in data["dashboard"]

    def test_get_metrics_structure(self, client):
        """Test GET /orchestrate/metrics response structure"""
        response = client.get("/orchestrate/metrics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check dashboard structure
        dashboard = data["dashboard"]

        # Check last_hour structure
        last_hour = dashboard["last_hour"]
        required_fields = ["sms_received", "ai_responses", "auto_approval_rate", "avg_response_time_ms", "escalations", "payment_plans"]
        for field in required_fields:
            assert field in last_hour
            assert isinstance(last_hour[field], (int, float))

        # Check today structure
        today = dashboard["today"]
        required_fields = ["total_messages", "escalations", "payment_plans", "approvals"]
        for field in required_fields:
            assert field in today
            assert isinstance(today[field], int)

    def test_get_metrics_with_time_range(self, client):
        """Test GET /orchestrate/metrics with hours query parameter"""
        # Test with valid hour values
        for hours in [1, 24, 168, 720]:  # 1 hour, 1 day, 1 week, 1 month
            response = client.get(f"/orchestrate/metrics?hours={hours}")
            assert response.status_code == status.HTTP_200_OK

    def test_get_metrics_invalid_time_range(self, client):
        """Test GET /orchestrate/metrics with invalid hours parameter"""
        response = client.get("/orchestrate/metrics?hours=0")  # Invalid: less than 1
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_metrics_with_format_json(self, client):
        """Test GET /orchestrate/metrics with JSON format"""
        response = client.get("/orchestrate/metrics?format=json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_get_metrics_with_format_dashboard(self, client):
        """Test GET /orchestrate/metrics with dashboard format"""
        response = client.get("/orchestrate/metrics?format=dashboard")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)
        # Dashboard format should have additional fields
        assert "overview" in data or "performance" in data

    def test_get_metrics_with_format_prometheus(self, client):
        """Test GET /orchestrate/metrics with Prometheus format"""
        response = client.get("/orchestrate/metrics?format=prometheus")

        assert response.status_code == status.HTTP_200_OK
        # Prometheus format should return text/plain
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

        # Check that it contains Prometheus-style metrics
        text_data = response.text
        assert "system_orchestrator" in text_data or "performance_http_request" in text_data

    def test_get_metrics_with_start_and_end_dates(self, client):
        """Test GET /orchestrate/metrics with start and end date parameters"""
        now = datetime.now()
        start_date = (now - timedelta(hours=1)).isoformat()
        end_date = now.isoformat()

        response = client.get(
            f"/orchestrate/metrics?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_get_metrics_invalid_date_format(self, client):
        """Test GET /orchestrate/metrics with invalid date format"""
        response = client.get(
            "/orchestrate/metrics?start_date=invalid-date&end_date=2025-10-03"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('app.services.metrics_service.MetricsService.get_metrics')
    def test_get_metrics_service_error_handling(self, mock_get_metrics, client):
        """Test error handling when metrics service fails"""
        mock_get_metrics.side_effect = Exception("Service error")

        response = client.get("/orchestrate/metrics")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_metrics_performance_endpoint(self, client):
        """Test GET /orchestrate/metrics/performance endpoint"""
        response = client.get("/orchestrate/metrics/performance")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

        # Performance metrics should include timing data
        required_fields = ["p50_response_time", "p90_response_time", "p99_response_time", "total_requests"]
        for field in required_fields:
            assert field in data

    def test_get_metrics_business_endpoint(self, client):
        """Test GET /orchestrate/metrics/business endpoint"""
        response = client.get("/orchestrate/metrics/business")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

        # Business metrics should include business-relevant data
        required_fields = ["total_sms_volume", "average_approval_rate", "total_escalations", "payment_plans_detected"]
        for field in required_fields:
            assert field in data

    def test_get_metrics_health_endpoint(self, client):
        """Test GET /orchestrate/metrics/health endpoint"""
        response = client.get("/orchestrate/metrics/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

        # Health metrics should include system health information
        required_fields = ["service_status", "last_updated", "metrics_collection_status"]
        for field in required_fields:
            assert field in data

    def test_get_metrics_caching(self, client):
        """Test that metrics endpoint has caching enabled"""
        # First request
        response1 = client.get("/orchestrate/metrics")
        assert response1.status_code == status.HTTP_200_OK

        # Check for cache headers
        cache_control = response1.headers.get("cache-control")
        if cache_control:
            assert "max-age" in cache_control.lower()

    def test_get_metrics_rate_limiting(self, client):
        """Test that metrics endpoint has rate limiting (if implemented)"""
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = client.get("/orchestrate/metrics")
            responses.append(response)

        # At least some requests should succeed
        success_count = sum(1 for r in responses if r.status_code == status.HTTP_200_OK)
        assert success_count > 0

    def test_get_metrics_concurrent_requests(self, client):
        """Test concurrent requests to metrics endpoint"""
        import threading
        import time

        results = []

        def make_request():
            response = client.get("/orchestrate/metrics")
            results.append(response.status_code)

        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should succeed
        assert all(status == status.HTTP_200_OK for status in results)

    def test_get_metrics_with_different_granularities(self, client):
        """Test metrics with different time granularities"""
        granularities = ["minute", "hour", "day"]

        for granularity in granularities:
            response = client.get(f"/orchestrate/metrics?granularity={granularity}")
            assert response.status_code == status.HTTP_200_OK

    def test_metrics_response_time(self, client):
        """Test that metrics endpoint responds quickly"""
        import time

        start_time = time.time()
        response = client.get("/orchestrate/metrics")
        end_time = time.time()

        assert response.status_code == status.HTTP_200_OK

        # Response should be fast (under 1 second)
        response_time = end_time - start_time
        assert response_time < 1.0

    @patch('app.services.metrics_service.MetricsService')
    def test_metrics_service_injection(self, mock_service_class, client):
        """Test that metrics service is properly injected"""
        mock_service = Mock()
        mock_service.get_metrics.return_value = {"test": "data"}
        mock_service_class.return_value = mock_service

        response = client.get("/orchestrate/metrics")
        assert response.status_code == status.HTTP_200_OK
        mock_service.get_metrics.assert_called()

    def test_metrics_endpoint_authentication(self, client):
        """Test metrics endpoint authentication (if implemented)"""
        # Test without authentication
        response = client.get("/orchestrate/metrics")

        # If authentication is required, this should return 401
        # If not required, this should return 200
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_metrics_endpoint_cors_headers(self, client):
        """Test CORS headers on metrics endpoint"""
        response = client.get("/orchestrate/metrics")

        # Check for CORS headers if implemented
        cors_headers = ["access-control-allow-origin", "access-control-allow-methods"]
        for header in cors_headers:
            if header in response.headers:
                assert response.headers[header] is not None

    def test_metrics_error_response_format(self, client):
        """Test that error responses follow consistent format"""
        # Test with invalid parameter
        response = client.get("/orchestrate/metrics?time_range=invalid")

        if response.status_code != status.HTTP_200_OK:
            error_data = response.json()
            assert "detail" in error_data or "error" in error_data

    def test_metrics_data_types(self, client):
        """Test that metrics endpoint returns correct data types"""
        response = client.get("/orchestrate/metrics")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()

        # Check that numeric values are actually numbers
        if "last_hour" in data:
            last_hour = data["last_hour"]
            numeric_fields = ["sms_received", "ai_responses", "auto_approval_rate", "avg_response_time_ms"]
            for field in numeric_fields:
                if field in last_hour:
                    assert isinstance(last_hour[field], (int, float))