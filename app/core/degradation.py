"""
Graceful degradation strategies for external service failures.
"""
import asyncio
import time
from enum import Enum
from typing import Any, Dict, Optional, List, Callable, Union
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger(__name__)


class DegradationMode(Enum):
    """Degradation modes for service availability."""

    FULL = "full"  # All services available
    PARTIAL = "partial"  # Some services unavailable
    READ_ONLY = "read_only"  # Write operations queued
    OFFLINE = "offline"  # All operations queued
    EMERGENCY = "emergency"  # Minimal functionality


@dataclass
class ServiceStatus:
    """Status of an external service."""

    name: str
    available: bool = True
    last_check: float = field(default_factory=time.time)
    circuit_breaker_open: bool = False
    fallback_available: bool = True
    response_time: float = 0.0
    error_rate: float = 0.0
    degradation_level: float = 0.0  # 0.0 = full, 1.0 = completely degraded


@dataclass
class FallbackResponse:
    """Fallback response for degraded service operations."""

    success: bool
    data: Any = None
    message: str = ""
    fallback_used: str = ""
    queued: bool = False
    retry_after: Optional[float] = None


class DegradationManager:
    """Manages graceful degradation strategies for external services."""

    def __init__(self):
        self.service_status: Dict[str, ServiceStatus] = {}
        self.current_mode = DegradationMode.FULL
        self.queued_operations: List[Dict[str, Any]] = []
        self.fallback_handlers: Dict[str, Callable] = {}
        self.degradation_callbacks: List[Callable] = []

        # Initialize default services
        self._initialize_default_services()

        logger.info("Degradation manager initialized", mode=self.current_mode.value)

    def _initialize_default_services(self) -> None:
        """Initialize default external services."""
        default_services = [
            "collections_monitor",
            "sms_agent",
            "notification_service",
            "openai",
            "supabase",
        ]

        for service_name in default_services:
            self.service_status[service_name] = ServiceStatus(name=service_name)

    def register_service(self, service_name: str, fallback_handler: Optional[Callable] = None) -> None:
        """Register a new service for degradation management."""
        if service_name not in self.service_status:
            self.service_status[service_name] = ServiceStatus(name=service_name)

        if fallback_handler:
            self.fallback_handlers[service_name] = fallback_handler

        logger.info("Service registered for degradation", service=service_name)

    def update_service_status(
        self,
        service_name: str,
        available: bool,
        circuit_breaker_open: bool = False,
        response_time: float = 0.0,
        error_rate: float = 0.0,
    ) -> None:
        """Update service status and recalculate degradation mode."""
        if service_name not in self.service_status:
            self.register_service(service_name)

        status = self.service_status[service_name]
        status.available = available
        status.last_check = time.time()
        status.circuit_breaker_open = circuit_breaker_open
        status.response_time = response_time
        status.error_rate = error_rate

        # Calculate degradation level
        if not available or circuit_breaker_open:
            status.degradation_level = 1.0
        elif error_rate > 0.5:
            status.degradation_level = 0.8
        elif error_rate > 0.2:
            status.degradation_level = 0.5
        elif response_time > 5.0:
            status.degradation_level = 0.3
        else:
            status.degradation_level = 0.1 * error_rate

        # Recalculate overall degradation mode
        self._recalculate_degradation_mode()

        logger.info(
            "Service status updated",
            service=service_name,
            available=available,
            degradation_level=status.degradation_level,
            current_mode=self.current_mode.value,
        )

    def _recalculate_degradation_mode(self) -> None:
        """Recalculate overall degradation mode based on service statuses."""
        if not self.service_status:
            return

        # Count critical services
        critical_services = ["collections_monitor", "sms_agent", "supabase"]
        critical_down = sum(
            1 for service in critical_services
            if self.service_status.get(service, ServiceStatus(service)).degradation_level > 0.8
        )

        # Count all services
        total_services = len(self.service_status)
        severely_degraded = sum(
            1 for status in self.service_status.values()
            if status.degradation_level > 0.8
        )

        # Determine mode
        if critical_down >= 2 or severely_degraded >= total_services * 0.7:
            new_mode = DegradationMode.EMERGENCY
        elif critical_down >= 1 or severely_degraded >= total_services * 0.5:
            new_mode = DegradationMode.OFFLINE
        elif severely_degraded >= total_services * 0.3:
            new_mode = DegradationMode.READ_ONLY
        elif severely_degraded > 0:
            new_mode = DegradationMode.PARTIAL
        else:
            new_mode = DegradationMode.FULL

        if new_mode != self.current_mode:
            old_mode = self.current_mode
            self.current_mode = new_mode
            self._notify_degradation_change(old_mode, new_mode)

    def _notify_degradation_change(self, old_mode: DegradationMode, new_mode: DegradationMode) -> None:
        """Notify callbacks about degradation mode change."""
        logger.warning(
            "Degradation mode changed",
            old_mode=old_mode.value,
            new_mode=new_mode.value,
        )

        for callback in self.degradation_callbacks:
            try:
                callback(old_mode, new_mode)
            except Exception as e:
                logger.error(
                    "Error in degradation callback",
                    error=str(e),
                )

    def can_execute_operation(
        self,
        service_name: str,
        operation_type: str = "read"
    ) -> tuple[bool, Optional[FallbackResponse]]:
        """Check if operation can be executed given current degradation mode."""

        if self.current_mode == DegradationMode.EMERGENCY:
            # Only emergency operations allowed
            if operation_type == "emergency":
                return True, None
            else:
                return False, FallbackResponse(
                    success=False,
                    message="Service in emergency mode - only critical operations allowed",
                    fallback_used="emergency_only",
                )

        elif self.current_mode == DegradationMode.OFFLINE:
            # All operations queued
            return False, FallbackResponse(
                success=False,
                message="Service offline - operation queued for later processing",
                fallback_used="offline_queue",
                queued=True,
            )

        elif self.current_mode == DegradationMode.READ_ONLY:
            # Only read operations allowed
            if operation_type == "write":
                return False, FallbackResponse(
                    success=False,
                    message="Service in read-only mode - write operation queued",
                    fallback_used="read_only_queue",
                    queued=True,
                )

        # Check specific service availability
        if service_name in self.service_status:
            status = self.service_status[service_name]

            if not status.available or status.circuit_breaker_open:
                # Try fallback
                if service_name in self.fallback_handlers:
                    try:
                        fallback_result = self.fallback_handlers[service_name]()
                        return True, FallbackResponse(
                            success=True,
                            data=fallback_result,
                            message="Using fallback response",
                            fallback_used=service_name,
                        )
                    except Exception as e:
                        logger.error(
                            "Fallback handler failed",
                            service=service_name,
                            error=str(e),
                        )

                return False, FallbackResponse(
                    success=False,
                    message=f"Service '{service_name}' unavailable",
                    fallback_used="none",
                )

        return True, None

    def queue_operation(
        self,
        service_name: str,
        operation: str,
        data: Dict[str, Any],
        priority: int = 0
    ) -> str:
        """Queue an operation for later processing."""
        operation_id = f"{service_name}_{int(time.time() * 1000)}"

        queued_op = {
            "id": operation_id,
            "service": service_name,
            "operation": operation,
            "data": data,
            "priority": priority,
            "timestamp": time.time(),
            "attempts": 0,
        }

        self.queued_operations.append(queued_op)

        # Sort by priority (higher first)
        self.queued_operations.sort(key=lambda x: x["priority"], reverse=True)

        logger.info(
            "Operation queued",
            operation_id=operation_id,
            service=service_name,
            operation=operation,
            queue_size=len(self.queued_operations),
        )

        return operation_id

    async def process_queued_operations(self, max_operations: int = 10) -> int:
        """Process queued operations that can now be executed."""
        processed = 0
        remaining_operations = []

        for operation in self.queued_operations[:max_operations]:
            service_name = operation["service"]
            operation_type = operation["data"].get("type", "read")

            can_execute, fallback = self.can_execute_operation(service_name, operation_type)

            if can_execute:
                try:
                    # Here you would execute the actual operation
                    # For now, we'll just log and mark as processed
                    logger.info(
                        "Processing queued operation",
                        operation_id=operation["id"],
                        service=service_name,
                    )
                    processed += 1

                except Exception as e:
                    logger.error(
                        "Failed to process queued operation",
                        operation_id=operation["id"],
                        error=str(e),
                    )
                    operation["attempts"] += 1
                    if operation["attempts"] < 3:
                        remaining_operations.append(operation)
            else:
                # Can't execute yet, keep in queue
                remaining_operations.append(operation)

        # Update queued operations
        self.queued_operations = remaining_operations + self.queued_operations[max_operations:]

        if processed > 0:
            logger.info(
                "Processed queued operations",
                processed=processed,
                remaining=len(self.queued_operations),
            )

        return processed

    def get_service_health(self) -> Dict[str, Any]:
        """Get comprehensive service health information."""
        return {
            "current_mode": self.current_mode.value,
            "services": {
                name: {
                    "available": status.available,
                    "degradation_level": status.degradation_level,
                    "circuit_breaker_open": status.circuit_breaker_open,
                    "response_time": status.response_time,
                    "error_rate": status.error_rate,
                    "last_check": status.last_check,
                }
                for name, status in self.service_status.items()
            },
            "queued_operations": len(self.queued_operations),
            "fallback_handlers": list(self.fallback_handlers.keys()),
        }

    def add_degradation_callback(self, callback: Callable) -> None:
        """Add callback for degradation mode changes."""
        self.degradation_callbacks.append(callback)

    def reset(self) -> None:
        """Reset all service statuses and clear queued operations."""
        for status in self.service_status.values():
            status.available = True
            status.circuit_breaker_open = False
            status.degradation_level = 0.0
            status.response_time = 0.0
            status.error_rate = 0.0

        self.queued_operations.clear()
        self.current_mode = DegradationMode.FULL

        logger.info("Degradation manager reset")


