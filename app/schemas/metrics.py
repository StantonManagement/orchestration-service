"""
Pydantic schemas for metrics API responses.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class MetricValue(BaseModel):
    """Single metric value with metadata."""
    value: float = Field(..., description="Metric value")
    timestamp: datetime = Field(..., description="Timestamp when metric was recorded")
    tags: Dict[str, str] = Field(default_factory=dict, description="Metric tags/labels")


class MetricSummary(BaseModel):
    """Summary statistics for a metric."""
    count: int = Field(..., description="Number of data points")
    sum: float = Field(..., description="Sum of all values")
    avg: float = Field(..., description="Average value")
    min: float = Field(..., description="Minimum value")
    max: float = Field(..., description="Maximum value")
    p50: float = Field(..., description="50th percentile")
    p90: float = Field(..., description="90th percentile")
    p99: float = Field(..., description="99th percentile")


class SMSMetrics(BaseModel):
    """SMS processing metrics."""
    received: int = Field(..., description="Number of SMS messages received")
    processed: int = Field(..., description="Number of SMS messages processed")
    failed: int = Field(..., description="Number of failed SMS processing attempts")
    rate_per_hour: float = Field(..., description="SMS processing rate per hour")


class AIMetrics(BaseModel):
    """AI response generation metrics."""
    responses: int = Field(..., description="Number of AI responses generated")
    avg_response_time_ms: float = Field(..., description="Average AI response time in milliseconds")
    avg_confidence: float = Field(..., description="Average confidence score")
    response_rate: float = Field(..., description="Response rate (responses / SMS received)")


class ApprovalMetrics(BaseModel):
    """Approval workflow metrics."""
    total: int = Field(..., description="Total approval decisions")
    approved: int = Field(..., description="Number of approved responses")
    rejected: int = Field(..., description="Number of rejected responses")
    auto_approval_rate: float = Field(..., description="Rate of automatic approvals")
    avg_approval_time_ms: float = Field(..., description="Average approval time in milliseconds")


class EscalationMetrics(BaseModel):
    """Escalation metrics."""
    total: int = Field(..., description="Total escalations")
    by_type: Dict[str, int] = Field(..., description="Escalations by type")
    by_severity: Dict[str, int] = Field(..., description="Escalations by severity")
    rate_per_hour: float = Field(..., description="Escalation rate per hour")
    avg_resolution_time_ms: float = Field(..., description="Average resolution time in milliseconds")


class PaymentPlanMetrics(BaseModel):
    """Payment plan detection metrics."""
    detected: int = Field(..., description="Number of payment plans detected")
    validated: int = Field(..., description="Number of payment plans validated")
    auto_approved: int = Field(..., description="Number of auto-approved payment plans")
    detection_rate: float = Field(..., description="Payment plan detection rate")
    validation_rate: float = Field(..., description="Payment plan validation rate")


class PerformanceMetrics(BaseModel):
    """Performance metrics."""
    avg_response_times: Dict[str, float] = Field(..., description="Average response times by operation")
    throughput: Dict[str, float] = Field(..., description="Throughput metrics")
    error_rates: Dict[str, float] = Field(..., description="Error rates by service/operation")
    resource_utilization: Dict[str, float] = Field(..., description="Resource utilization metrics")


class ServiceHealth(BaseModel):
    """Service health information."""
    healthy: int = Field(..., description="Number of healthy checks")
    unhealthy: int = Field(..., description="Number of unhealthy checks")
    availability: float = Field(..., description="Service availability (0.0-1.0)")
    response_time_ms: float = Field(..., description="Average response time in milliseconds")
    last_check: datetime = Field(..., description="Last health check timestamp")


class LastHourMetrics(BaseModel):
    """Metrics for the last hour."""
    sms_received: int = Field(..., description="SMS received in last hour")
    ai_responses: int = Field(..., description="AI responses in last hour")
    auto_approval_rate: float = Field(..., description="Auto approval rate in last hour")
    avg_response_time_ms: float = Field(..., description="Average response time in last hour")
    escalations: int = Field(..., description="Escalations in last hour")
    payment_plans: int = Field(..., description="Payment plans detected in last hour")


class TodayMetrics(BaseModel):
    """Metrics for today."""
    total_messages: int = Field(..., description="Total messages today")
    escalations: int = Field(..., description="Total escalations today")
    payment_plans: int = Field(..., description="Total payment plans today")
    approvals: int = Field(..., description="Total approvals today")


class MetricsTimeframe(BaseModel):
    """Metrics for a specific timeframe."""
    timeframe_hours: int = Field(..., description="Timeframe in hours")
    sms_metrics: SMSMetrics = Field(..., description="SMS metrics")
    ai_metrics: AIMetrics = Field(..., description="AI metrics")
    approval_metrics: ApprovalMetrics = Field(..., description="Approval metrics")
    escalation_metrics: EscalationMetrics = Field(..., description="Escalation metrics")
    payment_plan_metrics: PaymentPlanMetrics = Field(..., description="Payment plan metrics")


class DashboardMetrics(BaseModel):
    """Dashboard-ready metrics data."""
    last_hour: LastHourMetrics = Field(..., description="Last hour metrics")
    today: TodayMetrics = Field(..., description="Today's metrics")
    system_health: Dict[str, ServiceHealth] = Field(..., description="System health by service")
    performance: PerformanceMetrics = Field(..., description="Performance metrics")


class MetricsRequest(BaseModel):
    """Request for metrics with filtering options."""
    hours: Optional[int] = Field(default=1, ge=1, le=8760, description="Number of hours to look back (1-8760)")
    tenant_id: Optional[str] = Field(default=None, description="Filter by tenant ID")
    start_time: Optional[datetime] = Field(default=None, description="Start time filter")
    end_time: Optional[datetime] = Field(default=None, description="End time filter")
    metrics: Optional[List[str]] = Field(default=None, description="Specific metrics to include")


class MetricsResponse(BaseModel):
    """Comprehensive metrics response."""
    timeframe: MetricsTimeframe = Field(..., description="Time-based metrics")
    dashboard: DashboardMetrics = Field(..., description="Dashboard-ready metrics")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Response generation timestamp")
    filters_applied: Dict[str, Any] = Field(default_factory=dict, description="Applied filters")


class PrometheusMetricsResponse(BaseModel):
    """Prometheus-formatted metrics response."""
    metrics: str = Field(..., description="Prometheus-formatted metrics")
    content_type: str = Field(default="text/plain; version=0.0.4", description="Content type header")


class HealthCheckMetrics(BaseModel):
    """Health check specific metrics."""
    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status")
    response_time_ms: float = Field(..., description="Health check response time")
    last_check: datetime = Field(..., description="Last health check timestamp")
    uptime_seconds: Optional[float] = Field(default=None, description="Service uptime in seconds")


class CircuitBreakerMetrics(BaseModel):
    """Circuit breaker metrics."""
    service: str = Field(..., description="Service name")
    state: str = Field(..., description="Circuit breaker state (CLOSED, OPEN, HALF_OPEN)")
    failure_count: int = Field(..., description="Current failure count")
    success_count: int = Field(..., description="Current success count")
    last_failure: Optional[datetime] = Field(default=None, description="Last failure timestamp")
    last_success: Optional[datetime] = Field(default=None, description="Last success timestamp")


class ErrorRateMetrics(BaseModel):
    """Error rate metrics."""
    service: str = Field(..., description="Service name")
    error_type: str = Field(..., description="Type of error")
    count: int = Field(..., description="Error count")
    rate: float = Field(..., description="Error rate (errors / total requests)")
    time_window_hours: int = Field(..., description="Time window for rate calculation")


class ThroughputMetrics(BaseModel):
    """Throughput metrics."""
    operation: str = Field(..., description="Operation name")
    requests_per_minute: float = Field(..., description="Requests per minute")
    requests_per_hour: float = Field(..., description="Requests per hour")
    avg_processing_time_ms: float = Field(..., description="Average processing time")
    time_window_hours: int = Field(..., description="Time window for calculations")


class MetricAlert(BaseModel):
    """Metric alert definition."""
    metric_name: str = Field(..., description="Name of the metric")
    threshold: float = Field(..., description="Alert threshold")
    operator: str = Field(..., description="Comparison operator (>, <, >=, <=")
    severity: str = Field(..., description="Alert severity (low, medium, high, critical)")
    enabled: bool = Field(default=True, description="Whether alert is enabled")
    last_triggered: Optional[datetime] = Field(default=None, description="Last time alert was triggered")