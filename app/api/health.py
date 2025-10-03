"""
Health check endpoints for the System Orchestrator Service.
"""
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.core.logging import get_logger
from app.core.circuit_breaker import CircuitBreakerConfig, ServiceClient
from app.core.degradation import degradation_manager, DegradationMode
from app.services.collections_monitor import CollectionsMonitorClient
from app.services.sms_agent import SMSAgentClient

router = APIRouter()
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    uptime_seconds: float
    timestamp: datetime
    service_name: str


class DetailedHealthResponse(HealthResponse):
    """Detailed health check response model."""

    checks: dict


class DependenciesHealthResponse(BaseModel):
    """Dependencies health check response model."""

    collections_monitor: bool
    sms_agent: bool
    notification_service: bool
    supabase: bool
    openai: bool
    overall_status: str
    degradation_mode: str


class ServiceHealthDetail(BaseModel):
    """Detailed health information for a single service."""

    healthy: bool
    circuit_breaker_status: Optional[Dict[str, Any]] = None
    response_time: float = 0.0
    last_check: float = 0.0
    error_rate: float = 0.0
    fallback_available: bool = True


class DetailedDependenciesHealthResponse(BaseModel):
    """Detailed dependencies health check response model."""

    services: Dict[str, ServiceHealthDetail]
    overall_status: str
    degradation_mode: str
    queued_operations: int
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """
    Basic health check endpoint.

    Returns service status, version, and basic health indicators.
    """
    logger.info(
        "Health check requested", correlation_id=request.headers.get("X-Correlation-ID")
    )

    # Calculate uptime
    start_time = getattr(request.app.state, "start_time", time.time())
    uptime = time.time() - start_time

    response = HealthResponse(
        status="healthy",
        version=settings.version,
        uptime_seconds=uptime,
        timestamp=datetime.utcnow(),
        service_name=settings.app_name,
    )

    logger.info(
        "Health check completed",
        status=response.status,
        uptime_seconds=response.uptime_seconds,
        correlation_id=request.headers.get("X-Correlation-ID"),
    )

    return response


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(request: Request):
    """
    Detailed health check endpoint with additional diagnostics.

    Returns comprehensive health information including various system checks.
    """
    logger.info(
        "Detailed health check requested",
        correlation_id=request.headers.get("X-Correlation-ID"),
    )

    # Calculate uptime
    start_time = getattr(request.app.state, "start_time", time.time())
    uptime = time.time() - start_time

    # Basic health checks (can be expanded in future stories)
    checks = {
        "database": "not_implemented",  # Will be implemented in future stories
        "external_services": "not_implemented",  # Will be implemented in future stories
        "memory": "healthy",  # Basic check - could be enhanced with actual metrics
    }

    # Determine overall status
    overall_status = (
        "healthy"
        if all(status in ["healthy", "not_implemented"] for status in checks.values())
        else "unhealthy"
    )

    response = DetailedHealthResponse(
        status=overall_status,
        version=settings.version,
        uptime_seconds=uptime,
        timestamp=datetime.utcnow(),
        service_name=settings.app_name,
        checks=checks,
    )

    logger.info(
        "Detailed health check completed",
        status=response.status,
        uptime_seconds=response.uptime_seconds,
        checks=response.checks,
        correlation_id=request.headers.get("X-Correlation-ID"),
    )

    return response


async def check_service_health(service_name: str, health_check_func) -> tuple[bool, float]:
    """Check health of a single service with timing."""
    start_time = time.time()
    try:
        is_healthy = await health_check_func()
        response_time = time.time() - start_time
        return is_healthy, response_time
    except Exception as e:
        response_time = time.time() - start_time
        logger.warning(
            f"{service_name} health check failed",
            error=str(e),
            response_time=response_time,
            correlation_id=None,  # Will be set by caller
        )
        return False, response_time


