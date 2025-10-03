"""
Dependency injection for FastAPI application.

Provides factory functions for creating service instances with proper
dependency injection and configuration.
"""

from functools import lru_cache
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.circuit_breaker import ServiceClient
from app.services.escalation_service import EscalationService
from app.services.workflow_service import WorkflowService
from app.core.config import get_settings


def get_service_client(
    service_name: str,
    base_url: str,
    timeout_seconds: int = 30
) -> ServiceClient:
    """
    Create a service client with circuit breaker.

    Args:
        service_name: Name of the service for logging
        base_url: Base URL for the service
        timeout_seconds: Request timeout in seconds

    Returns:
        Configured ServiceClient instance
    """
    return ServiceClient(
        service_name=service_name,
        base_url=base_url,
        timeout_seconds=timeout_seconds
    )


@lru_cache()
def get_notification_service_client() -> ServiceClient:
    """Get notification service client."""
    settings = get_settings()
    return get_service_client(
        service_name="notification_service",
        base_url=settings.notification_service_url,
        timeout_seconds=30
    )


@lru_cache()
def get_sms_agent_client() -> ServiceClient:
    """Get SMS agent service client."""
    settings = get_settings()
    return get_service_client(
        service_name="sms_agent_service",
        base_url=settings.sms_agent_service_url,
        timeout_seconds=30
    )


@lru_cache()
def get_collections_monitor_client() -> ServiceClient:
    """Get collections monitor service client."""
    settings = get_settings()
    return get_service_client(
        service_name="collections_monitor_service",
        base_url=settings.collections_monitor_service_url,
        timeout_seconds=30
    )


def get_escalation_service(
    db: Session = Depends(get_db),
    notification_client: ServiceClient = Depends(get_notification_service_client),
    sms_agent_client: ServiceClient = Depends(get_sms_agent_client),
    collections_monitor_client: ServiceClient = Depends(get_collections_monitor_client)
) -> EscalationService:
    """
    Get escalation service with all dependencies injected.

    Args:
        db: Database session
        notification_client: Notification service client
        sms_agent_client: SMS agent service client
        collections_monitor_client: Collections monitor service client

    Returns:
        Configured EscalationService instance
    """
    return EscalationService(
        notification_client=notification_client,
        sms_agent_client=sms_agent_client,
        collections_monitor_client=collections_monitor_client
    )


def get_workflow_service(
    db: Session = Depends(get_db)
) -> WorkflowService:
    """
    Get workflow service with database dependency.

    Args:
        db: Database session

    Returns:
        Configured WorkflowService instance
    """
    return WorkflowService(db_session=db)