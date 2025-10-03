"""
Enhanced structured logging configuration with correlation IDs and performance monitoring.
"""
import time
import uuid
import threading
from typing import Any, Dict, Optional, List
from contextlib import contextmanager
from contextvars import ContextVar
import structlog

# Context variables for request-scoped data
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)
workflow_id_var: ContextVar[Optional[str]] = ContextVar('workflow_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)

# Performance timing context
performance_context = threading.local()


def add_correlation_id(
    logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add correlation ID to log events."""
    # Try to get from context variable first
    correlation_id = correlation_id_var.get()
    if not correlation_id:
        # Generate one if not present
        correlation_id = str(uuid.uuid4())[:8]
        correlation_id_var.set(correlation_id)

    event_dict["correlation_id"] = correlation_id
    return event_dict


def add_request_context(
    logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add request context information to log events."""
    tenant_id = tenant_id_var.get()
    if tenant_id:
        event_dict["tenant_id"] = tenant_id

    workflow_id = workflow_id_var.get()
    if workflow_id:
        event_dict["workflow_id"] = workflow_id

    user_id = user_id_var.get()
    if user_id:
        event_dict["user_id"] = user_id

    return event_dict


def add_service_context(
    logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add service context to log events."""
    event_dict["service"] = "system-orchestrator"
    event_dict["version"] = "1.0.0"
    event_dict["environment"] = "development"
    return event_dict


def add_timestamp(
    logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add ISO format timestamp to log events."""
    event_dict["timestamp"] = time.time()
    iso_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    event_dict["iso_timestamp"] = time.strftime(iso_format)
    return event_dict


def add_performance_context(
    logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add performance timing context to log events."""
    if hasattr(performance_context, 'operation_start'):
        duration = time.time() - performance_context.operation_start
        event_dict["operation_duration_ms"] = round(duration * 1000, 2)

    if hasattr(performance_context, 'operation_name'):
        event_dict["operation"] = performance_context.operation_name

    return event_dict


class LogSampler:
    """Log sampler for high-volume scenarios."""

    def __init__(self, sample_rate: float = 1.0):
        """
        Initialize sampler.

        Args:
            sample_rate: Rate between 0.0 and 1.0 for sampling logs
        """
        self.sample_rate = max(0.0, min(1.0, sample_rate))

    def should_log(self, level: str = "INFO") -> bool:
        """Determine if a log event should be sampled."""
        # Always log errors and warnings
        if level in ["ERROR", "WARNING", "CRITICAL"]:
            return True

        # Sample other levels based on rate
        if self.sample_rate >= 1.0:
            return True
        elif self.sample_rate <= 0.0:
            return False
        else:
            import random
            return random.random() < self.sample_rate


# Global sampler instance
_log_sampler = LogSampler()


def add_sampling_filter(
    logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add sampling information to log events."""
    level = event_dict.get("level", "INFO")
    should_log = _log_sampler.should_log(level)

    if should_log:
        event_dict["sampled"] = True
    else:
        # Return None to drop the log event
        return None

    return event_dict


def setup_logging(sample_rate: float = 1.0) -> None:
    """
    Configure enhanced structured logging.

    Args:
        sample_rate: Sampling rate for high-volume logs (0.0-1.0)
    """
    global _log_sampler
    _log_sampler = LogSampler(sample_rate)

    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        add_timestamp,
        add_service_context,
        add_request_context,
        add_correlation_id,
        add_performance_context,
        add_sampling_filter,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Filter out None values from sampling
    def filter_none(logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        return event_dict if event_dict is not None else {}

    processors.append(filter_none)
    processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def get_request_logger() -> structlog.stdlib.BoundLogger:
    """Get a request logger instance."""
    return structlog.get_logger("request")


def get_business_logger() -> structlog.stdlib.BoundLogger:
    """Get a business event logger instance."""
    return structlog.get_logger("business")


def get_performance_logger() -> structlog.stdlib.BoundLogger:
    """Get a performance logger instance."""
    return structlog.get_logger("performance")


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID in the current context."""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get correlation ID from current context."""
    return correlation_id_var.get()


def set_tenant_id(tenant_id: str) -> None:
    """Set tenant ID in the current context."""
    tenant_id_var.set(tenant_id)


def set_workflow_id(workflow_id: str) -> None:
    """Set workflow ID in the current context."""
    workflow_id_var.set(workflow_id)


def set_user_id(user_id: str) -> None:
    """Set user ID in the current context."""
    user_id_var.set(user_id)


@contextmanager
def correlation_context(correlation_id: str = None, tenant_id: str = None,
                       workflow_id: str = None, user_id: str = None):
    """
    Context manager for setting correlation context.

    Args:
        correlation_id: Correlation ID for the request
        tenant_id: Tenant ID
        workflow_id: Workflow ID
        user_id: User ID
    """
    # Store original values
    original_correlation_id = correlation_id_var.get()
    original_tenant_id = tenant_id_var.get()
    original_workflow_id = workflow_id_var.get()
    original_user_id = user_id_var.get()

    try:
        # Set new values
        if correlation_id:
            set_correlation_id(correlation_id)
        if tenant_id:
            set_tenant_id(tenant_id)
        if workflow_id:
            set_workflow_id(workflow_id)
        if user_id:
            set_user_id(user_id)

        yield

    finally:
        # Restore original values
        if original_correlation_id:
            set_correlation_id(original_correlation_id)
        if original_tenant_id:
            set_tenant_id(original_tenant_id)
        if original_workflow_id:
            set_workflow_id(original_workflow_id)
        if original_user_id:
            set_user_id(original_user_id)


@contextmanager
def performance_timing(operation_name: str):
    """
    Context manager for timing operations.

    Args:
        operation_name: Name of the operation being timed
    """
    start_time = time.time()
    performance_context.operation_name = operation_name
    performance_context.operation_start = start_time

    logger = get_performance_logger()
    logger.info("Operation started", operation=operation_name)

    try:
        yield

    finally:
        duration = time.time() - start_time
        duration_ms = round(duration * 1000, 2)

        logger.info(
            "Operation completed",
            operation=operation_name,
            duration_ms=duration_ms,
            duration_seconds=round(duration, 4)
        )

        # Clean up performance context
        if hasattr(performance_context, 'operation_name'):
            delattr(performance_context, 'operation_name')
        if hasattr(performance_context, 'operation_start'):
            delattr(performance_context, 'operation_start')


def log_business_event(event_type: str, **kwargs):
    """
    Log a structured business event.

    Args:
        event_type: Type of business event
        **kwargs: Additional event data
    """
    logger = get_business_logger()
    logger.info("Business event", event_type=event_type, **kwargs)


def log_performance_metrics(operation: str, duration_ms: float, **kwargs):
    """Log performance metrics."""
    logger = get_performance_logger()
    logger.info(
        "Performance metrics",
        operation=operation,
        duration_ms=duration_ms,
        **kwargs,
        event="performance_metrics"
    )


def log_request_start(logger, request_data: Dict[str, Any]):
    """Log the start of a request with context information."""
    logger.info(
        "Request started",
        method=request_data.get("method"),
        path=request_data.get("path"),
        user_agent=request_data.get("headers", {}).get("user-agent"),
        content_type=request_data.get("headers", {}).get("content-type"),
        event="request_start"
    )


def log_request_end(logger, response_data: Dict[str, Any]):
    """Log the end of a request with response information."""
    logger.info(
        "Request completed",
        status_code=response_data.get("status_code"),
        response_size=response_data.get("response_size"),
        duration_ms=response_data.get("duration_ms"),
        event="request_end"
    )


def log_error_with_context(logger, error: Exception, context: Dict[str, Any] = None):
    """Log an error with additional context information."""
    logger.error(
        "Error occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        context=context or {},
        event="error"
    )


def log_structured_format(logger, level: str, message: str, **kwargs):
    """Log a message in structured format with additional context."""
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, **kwargs, event="structured_log")


def log_filtering(logger, level: str, message: str, filters: Dict[str, Any] = None):
    """Log with filtering capabilities."""
    if filters:
        # Apply filtering logic here
        filtered_kwargs = {k: v for k, v in filters.items() if v is not None}
        getattr(logger, level.lower())(message, **filtered_kwargs, event="filtered_log")
    else:
        getattr(logger, level.lower())(message, event="filtered_log")


def log_aggregation(logger, metrics: Dict[str, Any]):
    """Log aggregated metrics."""
    logger.info("Metrics aggregated", **metrics, event="aggregation")


def log_middleware_integration(logger, middleware_name: str, action: str, **kwargs):
    """Log middleware integration events."""
    logger.info(f"Middleware {action}", middleware=middleware_name, **kwargs, event="middleware")


def log_error_stack_traces(logger, error: Exception, include_stack: bool = True):
    """Log error with optional stack traces."""
    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "include_stack": include_stack,
        "event": "error_stack_trace"
    }

    if include_stack:
        import traceback
        error_data["stack_trace"] = traceback.format_exc()

    logger.error("Error with stack trace", **error_data)


def configure_logging_settings(sample_rate: float = 1.0, log_level: str = "INFO"):
    """Configure logging settings dynamically."""
    setup_logging(sample_rate=sample_rate)
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            add_timestamp,
            add_correlation_id,
            add_request_context,
            add_service_context,
            add_performance_context,
            add_sampling_filter(sample_rate),
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logger = get_logger(__name__)
    logger.info("Logging configuration updated", sample_rate=sample_rate, log_level=log_level, event="config_updated")


class RequestTracer:
    """Request tracer for distributed tracing across service boundaries."""

    def __init__(self):
        self.trace_stack = []

    def start_trace(self, operation: str, service: str = None, **context):
        """Start a new trace segment."""
        trace_id = str(uuid.uuid4())[:16]
        span_id = str(uuid.uuid4())[:8]

        trace_segment = {
            "trace_id": trace_id,
            "span_id": span_id,
            "operation": operation,
            "service": service or "system-orchestrator",
            "start_time": time.time(),
            "context": context,
            "parent_span": self.trace_stack[-1]["span_id"] if self.trace_stack else None
        }

        self.trace_stack.append(trace_segment)

        logger = get_logger("tracer")
        logger.info("Trace started", **trace_segment)

        return trace_id, span_id

    def end_trace(self, success: bool = True, error: str = None):
        """End the current trace segment."""
        if not self.trace_stack:
            return

        trace_segment = self.trace_stack.pop()
        duration = time.time() - trace_segment["start_time"]
        duration_ms = round(duration * 1000, 2)

        trace_segment.update({
            "duration_ms": duration_ms,
            "success": success,
            "error": error,
            "end_time": time.time()
        })

        logger = get_logger("tracer")
        logger.info("Trace completed", **trace_segment)

    @contextmanager
    def trace(self, operation: str, service: str = None, **context):
        """Context manager for tracing operations."""
        trace_id, span_id = self.start_trace(operation, service, **context)

        try:
            yield trace_id, span_id
            self.end_trace(success=True)

        except Exception as e:
            self.end_trace(success=False, error=str(e))
            raise


# Global tracer instance
request_tracer = RequestTracer()
