"""
Tests for timeout monitoring utilities.

Comprehensive test coverage for Story 2.2 AC3 timeout requirements.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from app.utils.timeout_monitor import (
    TimeoutMonitor,
    WorkflowTimeout,
    TimeoutStatus
)


class TestWorkflowTimeout:
    """Test cases for WorkflowTimeout dataclass."""

    def test_workflow_timeout_creation(self):
        """Test WorkflowTimeout creation and properties."""
        now = datetime.utcnow()
        timeout = WorkflowTimeout(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=now,
            timeout_threshold=timedelta(hours=36),
            status=TimeoutStatus.ACTIVE
        )

        assert timeout.workflow_id == "test-workflow-1"
        assert timeout.customer_phone == "+1234567890"
        assert timeout.last_ai_response == now
        assert timeout.status == TimeoutStatus.ACTIVE
        assert timeout.warning_sent is False
        assert timeout.escalation_triggered is False

    def test_time_remaining_calculation(self):
        """Test time remaining calculation."""
        now = datetime.utcnow()
        timeout = WorkflowTimeout(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=now,
            timeout_threshold=timedelta(hours=36),
            status=TimeoutStatus.ACTIVE
        )

        # Should have approximately 36 hours remaining
        remaining = timeout.time_remaining
        assert timedelta(hours=35) < remaining <= timedelta(hours=36)

    def test_is_expired_false(self):
        """Test expiration check for non-expired workflow."""
        now = datetime.utcnow()
        timeout = WorkflowTimeout(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=now,
            timeout_threshold=timedelta(hours=36),
            status=TimeoutStatus.ACTIVE
        )

        assert timeout.is_expired is False

    def test_is_expired_true(self):
        """Test expiration check for expired workflow."""
        past_time = datetime.utcnow() - timedelta(hours=37)
        timeout = WorkflowTimeout(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=past_time,
            timeout_threshold=timedelta(hours=36),
            status=TimeoutStatus.ACTIVE
        )

        assert timeout.is_expired is True

    def test_is_warning_threshold_false(self):
        """Test warning threshold check for normal workflow."""
        now = datetime.utcnow()
        timeout = WorkflowTimeout(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=now,
            timeout_threshold=timedelta(hours=36),
            status=TimeoutStatus.ACTIVE
        )

        assert timeout.is_warning_threshold is False

    def test_is_warning_threshold_true(self):
        """Test warning threshold check for workflow near timeout."""
        near_timeout = datetime.utcnow() - timedelta(hours=35)
        timeout = WorkflowTimeout(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=near_timeout,
            timeout_threshold=timedelta(hours=36),
            status=TimeoutStatus.ACTIVE
        )

        assert timeout.is_warning_threshold is True

    def test_to_dict_conversion(self):
        """Test conversion to dictionary format."""
        now = datetime.utcnow()
        timeout = WorkflowTimeout(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=now,
            timeout_threshold=timedelta(hours=36),
            status=TimeoutStatus.ACTIVE
        )

        timeout_dict = timeout.to_dict()

        assert timeout_dict["workflow_id"] == "test-workflow-1"
        assert timeout_dict["customer_phone"] == "+1234567890"
        assert timeout_dict["status"] == "active"
        assert timeout_dict["timeout_threshold_hours"] == 36
        assert timeout_dict["warning_sent"] is False
        assert timeout_dict["escalation_triggered"] is False


class TestTimeoutMonitor:
    """Test cases for TimeoutMonitor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = TimeoutMonitor(timeout_hours=36)

    def test_monitor_initialization(self):
        """Test timeout monitor initialization."""
        assert self.monitor.timeout_threshold == timedelta(hours=36)
        assert self.monitor.active_timeouts == {}
        assert self.monitor._monitoring_interval == 300

    def test_register_workflow(self):
        """Test workflow registration."""
        now = datetime.utcnow()
        timeout = self.monitor.register_workflow(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=now
        )

        assert timeout.workflow_id == "test-workflow-1"
        assert timeout.customer_phone == "+1234567890"
        assert timeout.last_ai_response == now
        assert timeout.timeout_threshold == timedelta(hours=36)
        assert timeout.status == TimeoutStatus.ACTIVE

        # Check it's stored in active_timeouts
        assert "test-workflow-1" in self.monitor.active_timeouts
        assert self.monitor.active_timeouts["test-workflow-1"] == timeout

    def test_update_workflow_response(self):
        """Test updating workflow response time."""
        # First register a workflow
        now = datetime.utcnow()
        self.monitor.register_workflow(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=now
        )

        # Update with new response time
        new_response_time = now + timedelta(hours=1)
        updated_timeout = self.monitor.update_workflow_response(
            workflow_id="test-workflow-1",
            response_time=new_response_time
        )

        assert updated_timeout is not None
        assert updated_timeout.last_ai_response == new_response_time
        assert updated_timeout.status == TimeoutStatus.ACTIVE
        assert updated_timeout.warning_sent is False

    def test_update_nonexistent_workflow(self):
        """Test updating workflow that doesn't exist."""
        result = self.monitor.update_workflow_response(
            workflow_id="nonexistent-workflow",
            response_time=datetime.utcnow()
        )

        assert result is None

    def test_remove_workflow(self):
        """Test removing workflow from monitoring."""
        # Register a workflow first
        self.monitor.register_workflow(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=datetime.utcnow()
        )

        # Remove it
        result = self.monitor.remove_workflow("test-workflow-1")
        assert result is True
        assert "test-workflow-1" not in self.monitor.active_timeouts

        # Try to remove again
        result = self.monitor.remove_workflow("test-workflow-1")
        assert result is False

    def test_get_expired_workflows(self):
        """Test getting expired workflows."""
        # Add an expired workflow
        past_time = datetime.utcnow() - timedelta(hours=37)
        self.monitor.register_workflow(
            workflow_id="expired-workflow",
            customer_phone="+1234567890",
            last_ai_response=past_time
        )

        # Add a normal workflow
        now = datetime.utcnow()
        self.monitor.register_workflow(
            workflow_id="normal-workflow",
            customer_phone="+1234567891",
            last_ai_response=now
        )

        expired = self.monitor.get_expired_workflows()
        assert len(expired) == 1
        assert expired[0].workflow_id == "expired-workflow"

    def test_get_warning_workflows(self):
        """Test getting workflows near timeout."""
        # Add a workflow near timeout (35 hours old)
        near_timeout = datetime.utcnow() - timedelta(hours=35)
        self.monitor.register_workflow(
            workflow_id="warning-workflow",
            customer_phone="+1234567890",
            last_ai_response=near_timeout
        )

        # Add a normal workflow
        now = datetime.utcnow()
        self.monitor.register_workflow(
            workflow_id="normal-workflow",
            customer_phone="+1234567891",
            last_ai_response=now
        )

        warnings = self.monitor.get_warning_workflows()
        assert len(warnings) == 1
        assert warnings[0].workflow_id == "warning-workflow"

    @pytest.mark.asyncio
    async def test_check_timeouts(self):
        """Test timeout checking functionality."""
        # Add expired workflow
        past_time = datetime.utcnow() - timedelta(hours=37)
        self.monitor.register_workflow(
            workflow_id="expired-workflow",
            customer_phone="+1234567890",
            last_ai_response=past_time
        )

        # Add warning workflow
        near_timeout = datetime.utcnow() - timedelta(hours=35)
        self.monitor.register_workflow(
            workflow_id="warning-workflow",
            customer_phone="+1234567891",
            last_ai_response=near_timeout
        )

        # Check timeouts
        result = await self.monitor.check_timeouts()

        assert "expired" in result
        assert "warnings" in result
        assert len(result["expired"]) == 1
        assert len(result["warnings"]) == 1
        assert result["expired"][0].workflow_id == "expired-workflow"
        assert result["warnings"][0].workflow_id == "warning-workflow"

    def test_get_workflow_timeout(self):
        """Test getting specific workflow timeout."""
        # Register a workflow
        now = datetime.utcnow()
        registered_timeout = self.monitor.register_workflow(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=now
        )

        # Get it back
        retrieved_timeout = self.monitor.get_workflow_timeout("test-workflow-1")
        assert retrieved_timeout == registered_timeout

        # Try to get non-existent workflow
        nonexistent = self.monitor.get_workflow_timeout("nonexistent")
        assert nonexistent is None

    def test_get_all_timeouts(self):
        """Test getting all active timeouts."""
        # Register multiple workflows
        self.monitor.register_workflow(
            workflow_id="workflow-1",
            customer_phone="+1234567890",
            last_ai_response=datetime.utcnow()
        )
        self.monitor.register_workflow(
            workflow_id="workflow-2",
            customer_phone="+1234567891",
            last_ai_response=datetime.utcnow()
        )

        all_timeouts = self.monitor.get_all_timeouts()
        assert len(all_timeouts) == 2
        workflow_ids = [t.workflow_id for t in all_timeouts]
        assert "workflow-1" in workflow_ids
        assert "workflow-2" in workflow_ids

    def test_get_timeout_statistics(self):
        """Test getting timeout statistics."""
        # Add different types of workflows
        past_time = datetime.utcnow() - timedelta(hours=37)
        self.monitor.register_workflow(
            workflow_id="expired-workflow",
            customer_phone="+1234567890",
            last_ai_response=past_time
        )

        near_timeout = datetime.utcnow() - timedelta(hours=35)
        self.monitor.register_workflow(
            workflow_id="warning-workflow",
            customer_phone="+1234567891",
            last_ai_response=near_timeout
        )

        stats = self.monitor.get_timeout_statistics()
        assert stats["total_active_workflows"] == 2
        assert stats["expired_workflows"] == 1
        assert stats["warning_workflows"] == 1
        assert stats["escalated_workflows"] == 0
        assert stats["timeout_threshold_hours"] == 36
        assert stats["monitoring_active"] is None

    def test_mark_workflow_escalated(self):
        """Test marking workflow as escalated."""
        # Register a workflow
        self.monitor.register_workflow(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=datetime.utcnow()
        )

        # Mark as escalated
        result = self.monitor.mark_workflow_escalated("test-workflow-1")
        assert result is True

        # Check status updated
        timeout = self.monitor.get_workflow_timeout("test-workflow-1")
        assert timeout.escalation_triggered is True
        assert timeout.status == TimeoutStatus.ESCALATED

        # Try to mark non-existent workflow
        result = self.monitor.mark_workflow_escalated("nonexistent")
        assert result is False

    def test_cleanup_old_timeouts(self):
        """Test cleanup of old timeout entries."""
        # Create an old escalated timeout
        old_time = datetime.utcnow() - timedelta(days=10)
        timeout = WorkflowTimeout(
            workflow_id="old-workflow",
            customer_phone="+1234567890",
            last_ai_response=old_time,
            timeout_threshold=timedelta(hours=36),
            status=TimeoutStatus.ESCALATED
        )
        timeout.created_at = old_time
        timeout.escalation_triggered = True
        self.monitor.active_timeouts["old-workflow"] = timeout

        # Create a recent timeout
        self.monitor.register_workflow(
            workflow_id="recent-workflow",
            customer_phone="+1234567891",
            last_ai_response=datetime.utcnow()
        )

        # Clean up old timeouts
        removed_count = self.monitor.cleanup_old_timeouts(days_old=7)

        assert removed_count == 1
        assert "old-workflow" not in self.monitor.active_timeouts
        assert "recent-workflow" in self.monitor.active_timeouts

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring."""
        # Start monitoring
        await self.monitor.start_monitoring()
        assert self.monitor._monitoring_task is not None
        assert self.monitor._monitoring_task.done() is False

        # Try to start again (should warn but not create new task)
        original_task = self.monitor._monitoring_task
        await self.monitor.start_monitoring()
        assert self.monitor._monitoring_task == original_task

        # Stop monitoring
        await self.monitor.stop_monitoring()
        assert self.monitor._monitoring_task.cancelled() or self.monitor._monitoring_task.done()

    @pytest.mark.asyncio
    async def test_monitoring_with_custom_timeout(self):
        """Test monitor with custom timeout duration."""
        custom_monitor = TimeoutMonitor(timeout_hours=24)
        assert custom_monitor.timeout_threshold == timedelta(hours=24)

        # Register workflow and check timeout calculation
        now = datetime.utcnow()
        timeout = custom_monitor.register_workflow(
            workflow_id="test-workflow",
            customer_phone="+1234567890",
            last_ai_response=now
        )

        assert timeout.timeout_threshold == timedelta(hours=24)

        # Test expiration with 24-hour timeout
        past_time = datetime.utcnow() - timedelta(hours=25)
        expired_timeout = custom_monitor.register_workflow(
            workflow_id="expired-workflow",
            customer_phone="+1234567891",
            last_ai_response=past_time
        )

        assert expired_timeout.is_expired is True