# Global degradation manager instance
degradation_manager = DegradationManager()


# Fallback handlers for specific services
def collections_monitor_fallback() -> Dict[str, Any]:
    """Fallback for Collections Monitor service."""
    return {
        "tenant_id": "unknown",
        "account_balance": 0.0,
        "payment_history": [],
        "fallback": True,
    }


def sms_agent_fallback() -> Dict[str, Any]:
    """Fallback for SMS Agent service."""
    return {
        "message_id": f"fallback_{int(time.time())}",
        "status": "queued",
        "fallback": True,
    }


def notification_service_fallback() -> Dict[str, Any]:
    """Fallback for Notification Service service."""
    return {
        "notification_id": f"fallback_{int(time.time())}",
        "status": "logged_for_manual_review",
        "fallback": True,
    }


def openai_fallback() -> Dict[str, Any]:
    """Fallback for OpenAI service."""
    return {
        "response": "I'm sorry, I'm currently experiencing technical difficulties. Please try again later or contact support.",
        "confidence": 0.1,
        "fallback": True,
    }


# Register fallback handlers
degradation_manager.fallback_handlers.update({
    "collections_monitor": collections_monitor_fallback,
    "sms_agent": sms_agent_fallback,
    "notification_service": notification_service_fallback,
    "openai": openai_fallback,
})