@router.get("/health/dependencies", response_model=DependenciesHealthResponse)
async def dependencies_health_check(request: Request):
    """
    Health check endpoint for external service dependencies.

    Returns connectivity status for all external services.
    """
    correlation_id = request.headers.get("X-Correlation-ID")
    logger.info(
        "Dependencies health check requested",
        correlation_id=correlation_id,
    )

    # Initialize service clients
    collections_client = CollectionsMonitorClient()
    sms_agent_client = SMSAgentClient()

    # Check external services in parallel
    tasks = [
        check_service_health("Collections Monitor", collections_client.health_check),
        check_service_health("SMS Agent", sms_agent_client.health_check),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Extract results
    collections_healthy, collections_response_time = results[0] if not isinstance(results[0], Exception) else (False, 0.0)
    sms_agent_healthy, sms_response_time = results[1] if not isinstance(results[1], Exception) else (False, 0.0)

    # Update degradation manager with current service status
    degradation_manager.update_service_status(
        "collections_monitor",
        collections_healthy,
        circuit_breaker_open=not collections_healthy,
        response_time=collections_response_time,
    )

    degradation_manager.update_service_status(
        "sms_agent",
        sms_agent_healthy,
        circuit_breaker_open=not sms_agent_healthy,
        response_time=sms_response_time,
    )

    # For services not yet implemented, mark as False but check if fallback is available
    notification_service_available = False  # Not implemented yet
    supabase_available = False  # Not implemented yet
    openai_available = False  # Not implemented yet

    # Determine overall status
    services_healthy = sum([
        collections_healthy,
        sms_agent_healthy,
        notification_service_available,
        supabase_available,
        openai_available,
    ])

    if services_healthy >= 4:
        overall_status = "healthy"
    elif services_healthy >= 3:
        overall_status = "degraded"
    elif services_healthy >= 2:
        overall_status = "unhealthy"
    else:
        overall_status = "critical"

    response = DependenciesHealthResponse(
        collections_monitor=collections_healthy,
        sms_agent=sms_agent_healthy,
        notification_service=notification_service_available,
        supabase=supabase_available,
        openai=openai_available,
        overall_status=overall_status,
        degradation_mode=degradation_manager.current_mode.value,
    )

    logger.info(
        "Dependencies health check completed",
        collections_monitor=response.collections_monitor,
        sms_agent=response.sms_agent,
        overall_status=overall_status,
        degradation_mode=response.degradation_mode,
        correlation_id=correlation_id,
    )

    return response


@router.get("/health/dependencies/detailed", response_model=DetailedDependenciesHealthResponse)
async def dependencies_health_check_detailed(request: Request):
    """
    Detailed health check endpoint for external service dependencies.

    Returns detailed status including circuit breaker states, degradation mode, and metrics.
    """
    correlation_id = request.headers.get("X-Correlation-ID")
    logger.info(
        "Detailed dependencies health check requested",
        correlation_id=correlation_id,
    )

    # Initialize service clients
    collections_client = CollectionsMonitorClient()
    sms_agent_client = SMSAgentClient()

    # Check services in parallel with timing
    tasks = [
        check_service_health("Collections Monitor", collections_client.health_check),
        check_service_health("SMS Agent", sms_agent_client.health_check),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Extract results
    collections_healthy, collections_response_time = results[0] if not isinstance(results[0], Exception) else (False, 0.0)
    sms_agent_healthy, sms_response_time = results[1] if not isinstance(results[1], Exception) else (False, 0.0)

    # Get circuit breaker status
    collections_circuit_status = collections_client.get_circuit_breaker_status()
    sms_circuit_status = sms_agent_client.get_circuit_breaker_status()

    # Update degradation manager
    degradation_manager.update_service_status(
        "collections_monitor",
        collections_healthy,
        circuit_breaker_open=not collections_healthy,
        response_time=collections_response_time,
    )

    degradation_manager.update_service_status(
        "sms_agent",
        sms_agent_healthy,
        circuit_breaker_open=not sms_agent_healthy,
        response_time=sms_response_time,
    )

    # Build detailed service status
    services = {
        "collections_monitor": ServiceHealthDetail(
            healthy=collections_healthy,
            circuit_breaker_status=collections_circuit_status,
            response_time=collections_response_time,
            last_check=time.time(),
            error_rate=collections_circuit_status.get("metrics", {}).get("failure_rate", 0.0),
            fallback_available="collections_monitor" in degradation_manager.fallback_handlers,
        ),
        "sms_agent": ServiceHealthDetail(
            healthy=sms_agent_healthy,
            circuit_breaker_status=sms_circuit_status,
            response_time=sms_response_time,
            last_check=time.time(),
            error_rate=sms_circuit_status.get("metrics", {}).get("failure_rate", 0.0),
            fallback_available="sms_agent" in degradation_manager.fallback_handlers,
        ),
        "notification_service": ServiceHealthDetail(
            healthy=False,
            last_check=time.time(),
            fallback_available=False,  # Not implemented yet
        ),
        "supabase": ServiceHealthDetail(
            healthy=False,
            last_check=time.time(),
            fallback_available=False,  # Not implemented yet
        ),
        "openai": ServiceHealthDetail(
            healthy=False,
            last_check=time.time(),
            fallback_available=False,  # Not implemented yet
        ),
    }

    # Get degradation manager status
    service_health = degradation_manager.get_service_health()

    # Determine overall status
    healthy_count = sum(1 for service in services.values() if service.healthy)
    total_count = len(services)

    if healthy_count == total_count:
        overall_status = "healthy"
    elif healthy_count >= total_count * 0.7:
        overall_status = "degraded"
    elif healthy_count >= total_count * 0.4:
        overall_status = "unhealthy"
    else:
        overall_status = "critical"

    response = DetailedDependenciesHealthResponse(
        services=services,
        overall_status=overall_status,
        degradation_mode=degradation_manager.current_mode.value,
        queued_operations=len(degradation_manager.queued_operations),
        timestamp=datetime.utcnow(),
    )

    logger.info(
        "Detailed dependencies health check completed",
        overall_status=overall_status,
        degradation_mode=response.degradation_mode,
        healthy_services=healthy_count,
        total_services=total_count,
        queued_operations=response.queued_operations,
        correlation_id=correlation_id,
    )

    return response


@router.post("/health/dependencies/reset")
async def reset_dependencies_health(request: Request):
    """
    Reset circuit breakers and degradation manager.

    For administrative use only.
    """
    correlation_id = request.headers.get("X-Correlation-ID")
    logger.info(
        "Dependencies health reset requested",
        correlation_id=correlation_id,
    )

    # Reset degradation manager
    degradation_manager.reset()

    # Reset circuit breakers in service clients
    collections_client = CollectionsMonitorClient()
    sms_agent_client = SMSAgentClient()

    collections_client.circuit_breaker.reset()
    sms_agent_client.circuit_breaker.reset()

    logger.info(
        "Dependencies health reset completed",
        correlation_id=correlation_id,
    )

    return {
        "status": "reset_completed",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "All circuit breakers and degradation manager have been reset"
    }


@router.get("/health/degradation")
async def degradation_status_check(request: Request):
    """
    Get current degradation status and queue information.
    """
    correlation_id = request.headers.get("X-Correlation-ID")

    status = degradation_manager.get_service_health()

    logger.info(
        "Degradation status check requested",
        current_mode=status["current_mode"],
        correlation_id=correlation_id,
    )

    return status
