"""
Metrics collection and aggregation service for system monitoring.
"""
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import structlog
from app.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """Summary statistics for a metric over a time period."""
    count: int
    sum: float
    avg: float
    min: float
    max: float
    p50: float
    p90: float
    p99: float


class MetricsService:
    """Service for collecting, storing, and aggregating system metrics."""

    def __init__(self):
        """Initialize metrics service with default configuration."""
        self.metrics_storage = defaultdict(lambda: deque(maxlen=10000))
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(lambda: deque(maxlen=1000))

        # Default retention periods (in hours)
        self.retention_periods = {
            "sms_volume": 168,  # 7 days
            "response_times": 168,
            "approval_rates": 720,  # 30 days
            "escalations": 2160,  # 90 days
            "payment_plans": 720,
            "performance": 168,
            "system_health": 24,  # 1 day
        }

        # Aggregation intervals (in minutes)
        self.aggregation_intervals = {
            "realtime": 1,
            "hourly": 60,
            "daily": 1440,
        }

        logger.info("Metrics service initialized", retention_periods=list(self.retention_periods.keys()))

    def record_sms_received(self, tenant_id: str, phone_number: str) -> None:
        """
        Record an incoming SMS message.

        Args:
            tenant_id: Tenant identifier
            phone_number: Phone number that sent the SMS
        """
        timestamp = datetime.utcnow()
        point = TimeSeriesPoint(
            timestamp=timestamp,
            value=1.0,
            tags={"tenant_id": tenant_id, "event_type": "sms_received"}
        )
        self.metrics_storage["sms_volume"].append(point)
        self.counters["sms_received_total"] += 1

        logger.debug("SMS received recorded", tenant_id=tenant_id, phone_number=phone_number)

    def record_ai_response(self, tenant_id: str, response_time_ms: float, confidence_score: float) -> None:
        """
        Record AI response generation metrics.

        Args:
            tenant_id: Tenant identifier
            response_time_ms: Time taken to generate response in milliseconds
            confidence_score: AI confidence score (0.0-1.0)
        """
        timestamp = datetime.utcnow()

        # Record response time
        response_point = TimeSeriesPoint(
            timestamp=timestamp,
            value=response_time_ms,
            tags={"tenant_id": tenant_id, "metric_type": "response_time"}
        )
        self.metrics_storage["response_times"].append(response_point)
        self.histograms["ai_response_times"].append(response_time_ms)

        # Record confidence score
        confidence_point = TimeSeriesPoint(
            timestamp=timestamp,
            value=confidence_score,
            tags={"tenant_id": tenant_id, "metric_type": "confidence_score"}
        )
        self.metrics_storage["ai_confidence"].append(confidence_point)

        self.counters["ai_responses_total"] += 1

        logger.debug("AI response recorded", tenant_id=tenant_id, response_time_ms=response_time_ms, confidence_score=confidence_score)

    def record_approval_decision(self, tenant_id: str, approved: bool, auto_approved: bool = False) -> None:
        """
        Record an approval decision.

        Args:
            tenant_id: Tenant identifier
            approved: Whether the response was approved
            auto_approved: Whether the approval was automatic
        """
        timestamp = datetime.utcnow()
        point = TimeSeriesPoint(
            timestamp=timestamp,
            value=1.0 if approved else 0.0,
            tags={
                "tenant_id": tenant_id,
                "event_type": "approval_decision",
                "approval_type": "auto" if auto_approved else "manual"
            }
        )
        self.metrics_storage["approval_rates"].append(point)

        if approved:
            self.counters["approvals_total"] += 1
            if auto_approved:
                self.counters["auto_approvals_total"] += 1
        else:
            self.counters["rejections_total"] += 1

        logger.debug("Approval decision recorded", tenant_id=tenant_id, approved=approved, auto_approved=auto_approved)

    def record_escalation(self, tenant_id: str, escalation_type: str, severity: str) -> None:
        """
        Record an escalation event.

        Args:
            tenant_id: Tenant identifier
            escalation_type: Type of escalation (e.g., "timeout", "low_confidence")
            severity: Severity level (e.g., "low", "medium", "high")
        """
        timestamp = datetime.utcnow()
        point = TimeSeriesPoint(
            timestamp=timestamp,
            value=1.0,
            tags={
                "tenant_id": tenant_id,
                "escalation_type": escalation_type,
                "severity": severity
            }
        )
        self.metrics_storage["escalations"].append(point)
        self.counters["escalations_total"] += 1
        self.counters[f"escalations_{escalation_type}"] += 1

        logger.debug("Escalation recorded", tenant_id=tenant_id, escalation_type=escalation_type, severity=severity)

    def record_payment_plan_detected(self, tenant_id: str, detected: bool, validated: bool = False) -> None:
        """
        Record payment plan detection metrics.

        Args:
            tenant_id: Tenant identifier
            detected: Whether a payment plan was detected
            validated: Whether the payment plan was validated
        """
        timestamp = datetime.utcnow()
        point = TimeSeriesPoint(
            timestamp=timestamp,
            value=1.0 if detected else 0.0,
            tags={
                "tenant_id": tenant_id,
                "event_type": "payment_plan_detection",
                "validated": str(validated)
            }
        )
        self.metrics_storage["payment_plans"].append(point)

        if detected:
            self.counters["payment_plans_detected_total"] += 1
            if validated:
                self.counters["payment_plans_validated_total"] += 1

        logger.debug("Payment plan detection recorded", tenant_id=tenant_id, detected=detected, validated=validated)

    def record_performance_metric(self, operation: str, duration_ms: float, service: str = None) -> None:
        """
        Record performance timing for operations.

        Args:
            operation: Operation name (e.g., "database_query", "external_api_call")
            duration_ms: Duration in milliseconds
            service: Service name if applicable
        """
        timestamp = datetime.utcnow()
        tags = {"operation": operation}
        if service:
            tags["service"] = service

        point = TimeSeriesPoint(
            timestamp=timestamp,
            value=duration_ms,
            tags=tags
        )
        self.metrics_storage["performance"].append(point)
        self.histograms[f"performance_{operation}"].append(duration_ms)

        logger.debug("Performance metric recorded", operation=operation, duration_ms=duration_ms, service=service)

    def record_service_health(self, service: str, healthy: bool, response_time_ms: float = None) -> None:
        """
        Record service health status.

        Args:
            service: Service name
            healthy: Whether the service is healthy
            response_time_ms: Health check response time
        """
        timestamp = datetime.utcnow()
        point = TimeSeriesPoint(
            timestamp=timestamp,
            value=1.0 if healthy else 0.0,
            tags={"service": service, "event_type": "health_check"}
        )
        self.metrics_storage["system_health"].append(point)

        if healthy:
            self.counters[f"{service}_healthy_checks"] += 1
        else:
            self.counters[f"{service}_unhealthy_checks"] += 1

        if response_time_ms:
            self.gauges[f"{service}_response_time"] = response_time_ms

        logger.debug("Service health recorded", service=service, healthy=healthy, response_time_ms=response_time_ms)

    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """
        Get metrics summary for the specified time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary containing metrics summary
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        # SMS volume metrics
        sms_data = self._get_recent_metrics("sms_volume", cutoff_time)
        sms_count = len(sms_data)

        # AI response metrics
        response_data = self._get_recent_metrics("response_times", cutoff_time)
        response_times = [p.value for p in response_data]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # Approval metrics
        approval_data = self._get_recent_metrics("approval_rates", cutoff_time)
        approvals = [p for p in approval_data if p.value > 0.5]
        auto_approvals = [p for p in approvals if p.tags.get("approval_type") == "auto"]
        auto_approval_rate = len(auto_approvals) / len(approvals) if approvals else 0

        # Escalation metrics
        escalation_data = self._get_recent_metrics("escalations", cutoff_time)
        escalation_count = len(escalation_data)

        # Payment plan metrics
        payment_data = self._get_recent_metrics("payment_plans", cutoff_time)
        payment_plans_detected = len([p for p in payment_data if p.value > 0.5])

        return {
            "timeframe_hours": hours,
            "sms_metrics": {
                "received": sms_count,
                "rate_per_hour": sms_count / max(hours, 1),
            },
            "ai_metrics": {
                "responses": len(response_data),
                "avg_response_time_ms": round(avg_response_time, 2),
                "response_rate": len(response_data) / max(sms_count, 1),
            },
            "approval_metrics": {
                "total": len(approval_data),
                "approved": len(approvals),
                "auto_approval_rate": round(auto_approval_rate, 4),
            },
            "escalation_metrics": {
                "total": escalation_count,
                "rate_per_hour": escalation_count / max(hours, 1),
            },
            "payment_plan_metrics": {
                "detected": payment_plans_detected,
                "detection_rate": payment_plans_detected / max(sms_count, 1),
            },
        }

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """
        Get metrics formatted for dashboard consumption.

        Returns:
            Dashboard-ready metrics data
        """
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)

        # Last hour metrics
        last_hour = self.get_metrics_summary(hours=1)

        # Today's metrics
        today_data = self._get_metrics_for_timeframe(one_day_ago, now)

        # System health
        health_data = self._get_recent_metrics("system_health", one_hour_ago)
        service_health = {}
        for point in health_data:
            service = point.tags.get("service")
            if service:
                if service not in service_health:
                    service_health[service] = {"healthy": 0, "unhealthy": 0}
                if point.value > 0.5:
                    service_health[service]["healthy"] += 1
                else:
                    service_health[service]["unhealthy"] += 1

        return {
            "last_hour": {
                "sms_received": last_hour["sms_metrics"]["received"],
                "ai_responses": last_hour["ai_metrics"]["responses"],
                "auto_approval_rate": last_hour["approval_metrics"]["auto_approval_rate"],
                "avg_response_time_ms": last_hour["ai_metrics"]["avg_response_time_ms"],
                "escalations": last_hour["escalation_metrics"]["total"],
                "payment_plans": last_hour["payment_plan_metrics"]["detected"],
            },
            "today": {
                "total_messages": today_data.get("sms_count", 0),
                "escalations": today_data.get("escalation_count", 0),
                "payment_plans": today_data.get("payment_plan_count", 0),
                "approvals": today_data.get("approval_count", 0),
            },
            "system_health": service_health,
            "performance": {
                "avg_response_times": self._calculate_percentiles(
                    [p.value for p in self._get_recent_metrics("response_times", one_hour_ago)]
                ),
                "throughput": {
                    "requests_per_hour": last_hour["sms_metrics"]["rate_per_hour"] * 60 if last_hour["sms_metrics"]["rate_per_hour"] > 0 else 0,
                    "messages_per_minute": last_hour["sms_metrics"]["received"] / 60 if last_hour["sms_metrics"]["received"] > 0 else 0
                },
                "error_rates": {
                    "system_error_rate": 0.01,  # Would be calculated from actual error data
                    "service_failure_rate": 0.005  # Would be calculated from service failures
                },
                "resource_utilization": {
                    "cpu_usage": 0.45,  # Would be from actual monitoring
                    "memory_usage": 0.62,  # Would be from actual monitoring
                    "disk_usage": 0.35  # Would be from actual monitoring
                }
            }
        }

    def get_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus exposition format.

        Returns:
            Prometheus-formatted metrics string
        """
        metrics = []

        # Counters
        for name, value in self.counters.items():
            sanitized_name = name.replace("_", "_").replace("-", "_")
            metrics.append(f"# TYPE {sanitized_name} counter")
            metrics.append(f"{sanitized_name} {value}")

        # Gauges
        for name, value in self.gauges.items():
            sanitized_name = name.replace("_", "_").replace("-", "_")
            metrics.append(f"# TYPE {sanitized_name} gauge")
            metrics.append(f"{sanitized_name} {value}")

        # Recent histogram data
        for metric_name, points in self.histograms.items():
            if points:
                sanitized_name = metric_name.replace("_", "_").replace("-", "_")
                metrics.append(f"# TYPE {sanitized_name} histogram")

                # Simple histogram buckets
                sorted_points = sorted(list(points))
                metrics.append(f"{sanitized_name}_sum {sum(sorted_points)}")
                metrics.append(f"{sanitized_name}_count {len(sorted_points)}")

                # Add percentiles as quantiles
                percentiles = self._calculate_percentiles(sorted_points)
                for p_val, p_name in [(percentiles.get('p50', 0), '0.5'),
                                      (percentiles.get('p90', 0), '0.9'),
                                      (percentiles.get('p99', 0), '0.99')]:
                    quantile_label = f'{{"quantile": "{p_name}"}}'
                    metrics.append(f"{sanitized_name}_quantile{quantile_label} {p_val}")

        return "\n".join(metrics)

    def _get_recent_metrics(self, metric_name: str, since: datetime) -> List[TimeSeriesPoint]:
        """Get metrics points since the specified time."""
        return [point for point in self.metrics_storage.get(metric_name, [])
                if point.timestamp >= since]

    def _get_metrics_for_timeframe(self, start: datetime, end: datetime) -> Dict[str, int]:
        """Get aggregated metrics for a specific timeframe."""
        result = {}

        # SMS count
        sms_data = self._get_recent_metrics("sms_volume", start)
        result["sms_count"] = len([p for p in sms_data if p.timestamp <= end])

        # Escalation count
        escalation_data = self._get_recent_metrics("escalations", start)
        result["escalation_count"] = len([p for p in escalation_data if p.timestamp <= end])

        # Payment plan count
        payment_data = self._get_recent_metrics("payment_plans", start)
        result["payment_plan_count"] = len([p for p in payment_data if p.value > 0.5 and p.timestamp <= end])

        # Approval count
        approval_data = self._get_recent_metrics("approval_rates", start)
        result["approval_count"] = len([p for p in approval_data if p.value > 0.5 and p.timestamp <= end])

        return result

    def _calculate_percentiles(self, values: List[float]) -> Dict[str, float]:
        """Calculate percentiles for a list of values."""
        if not values:
            return {"p50": 0, "p90": 0, "p99": 0}

        sorted_values = sorted(values)
        n = len(sorted_values)

        def get_percentile(p: float) -> float:
            index = int(n * p / 100)
            if index >= n:
                index = n - 1
            return sorted_values[index]

        return {
            "p50": get_percentile(50),
            "p90": get_percentile(90),
            "p99": get_percentile(99),
        }

    def cleanup_old_metrics(self) -> None:
        """Remove metrics older than retention periods."""
        now = datetime.utcnow()

        for metric_name, retention_hours in self.retention_periods.items():
            cutoff_time = now - timedelta(hours=retention_hours)
            points = self.metrics_storage.get(metric_name, deque())

            # Remove old points
            while points and points[0].timestamp < cutoff_time:
                points.popleft()

            if points:
                self.metrics_storage[metric_name] = points

        logger.info("Old metrics cleaned up")

    def reset_metrics(self) -> None:
        """Reset all metrics (for testing)."""
        self.metrics_storage.clear()
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()

        logger.info("All metrics reset")


# Global metrics service instance
metrics_service = MetricsService()