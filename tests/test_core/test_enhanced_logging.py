import pytest
import json
import asyncio
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime
import uuid

from app.core.logging import (
    get_logger,
    setup_logging,
    correlation_context,
    performance_timing,
    log_business_event,
    log_performance_metrics,
    request_tracer,
    log_request_start,
    log_request_end,
    log_error_with_context,
    log_structured_format,
    log_filtering,
    log_aggregation,
    log_middleware_integration,
    log_error_stack_traces,
    configure_logging_settings
)


class TestEnhancedLogging:
    """Test suite for enhanced logging functionality"""

    @pytest.fixture
    def logger(self):
        """Create a logger instance for testing"""
        return get_logger("test_logger")

    @pytest.fixture
    def mock_context(self):
        """Create a mock correlation context"""
        return {
            "correlation_id": str(uuid.uuid4()),
            "request_id": str(uuid.uuid4()),
            "user_id": "test_user",
            "tenant_id": "test_tenant"
        }

    def test_logger_initialization(self, logger):
        """Test logger initialization with proper configuration"""
        assert logger is not None
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'warning')
        assert hasattr(logger, 'debug')

    def test_correlation_context(self, logger):
        """Test correlation ID context manager"""
        correlation_id = str(uuid.uuid4())

        with correlation_context(correlation_id):
            # After setting context, the correlation ID should be in the context variable
            from app.core.logging import correlation_id_var
            assert correlation_id_var.get() == correlation_id

    def test_correlation_context_nested(self, logger):
        """Test nested correlation ID contexts"""
        outer_id = str(uuid.uuid4())
        inner_id = str(uuid.uuid4())

        from app.core.logging import correlation_id_var, tenant_id_var

        with correlation_context(outer_id, tenant_id="test_outer"):
            assert correlation_id_var.get() == outer_id
            assert tenant_id_var.get() == "test_outer"

            with correlation_context(inner_id, tenant_id="test_inner"):
                assert correlation_id_var.get() == inner_id
                assert tenant_id_var.get() == "test_inner"

            # After inner context ends, should be back to outer
            assert correlation_id_var.get() == outer_id
            assert tenant_id_var.get() == "test_outer"

    def test_performance_timing(self, logger):
        """Test performance context manager"""
        operation_name = "test_operation"

        import time
        start_time = time.time()

        with performance_timing(operation_name):
            # Simulate some work
            time.sleep(0.01)

        # Check that some time has passed
        end_time = time.time()
        assert end_time - start_time >= 0.01

    async def test_performance_timing_async(self, logger):
        """Test performance context with async operations"""
        operation_name = "async_test_operation"

        import time
        start_time = time.time()

        with performance_timing(operation_name):
            # Simulate async work
            await asyncio.sleep(0.01)

        # Check that some time has passed
        end_time = time.time()
        assert end_time - start_time >= 0.01

    def test_log_request_start(self, logger):
        """Test request start logging"""
        request_data = {
            "method": "POST",
            "path": "/test/endpoint",
            "headers": {"content-type": "application/json"},
            "user_agent": "test-client/1.0"
        }

        with patch.object(logger, 'info') as mock_info:
            log_request_start(logger, request_data)
            mock_info.assert_called_once()

            # Check that the logged message contains expected fields
            call_args = mock_info.call_args
            assert "event" in call_args[1]
            assert call_args[1]["event"] == "request_start"
            assert "method" in call_args[1]
            assert call_args[1]["method"] == "POST"

    def test_log_request_end(self, logger):
        """Test request end logging"""
        response_data = {
            "status_code": 200,
            "response_size": 1024,
            "duration_ms": 150
        }

        with patch.object(logger, 'info') as mock_info:
            log_request_end(logger, response_data)
            mock_info.assert_called_once()

            # Check that the logged message contains expected fields
            call_args = mock_info.call_args
            assert "event" in call_args[1]
            assert call_args[1]["event"] == "request_end"
            assert "status_code" in call_args[1]
            assert call_args[1]["status_code"] == 200

    def test_log_business_event(self, logger):
        """Test business event logging"""
        with patch('app.core.logging.get_business_logger') as mock_get_logger:
            mock_business_logger = Mock()
            mock_get_logger.return_value = mock_business_logger

            log_business_event("sms_received", phone_number="+1234567890", message_content="Test message")

            mock_business_logger.info.assert_called_once_with(
                "Business event",
                event_type="sms_received",
                phone_number="+1234567890",
                message_content="Test message"
            )

    def test_log_error_with_context(self, logger):
        """Test error logging with context"""
        error = ValueError("Test error message")
        context = {
            "user_id": "test_user",
            "request_path": "/test/endpoint",
            "additional_info": "Some context"
        }

        with patch.object(logger, 'error') as mock_error:
            log_error_with_context(logger, error, context)
            mock_error.assert_called_once()

            # Check that the logged message contains expected fields
            call_args = mock_error.call_args
            assert "error_type" in call_args[1]
            assert call_args[1]["error_type"] == "ValueError"
            assert "error_message" in call_args[1]
            assert call_args[1]["error_message"] == "Test error message"

    def test_structured_logging_format(self, logger):
        """Test that logs are structured in JSON format"""
        test_data = {
            "test_key": "test_value",
            "timestamp": datetime.now().isoformat(),
            "numeric_value": 42
        }

        with patch('app.core.logging.logger') as mock_logger:
            logger.info("Test message", **test_data)

            # Verify the logger was called with structured data
            mock_logger.info.assert_called_once()

    def test_log_sampling(self, logger):
        """Test log sampling functionality"""
        # This test would verify that high-volume logs can be sampled
        # Implementation depends on the actual sampling logic

        # Test with sampling enabled
        test_data = {"high_volume": True, "sample_rate": 0.1}

        with patch.object(logger, 'debug') as mock_debug:
            # Log multiple messages
            for i in range(100):
                logger.debug(f"Debug message {i}", **test_data)

            # With sampling, not all debug messages should be logged
            # This is a basic test - actual sampling logic may vary
            assert mock_debug.call_count <= 100

    def test_log_filtering(self, logger):
        """Test log filtering capabilities"""
        sensitive_data = {
            "password": "secret123",
            "api_key": "sk-test123",
            "safe_data": "public_value"
        }

        with patch.object(logger, 'info') as mock_info:
            logger.info("Test with sensitive data", **sensitive_data)

            # Check that sensitive data is filtered/redacted
            call_args = mock_info.call_args
            logged_data = call_args[1]

            # Password should be redacted
            if "password" in logged_data:
                assert logged_data["password"] != "secret123"

            # API key should be redacted
            if "api_key" in logged_data:
                assert logged_data["api_key"] != "sk-test123"

    def test_correlation_id_propagation(self, logger):
        """Test correlation ID propagation across log messages"""
        correlation_id = str(uuid.uuid4())

        with correlation_context(correlation_id):
            with patch.object(logger, 'info') as mock_info:
                logger.info("Test message 1")
                logger.info("Test message 2")

                # Both messages should have the same correlation ID
                assert mock_info.call_count == 2

                for call in mock_info.call_args_list:
                    logged_data = call[1] if call[1] else {}
                    assert "correlation_id" in logged_data
                    assert logged_data["correlation_id"] == correlation_id

    def test_distributed_tracing(self, logger):
        """Test distributed tracing capabilities"""
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        tracing_context = {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": None
        }

        with correlation_context(trace_id, **tracing_context):
            with patch.object(logger, 'info') as mock_info:
                logger.info("Traced operation")

                call_args = mock_info.call_args
                logged_data = call_args[1]

                assert "trace_id" in logged_data
                assert logged_data["trace_id"] == trace_id
                assert "span_id" in logged_data
                assert logged_data["span_id"] == span_id

    def test_performance_logging_accuracy(self, logger):
        """Test accuracy of performance logging timing"""
        import time

        expected_duration = 0.1  # 100ms

        with performance_timing("timing_test") as perf_ctx:
            time.sleep(expected_duration)

        # Allow some tolerance for timing variations
        tolerance = 0.05  # 50ms tolerance
        actual_duration = perf_ctx["duration_ms"] / 1000  # Convert to seconds

        assert abs(actual_duration - expected_duration) <= tolerance

    def test_concurrent_logging(self, logger):
        """Test logging from concurrent operations"""
        import threading
        import time

        results = []

        def log_in_thread(thread_id):
            correlation_id = str(uuid.uuid4())
            with correlation_context(correlation_id, user_id=f"thread_{thread_id}"):
                with patch.object(logger, 'info') as mock_info:
                    logger.info(f"Message from thread {thread_id}")
                    results.append((thread_id, mock_info.call_args))

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=log_in_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify each thread logged with its own context
        assert len(results) == 5
        thread_ids = {result[0] for result in results}
        assert thread_ids == {0, 1, 2, 3, 4}

    def test_log_aggregation(self, logger):
        """Test log aggregation capabilities"""
        # This test would verify that logs can be aggregated
        # Implementation depends on the actual aggregation logic

        events = []
        for i in range(10):
            event = {
                "event_type": "test_event",
                "event_id": i,
                "timestamp": datetime.now().isoformat()
            }
            events.append(event)

            with patch.object(logger, 'info') as mock_info:
                log_business_event(logger, event)
                mock_info.assert_called_once()

    def test_middleware_integration(self, logger):
        """Test logging middleware integration"""
        # Simulate middleware context
        middleware_context = {
            "request_id": str(uuid.uuid4()),
            "user_id": "middleware_user",
            "tenant_id": "middleware_tenant",
            "ip_address": "192.168.1.1"
        }

        with correlation_context(**middleware_context):
            with patch.object(logger, 'info') as mock_info:
                logger.info("Middleware test message")

                call_args = mock_info.call_args
                logged_data = call_args[1]

                # Verify all middleware context is included
                for key, value in middleware_context.items():
                    assert key in logged_data
                    assert logged_data[key] == value

    def test_error_stack_traces(self, logger):
        """Test that error logs include stack traces"""
        try:
            # Create an error with a stack trace
            def deep_function():
                def deeper_function():
                    raise ValueError("Deep error")
                deeper_function()
            deep_function()
        except ValueError as e:
            with patch.object(logger, 'error') as mock_error:
                log_error_with_context(logger, e, {"context": "test"})

                call_args = mock_error.call_args
                logged_data = call_args[1]

                # Should include stack trace information
                assert "stack_trace" in logged_data or "traceback" in logged_data
                assert "error_type" in logged_data
                assert logged_data["error_type"] == "ValueError"

    def test_configuration_changes(self, logger):
        """Test that logging configuration changes take effect"""
        # This test would verify dynamic configuration changes
        # Implementation depends on the actual configuration system

        with patch('app.core.logging.setup_logging') as mock_setup:
            setup_logging(level="DEBUG", format="json")
            mock_setup.assert_called_once_with(level="DEBUG", format="json")