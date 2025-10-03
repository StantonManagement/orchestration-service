import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import json
from collections import deque

from app.services.metrics_service import MetricsService


class TestMetricsService:
    """Test suite for MetricsService class"""

    @pytest.fixture
    def metrics_service(self):
        """Create a MetricsService instance for testing"""
        return MetricsService()

    @pytest.fixture
    def mock_metrics_data(self):
        """Create mock metrics data for testing"""
        return {
            "timestamp": datetime.now(),
            "sms_volume": 10,
            "ai_responses": 8,
            "approval_rate": 0.85,
            "response_time_ms": 250,
            "escalations": 2,
            "payment_plans": 3
        }

    def test_metrics_service_initialization(self, metrics_service):
        """Test MetricsService initializes correctly"""
        assert isinstance(metrics_service.metrics_storage, dict)
        assert isinstance(metrics_service.counters, dict)
        assert isinstance(metrics_service.gauges, dict)
        assert isinstance(metrics_service.histograms, dict)

    def test_record_sms_volume(self, metrics_service):
        """Test SMS volume recording"""
        metrics_service.record_sms_received("test_tenant", "+1234567890")

        # Check metrics are recorded
        assert "sms_volume" in metrics_service.metrics_storage
        assert len(metrics_service.metrics_storage["sms_volume"]) == 1
        assert metrics_service.counters["sms_received_total"] == 1

    def test_record_ai_response_time(self, metrics_service):
        """Test AI response time recording"""
        metrics_service.record_ai_response("test_tenant", 150, 0.85)

        # Check metrics are recorded
        assert "response_times" in metrics_service.metrics_storage
        assert len(metrics_service.metrics_storage["response_times"]) == 1
        assert metrics_service.counters["ai_responses_total"] == 1
        assert metrics_service.histograms["ai_response_times"][0] == 150

    def test_record_approval_rate(self, metrics_service):
        """Test approval rate recording"""
        metrics_service.record_approval_decision("test_tenant", True, auto_approved=True)

        # Check metrics are recorded
        assert "approval_rates" in metrics_service.metrics_storage
        assert len(metrics_service.metrics_storage["approval_rates"]) == 1
        assert metrics_service.counters["approvals_total"] == 1
        assert metrics_service.counters["auto_approvals_total"] == 1

    def test_record_escalation(self, metrics_service):
        """Test escalation recording"""
        metrics_service.record_escalation("test_tenant", "timeout", "high")

        # Check metrics are recorded
        assert "escalations" in metrics_service.metrics_storage
        assert len(metrics_service.metrics_storage["escalations"]) == 1
        assert metrics_service.counters["escalations_total"] == 1
        assert metrics_service.counters["escalations_timeout"] == 1

    def test_record_payment_plan_detection(self, metrics_service):
        """Test payment plan detection recording"""
        metrics_service.record_payment_plan_detected("test_tenant", True, validated=True)

        # Check metrics are recorded
        assert "payment_plans" in metrics_service.metrics_storage
        assert len(metrics_service.metrics_storage["payment_plans"]) == 1
        assert metrics_service.counters["payment_plans_detected_total"] == 1
        assert metrics_service.counters["payment_plans_validated_total"] == 1

    def test_get_metrics_last_hour(self, metrics_service):
        """Test getting metrics for the last hour"""
        # Record some metrics
        metrics_service.record_sms_received("test_tenant", "+1234567890")
        metrics_service.record_ai_response("test_tenant", 200, 0.85)
        metrics_service.record_approval_decision("test_tenant", True, auto_approved=True)

        # Get last hour metrics
        result = metrics_service.get_metrics_summary(hours=1)

        assert "sms_metrics" in result
        assert "ai_metrics" in result
        assert "approval_metrics" in result
        assert result["sms_metrics"]["received"] == 1
        assert result["ai_metrics"]["responses"] == 1
        assert result["approval_metrics"]["auto_approval_rate"] == 1.0

    def test_get_metrics_today(self, metrics_service):
        """Test getting metrics for today"""
        # Record some metrics
        metrics_service.record_sms_received("test_tenant", "+1234567890")
        metrics_service.record_escalation("test_tenant", "timeout", "medium")
        metrics_service.record_payment_plan_detected("test_tenant", True, validated=True)

        # Get today's metrics
        result = metrics_service.get_dashboard_metrics()

        assert "today" in result
        assert "last_hour" in result
        assert result["today"]["total_messages"] == 1
        assert result["today"]["escalations"] == 1
        assert result["today"]["payment_plans"] == 1

    def test_get_metrics_summary_with_different_hours(self, metrics_service):
        """Test getting metrics summary with different hour values"""
        # Record some metrics
        metrics_service.record_sms_received("test_tenant", "+1234567890")

        # Get metrics for different time periods
        result_1hr = metrics_service.get_metrics_summary(hours=1)
        result_24hr = metrics_service.get_metrics_summary(hours=24)

        assert result_1hr["timeframe_hours"] == 1
        assert result_24hr["timeframe_hours"] == 24

    def test_calculate_percentiles(self, metrics_service):
        """Test percentile calculation"""
        # Add some response times
        response_times = [100, 150, 200, 250, 300]
        for time in response_times:
            metrics_service.record_ai_response("test_tenant", time, 0.85)

        # Calculate percentiles using the actual method
        percentiles = metrics_service._calculate_percentiles(response_times)

        assert percentiles["p50"] == 200  # Median of sorted times
        assert percentiles["p90"] == 300  # 90th percentile
        assert percentiles["p99"] == 300  # 99th percentile

    def test_get_performance_summary(self, metrics_service):
        """Test getting performance summary"""
        # Record some performance metrics
        for i in range(5):
            metrics_service.record_performance_metric("test_operation", 100 + i * 10)

        # Get performance metrics
        performance_data = metrics_service._get_recent_metrics("performance", datetime.utcnow() - timedelta(hours=1))

        assert isinstance(performance_data, list)

    def test_get_prometheus_metrics(self, metrics_service):
        """Test getting Prometheus metrics"""
        # Record some metrics
        metrics_service.record_sms_received("test_tenant", "+1234567890")
        metrics_service.record_ai_response("test_tenant", 150, 0.85)

        # Get Prometheus metrics
        prometheus_data = metrics_service.get_prometheus_metrics()

        assert isinstance(prometheus_data, str)
        assert "sms_received_total" in prometheus_data
        assert "ai_responses_total" in prometheus_data

    def test_record_service_health(self, metrics_service):
        """Test service health recording"""
        metrics_service.record_service_health("test_service", True, 50.0)

        # Check health metrics are recorded
        assert "system_health" in metrics_service.metrics_storage
        assert len(metrics_service.metrics_storage["system_health"]) == 1
        assert metrics_service.counters["test_service_healthy_checks"] == 1
        assert metrics_service.gauges["test_service_response_time"] == 50.0

    def test_metrics_storage_limits(self, metrics_service):
        """Test that metrics storage respects maxlen"""
        # Check that storage uses deque with maxlen
        for metric_name, storage in metrics_service.metrics_storage.items():
            assert isinstance(storage, deque)
            assert storage.maxlen == 10000

        # Check histograms also use deque with maxlen
        for hist_name, histogram in metrics_service.histograms.items():
            assert isinstance(histogram, deque)
            assert histogram.maxlen == 1000

    def test_get_dashboard_metrics(self, metrics_service):
        """Test getting dashboard-formatted metrics"""
        # Record some metrics
        metrics_service.record_sms_received("test_tenant", "+1234567890")
        metrics_service.record_ai_response("test_tenant", 180, 0.85)
        metrics_service.record_approval_decision("test_tenant", True, auto_approved=True)

        dashboard_data = metrics_service.get_dashboard_metrics()

        assert "last_hour" in dashboard_data
        assert "today" in dashboard_data
        assert "system_health" in dashboard_data
        assert "performance" in dashboard_data

        # Check last_hour section
        last_hour = dashboard_data["last_hour"]
        assert "sms_received" in last_hour
        assert "ai_responses" in last_hour
        assert "auto_approval_rate" in last_hour

    def test_cleanup_old_metrics(self, metrics_service):
        """Test cleanup of old metrics"""
        # Record some metrics
        metrics_service.record_sms_received("test_tenant", "+1234567890")
        metrics_service.record_ai_response("test_tenant", 150, 0.85)

        # Cleanup old metrics (should not raise errors)
        metrics_service.cleanup_old_metrics()

        # Check that storage structures remain intact
        assert isinstance(metrics_service.metrics_storage, dict)
        assert isinstance(metrics_service.counters, dict)
        assert isinstance(metrics_service.gauges, dict)
        assert isinstance(metrics_service.histograms, dict)

    def test_reset_metrics(self, metrics_service):
        """Test resetting all metrics"""
        # Record some metrics
        metrics_service.record_sms_received("test_tenant", "+1234567890")
        metrics_service.record_ai_response("test_tenant", 150, 0.85)

        # Reset metrics
        metrics_service.reset_metrics()

        # Check that all metrics are cleared
        assert len(metrics_service.counters) == 0
        assert len(metrics_service.gauges) == 0
        assert len(metrics_service.histograms) == 0
        assert len(metrics_service.metrics_storage) == 0

    @patch('app.services.metrics_service.datetime')
    def test_time_based_filtering(self, mock_datetime, metrics_service):
        """Test filtering metrics by time"""
        # Mock current time
        current_time = datetime(2025, 10, 3, 12, 0, 0)
        mock_datetime.now.return_value = current_time

        # Record metrics at different times
        old_time = current_time - timedelta(hours=2)
        recent_time = current_time - timedelta(minutes=30)

        # This would require mocking the timestamp storage
        # For now, just test the method exists
        metrics_service.get_metrics_summary(1)

    @pytest.mark.asyncio
    async def test_concurrent_metric_recording(self, metrics_service):
        """Test concurrent metric recording"""
        async def record_metrics():
            for i in range(10):
                metrics_service.record_sms_received("tenant123", f"+1555123456{i}")
                metrics_service.record_performance_metric("ai_response", i * 10)
                await asyncio.sleep(0.001)  # Small delay

        # Run concurrent recordings
        tasks = [record_metrics() for _ in range(3)]
        await asyncio.gather(*tasks)

        # Check that all metrics were recorded
        assert metrics_service.counters["sms_received_total"] > 0
        assert len(metrics_service.histograms["performance_ai_response"]) > 0