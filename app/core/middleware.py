"""
FastAPI middleware for correlation ID propagation and request tracing.
"""
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import (
    get_logger,
    set_correlation_id,
    get_correlation_id,
    set_tenant_id,
    set_workflow_id,
    set_user_id,
    correlation_context,
    performance_timing,
    request_tracer,
    log_business_event
)

logger = get_logger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add correlation ID."""
        # Extract correlation ID from headers or generate new one
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())[:8]

        # Extract other context from headers
        tenant_id = request.headers.get("X-Tenant-ID")
        workflow_id = request.headers.get("X-Workflow-ID")
        user_id = request.headers.get("X-User-ID")

        # Set correlation context
        with correlation_context(
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            user_id=user_id
        ):
            # Start request tracing
            with request_tracer.trace(
                operation=f"{request.method} {request.url.path}",
                service="system-orchestrator",
                method=request.method,
                path=request.url.path,
                query_params=str(request.query_params),
                user_agent=request.headers.get("User-Agent"),
                remote_addr=request.client.host if request.client else None
            ):
                # Log request start
                logger.info(
                    "Request started",
                    method=request.method,
                    path=request.url.path,
                    correlation_id=correlation_id,
                    tenant_id=tenant_id
                )

                # Time the request processing
                start_time = time.time()

                try:
                    # Process request
                    response = await call_next(request)

                    # Calculate processing time
                    processing_time = time.time() - start_time
                    processing_time_ms = round(processing_time * 1000, 2)

                    # Log request completion
                    logger.info(
                        "Request completed",
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        processing_time_ms=processing_time_ms,
                        correlation_id=correlation_id
                    )

                    # Add correlation ID to response headers
                    response.headers["X-Correlation-ID"] = correlation_id

                    # Add performance metrics to response headers (for debugging)
                    if response.status_code == 200:
                        response.headers["X-Processing-Time-MS"] = str(processing_time_ms)

                    # Log business event for request processing
                    log_business_event(
                        "http_request_completed",
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        processing_time_ms=processing_time_ms,
                        correlation_id=correlation_id,
                        tenant_id=tenant_id
                    )

                    return response

                except Exception as e:
                    # Calculate processing time for failed requests
                    processing_time = time.time() - start_time
                    processing_time_ms = round(processing_time * 1000, 2)

                    # Log request error
                    logger.error(
                        "Request failed",
                        method=request.method,
                        path=request.url.path,
                        error=str(e),
                        processing_time_ms=processing_time_ms,
                        correlation_id=correlation_id,
                        exc_info=True
                    )

                    # Log business event for request failure
                    log_business_event(
                        "http_request_failed",
                        method=request.method,
                        path=request.url.path,
                        error=str(e),
                        processing_time_ms=processing_time_ms,
                        correlation_id=correlation_id,
                        tenant_id=tenant_id
                    )

                    # Return JSON error response with correlation ID
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": "Internal server error",
                            "correlation_id": correlation_id,
                            "timestamp": time.time()
                        }
                    )


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for detailed performance monitoring."""

    def __init__(self, app, slow_request_threshold_ms: float = 1000.0):
        """
        Initialize performance monitoring middleware.

        Args:
            app: FastAPI application
            slow_request_threshold_ms: Threshold for logging slow requests
        """
        super().__init__(app)
        self.slow_request_threshold_ms = slow_request_threshold_ms

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request performance with detailed timing."""
        start_time = time.time()

        with performance_timing(f"{request.method} {request.url.path}"):
            response = await call_next(request)

        processing_time = (time.time() - start_time) * 1000

        # Log slow requests
        if processing_time > self.slow_request_threshold_ms:
            logger.warning(
                "Slow request detected",
                method=request.method,
                path=request.url.path,
                processing_time_ms=round(processing_time, 2),
                threshold_ms=self.slow_request_threshold_ms,
                correlation_id=get_correlation_id()
            )

        # Add performance header
        response.headers["X-Processing-Time-MS"] = str(round(processing_time, 2))

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for detailed request/response logging."""

    def __init__(self, app, log_body: bool = False, max_body_size: int = 1024):
        """
        Initialize request logging middleware.

        Args:
            app: FastAPI application
            log_body: Whether to log request/response bodies
            max_body_size: Maximum body size to log (in bytes)
        """
        super().__init__(app)
        self.log_body = log_body
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log detailed request information."""
        correlation_id = get_correlation_id()

        # Log request details
        request_data = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "client": request.client.host if request.client else None,
            "correlation_id": correlation_id
        }

        # Add request body if enabled and not too large
        if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if len(body) <= self.max_body_size:
                    request_data["body"] = body.decode("utf-8", errors="ignore")
                else:
                    request_data["body_size"] = len(body)
            except Exception as e:
                logger.warning("Failed to read request body", error=str(e), correlation_id=correlation_id)

        logger.info("HTTP request received", **request_data)

        # Process request
        response = await call_next(request)

        # Log response details
        response_data = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "correlation_id": correlation_id
        }

        # Add response body size
        if hasattr(response, 'body'):
            response_data["response_size"] = len(response.body) if response.body else 0

        logger.info("HTTP response sent", **response_data)

        return response


class MetricsCollectionMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics for monitoring."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Collect metrics for HTTP requests."""
        from app.services.metrics_service import metrics_service

        start_time = time.time()
        correlation_id = get_correlation_id()
        tenant_id = request.headers.get("X-Tenant-ID")

        try:
            response = await call_next(request)

            # Record request metrics
            processing_time_ms = (time.time() - start_time) * 1000

            # Record performance metric
            metrics_service.record_performance_metric(
                operation="http_request",
                duration_ms=processing_time_ms,
                service="system-orchestrator"
            )

            # Record service health metric
            metrics_service.record_service_health(
                service="system-orchestrator",
                healthy=response.status_code < 500,
                response_time_ms=processing_time_ms
            )

            # Record SMS processing metrics for specific endpoints
            if "/orchestrate/sms-received" in request.url.path and request.method == "POST":
                metrics_service.record_sms_received(
                    tenant_id=tenant_id or "unknown",
                    phone_number="extracted_from_request"
                )

            # Record approval workflow metrics
            if "/orchestrate/approve-response" in request.url.path and request.method == "POST":
                metrics_service.record_approval_decision(
                    tenant_id=tenant_id or "unknown",
                    approved=response.status_code == 200,
                    auto_approved=False  # Manual approval endpoint
                )

            # Record escalation metrics
            if "/orchestrate/escalate" in request.url.path and request.method == "POST":
                metrics_service.record_escalation(
                    tenant_id=tenant_id or "unknown",
                    escalation_type="manual",
                    severity="high"
                )

            logger.debug(
                "HTTP metrics collected",
                path=request.url.path,
                status_code=response.status_code,
                processing_time_ms=round(processing_time_ms, 2),
                correlation_id=correlation_id
            )

            return response

        except Exception as e:
            # Record failed request metrics
            processing_time_ms = (time.time() - start_time) * 1000

            metrics_service.record_performance_metric(
                operation="http_request_failed",
                duration_ms=processing_time_ms,
                service="system-orchestrator"
            )

            metrics_service.record_service_health(
                service="system-orchestrator",
                healthy=False,
                response_time_ms=processing_time_ms
            )

            logger.error(
                "Failed to collect HTTP metrics",
                error=str(e),
                processing_time_ms=round(processing_time_ms, 2),
                correlation_id=correlation_id,
                exc_info=True
            )

            raise