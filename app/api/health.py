"""
Health check endpoints for the System Orchestrator Service.
"""
import time
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import settings
from app.core.logging import get_logger
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


@router.get("/health/dependencies")
async def dependencies_health_check(request: Request):
    """
    Health check endpoint for external service dependencies.

    Returns connectivity status for all external services.
    """
    logger.info(
        "Dependencies health check requested",
        correlation_id=request.headers.get("X-Correlation-ID"),
    )

    # Initialize service clients
    collections_client = CollectionsMonitorClient()
    sms_agent_client = SMSAgentClient()

    # Check external services in parallel
    try:
        collections_healthy = await collections_client.health_check()
    except Exception as e:
        logger.warning(
            "Collections Monitor health check failed",
            error=str(e),
            correlation_id=request.headers.get("X-Correlation-ID"),
        )
        collections_healthy = False

    try:
        sms_agent_healthy = await sms_agent_client.health_check()
    except Exception as e:
        logger.warning(
            "SMS Agent health check failed",
            error=str(e),
            correlation_id=request.headers.get("X-Correlation-ID"),
        )
        sms_agent_healthy = False

    # Other services not yet implemented
    response = DependenciesHealthResponse(
        collections_monitor=collections_healthy,
        sms_agent=sms_agent_healthy,
        notification_service=False,  # Not implemented yet
        supabase=False,  # Not implemented yet
        openai=False,  # Not implemented yet
    )

    logger.info(
        "Dependencies health check completed",
        collections_monitor=response.collections_monitor,
        sms_agent=response.sms_agent,
        correlation_id=request.headers.get("X-Correlation-ID"),
    )

    return response


@router.get("/health/dependencies/detailed")
async def dependencies_health_check_detailed(request: Request):
    """
    Detailed health check endpoint for external service dependencies.

    Returns detailed status including circuit breaker states.
    """
    logger.info(
        "Detailed dependencies health check requested",
        correlation_id=request.headers.get("X-Correlation-ID"),
    )

    # Initialize service clients
    collections_client = CollectionsMonitorClient()
    sms_agent_client = SMSAgentClient()

    # Get circuit breaker status
    collections_status = collections_client.get_circuit_breaker_status()
    sms_agent_status = sms_agent_client.get_circuit_breaker_status()

    # Perform health checks
    collections_healthy = await collections_client.health_check()
    sms_agent_healthy = await sms_agent_client.health_check()

    dependencies_status: Dict[str, Any] = {
        "collections_monitor": {
            "healthy": collections_healthy,
            "circuit_breaker": collections_status,
        },
        "sms_agent": {
            "healthy": sms_agent_healthy,
            "circuit_breaker": sms_agent_status,
        },
        "notification_service": {"healthy": False, "status": "not_implemented"},
        "supabase": {"healthy": False, "status": "not_implemented"},
        "openai": {"healthy": False, "status": "not_implemented"},
    }

    logger.info(
        "Detailed dependencies health check completed",
        dependencies_count=len(dependencies_status),
        correlation_id=request.headers.get("X-Correlation-ID"),
    )

    return dependencies_status
