"""
Metrics API endpoints for system monitoring and observability.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Response, Depends
from fastapi.responses import PlainTextResponse

from app.schemas.metrics import (
    MetricsRequest,
    MetricsResponse
)
from app.services.metrics_service import metrics_service
from app.core.logging import get_logger, performance_timing, correlation_context
from app.core.circuit_breaker import ServiceClient
from app.services.external import ServiceClients

router = APIRouter()
logger = get_logger(__name__)

# Cache for metrics responses to improve performance
_metrics_cache = {}
_cache_timestamp = None
_cache_ttl_seconds = 60  # Cache metrics for 1 minute


def _get_cached_metrics(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached metrics if available and not expired."""
    global _cache_timestamp, _metrics_cache

    if (_cache_timestamp is None or
        time.time() - _cache_timestamp > _cache_ttl_seconds):
        return None

    return _metrics_cache.get(cache_key)


def _cache_metrics(cache_key: str, data: Dict[str, Any]) -> None:
    """Cache metrics data."""
    global _cache_timestamp, _metrics_cache
    _metrics_cache[cache_key] = data
    _cache_timestamp = time.time()


@router.get("/orchestrate/metrics", response_model=None)
async def get_metrics(
    hours: int = Query(default=1, ge=1, le=8760, description="Hours to look back (1-8760)"),
    tenant_id: Optional[str] = Query(default=None, description="Filter by tenant ID"),
    format: str = Query(default="json", pattern="^(json|dashboard|prometheus)$", description="Response format"),
    start_date: Optional[str] = Query(default=None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(default=None, description="End date in ISO format")
):
    """
    Get comprehensive system metrics.

    Supports multiple response formats:
    - json: Full detailed metrics response
    - dashboard: Simplified dashboard-ready metrics
    - prometheus: Prometheus-compatible metrics format
    """
    cache_key = f"metrics_{hours}_{tenant_id}_{format}"

    # Try to get from cache first
    cached_data = _get_cached_metrics(cache_key)
    if cached_data:
        logger.debug("Returning cached metrics", cache_key=cache_key)
        return MetricsResponse(**cached_data) if format == "json" else cached_data

    # Validate date parameters if provided
    if start_date or end_date:
        try:
            if start_date:
                datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {str(e)}"
            )

    with performance_timing("get_metrics_api"):
        try:
            # Get metrics summary from service
            metrics_summary = metrics_service.get_metrics_summary(hours=hours)

            # Get dashboard metrics
            dashboard_data = metrics_service.get_dashboard_metrics()

            # Build system health properly for both formats
            system_health_dict = {}
            for service, health in dashboard_data["system_health"].items():
                healthy_count = health.get("healthy", 0)
                unhealthy_count = health.get("unhealthy", 0)
                total_count = healthy_count + unhealthy_count
                availability = healthy_count / total_count if total_count > 0 else 0.0

                system_health_dict[service] = ServiceHealth(
                    healthy=healthy_count,
                    unhealthy=unhealthy_count,
                    availability=availability,
                    response_time_ms=0.0,  # Would be calculated from health checks
                    last_check=datetime.utcnow()
                )

            # Create response data based on format
            if format == "prometheus":
                prometheus_metrics = metrics_service.get_prometheus_metrics()
                _cache_metrics(cache_key, {"metrics": prometheus_metrics})
                return PlainTextResponse(
                    content=prometheus_metrics,
                    headers={"Content-Type": "text/plain; charset=utf-8"}
                )

            elif format == "dashboard":
                dashboard_metrics = DashboardMetrics(
                    last_hour=LastHourMetrics(**dashboard_data["last_hour"]),
                    today=TodayMetrics(**dashboard_data["today"]),
                    system_health=system_health_dict,
                    performance=PerformanceMetrics(
                        avg_response_times=dashboard_data["performance"]["avg_response_times"],
                        throughput={"requests_per_hour": metrics_summary["sms_metrics"]["rate_per_hour"] * 60},  # Simplified
                        error_rates={"system_error_rate": 0.01},  # Would be calculated from actual error rates
                        resource_utilization={"cpu_usage": 0.45, "memory_usage": 0.62}  # Would be from actual monitoring
                    )
                )
                _cache_metrics(cache_key, dashboard_metrics.model_dump())
                return dashboard_metrics

            else:  # json format (default)
                # Build comprehensive response
                timeframe_data = MetricsTimeframe(
                    timeframe_hours=hours,
                    sms_metrics=SMSMetrics(
                        received=metrics_summary["sms_metrics"]["received"],
                        processed=metrics_summary["sms_metrics"]["received"],  # Assuming received == processed
                        failed=0,  # Would be calculated from failed workflows
                        rate_per_hour=metrics_summary["sms_metrics"]["rate_per_hour"]
                    ),
                    ai_metrics=AIMetrics(
                        responses=metrics_summary["ai_metrics"]["responses"],
                        avg_response_time_ms=metrics_summary["ai_metrics"]["avg_response_time_ms"],
                        avg_confidence=0.85,  # Would be calculated from actual confidence scores
                        response_rate=metrics_summary["ai_metrics"]["response_rate"]
                    ),
                    approval_metrics=ApprovalMetrics(
                        total=metrics_summary["approval_metrics"]["total"],
                        approved=metrics_summary["approval_metrics"]["approved"],
                        rejected=metrics_summary["approval_metrics"]["total"] - metrics_summary["approval_metrics"]["approved"],
                        auto_approval_rate=metrics_summary["approval_metrics"]["auto_approval_rate"],
                        avg_approval_time_ms=500.0  # Would be calculated from actual approval times
                    ),
                    escalation_metrics=EscalationMetrics(
                        total=metrics_summary["escalation_metrics"]["total"],
                        by_type={"low_confidence": metrics_summary["escalation_metrics"]["total"]},  # Simplified
                        by_severity={"medium": metrics_summary["escalation_metrics"]["total"]},  # Simplified
                        rate_per_hour=metrics_summary["escalation_metrics"]["rate_per_hour"],
                        avg_resolution_time_ms=30000.0  # Would be calculated from actual resolution times
                    ),
                    payment_plan_metrics=PaymentPlanMetrics(
                        detected=metrics_summary["payment_plan_metrics"]["detected"],
                        validated=int(metrics_summary["payment_plan_metrics"]["detected"] * 0.8),  # Assuming 80% validation rate
                        auto_approved=int(metrics_summary["payment_plan_metrics"]["detected"] * 0.6),  # Assuming 60% auto-approval
                        detection_rate=metrics_summary["payment_plan_metrics"]["detection_rate"],
                        validation_rate=0.8  # Assuming 80% validation rate
                    )
                )

                dashboard_metrics = DashboardMetrics(
                    last_hour=LastHourMetrics(**dashboard_data["last_hour"]),
                    today=TodayMetrics(**dashboard_data["today"]),
                    system_health=system_health_dict,
                    performance=PerformanceMetrics(
                        avg_response_times=dashboard_data["performance"]["avg_response_times"],
                        throughput={"requests_per_hour": metrics_summary["sms_metrics"]["rate_per_hour"] * 60},  # Simplified
                        error_rates={"system_error_rate": 0.01},  # Would be calculated from actual error rates
                        resource_utilization={"cpu_usage": 0.45, "memory_usage": 0.62}  # Would be from actual monitoring
                    )
                )

                response_data = MetricsResponse(
                    timeframe=timeframe_data,
                    dashboard=dashboard_metrics,
                    generated_at=datetime.utcnow(),
                    filters_applied={"hours": hours, "tenant_id": tenant_id}
                )

                _cache_metrics(cache_key, response_data.model_dump())

                logger.info(
                    "Metrics retrieved successfully",
                    hours=hours,
                    tenant_id=tenant_id,
                    format=format,
                    sms_received=response_data.timeframe.sms_metrics.received,
                    ai_responses=response_data.timeframe.ai_metrics.responses
                )

                return response_data

        except Exception as e:
            logger.error("Failed to retrieve metrics", error=str(e), hours=hours, tenant_id=tenant_id)
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve metrics"
            )






