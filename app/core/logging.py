"""
Structured logging configuration with correlation IDs.
"""
import time
import uuid
from typing import Any, Dict
import structlog


def add_correlation_id(
    logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add correlation ID to log events."""
    # In a real application, this would extract from request context
    # For now, we'll generate a simple correlation ID if not present
    if "correlation_id" not in event_dict:
        event_dict["correlation_id"] = str(uuid.uuid4())[:8]
    return event_dict


def add_timestamp(
    logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add timestamp to log events."""
    event_dict["timestamp"] = time.time()
    return event_dict


def setup_logging() -> None:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            add_timestamp,
            add_correlation_id,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
