"""
Tests for escalation service.

Comprehensive test coverage for Story 2.2 escalation workflows.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from app.services.escalation_service import EscalationService
from app.utils.escalation_triggers import EscalationReason, EscalationTrigger
from app.models.schemas import EscalationRequest, EscalationResponse


class TestEscalationService:
    """Test cases for EscalationService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_notification_client = Mock()
        self.mock_sms_agent_client = Mock()
        self.mock_collections_monitor_client = Mock()

        self.service = EscalationService(
            notification_client=self.mock_notification_client,
            sms_agent_client=self.mock_sms_agent_client,
            collections_monitor_client=self.mock_collections_monitor_client
        )

    @pytest.mark.asyncio
    async def test_analyze_message_for_escalation_with_trigger(self):
        """Test message analysis that detects escalation trigger."""
        message_text = "I am furious and want to speak to your supervisor!"
        workflow_id = "test-workflow-1"
        customer_phone = "+1234567890"

        should_escalate, trigger = await self.service.analyze_message_for_escalation(
            message_text=message_text,
            workflow_id=workflow_id,
            customer_phone=customer_phone
        )

        assert should_escalate is True
        assert trigger is not None
        assert trigger.reason == EscalationReason.ANGER
        assert trigger.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_analyze_message_for_escalation_no_trigger(self):
        """Test message analysis with no escalation triggers."""
        message_text = "Thank you for your help. I understand the payment options."
        workflow_id = "test-workflow-1"
        customer_phone = "+1234567890"

        should_escalate, trigger = await self.service.analyze_message_for_escalation(
            message_text=message_text,
            workflow_id=workflow_id,
            customer_phone=customer_phone
        )

        assert should_escalate is False
        assert trigger is None

    @pytest.mark.asyncio
    async def test_analyze_message_legal_trigger(self):
        """Test message analysis with legal escalation trigger."""
        message_text = "I will contact my lawyer about this issue."
        workflow_id = "test-workflow-1"
        customer_phone = "+1234567890"

        should_escalate, trigger = await self.service.analyze_message_for_escalation(
            message_text=message_text,
            workflow_id=workflow_id,
            customer_phone=customer_phone
        )

        assert should_escalate is True
        assert trigger is not None
        assert trigger.reason == EscalationReason.LEGAL_REQUEST
        assert trigger.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_register_workflow_timeout(self):
        """Test registering workflow for timeout monitoring."""
        workflow_id = "test-workflow-1"
        customer_phone = "+1234567890"
        last_response = datetime.utcnow()

        await self.service.register_workflow_timeout(
            workflow_id=workflow_id,
            customer_phone=customer_phone,
            last_ai_response=last_response
        )

        # Verify timeout is registered
        timeout = self.service.timeout_monitor.get_workflow_timeout(workflow_id)
        assert timeout is not None
        assert timeout.workflow_id == workflow_id
        assert timeout.customer_phone == customer_phone
        assert timeout.last_ai_response == last_response

    @pytest.mark.asyncio
    async def test_update_workflow_response(self):
        """Test updating workflow response time."""
        workflow_id = "test-workflow-1"
        customer_phone = "+1234567890"
        initial_response = datetime.utcnow()

        # Register first
        await self.service.register_workflow_timeout(
            workflow_id=workflow_id,
            customer_phone=customer_phone,
            last_ai_response=initial_response
        )

        # Update with new response time
        new_response = datetime.utcnow() + timedelta(hours=1)
        await self.service.update_workflow_response(
            workflow_id=workflow_id,
            response_time=new_response
        )

        # Verify update
        timeout = self.service.timeout_monitor.get_workflow_timeout(workflow_id)
        assert timeout is not None
        assert timeout.last_ai_response == new_response

    @pytest.mark.asyncio
    async def test_remove_workflow_monitoring(self):
        """Test removing workflow from monitoring."""
        workflow_id = "test-workflow-1"
        customer_phone = "+1234567890"

        # Register first
        await self.service.register_workflow_timeout(
            workflow_id=workflow_id,
            customer_phone=customer_phone,
            last_ai_response=datetime.utcnow()
        )

        # Verify it exists
        timeout = self.service.timeout_monitor.get_workflow_timeout(workflow_id)
        assert timeout is not None

        # Remove it
        await self.service.remove_workflow_monitoring(workflow_id)

        # Verify it's gone
        timeout = self.service.timeout_monitor.get_workflow_timeout(workflow_id)
        assert timeout is None

    @pytest.mark.asyncio
    async def test_check_timeout_escalations(self):
        """Test checking for timeout-based escalations."""
        # Create expired workflow
        past_time = datetime.utcnow() - timedelta(hours=37)
        await self.service.register_workflow_timeout(
            workflow_id="expired-workflow",
            customer_phone="+1234567890",
            last_ai_response=past_time
        )

        # Check for escalations
        escalations = await self.service.check_timeout_escalations()

        assert len(escalations) == 1
        assert escalations[0]["workflow_id"] == "expired-workflow"
        assert escalations[0]["escalation_type"] == "timeout_based"

    @pytest.mark.asyncio
    async def test_check_timeout_escalations_with_warnings(self):
        """Test timeout checking with warning workflows."""
        # Create workflow near timeout (35 hours old)
        near_timeout = datetime.utcnow() - timedelta(hours=35)
        await self.service.register_workflow_timeout(
            workflow_id="warning-workflow",
            customer_phone="+1234567890",
            last_ai_response=near_timeout
        )

        # Check for escalations (should not escalate warnings, only send notifications)
        escalations = await self.service.check_timeout_escalations()

        # Should not trigger escalation for warnings
        assert len(escalations) == 0

    @pytest.mark.asyncio
    async def test_trigger_escalation_success(self):
        """Test successful escalation triggering."""
        trigger = EscalationTrigger(
            reason=EscalationReason.ANGER,
            confidence=0.8,
            matched_text="furious",
            pattern_type="keyword"
        )

        escalation_details = await self.service._trigger_escalation(
            workflow_id="test-workflow-1",
            customer_phone="+1234567890",
            trigger=trigger,
            escalation_type="trigger_based"
        )

        assert escalation_details["workflow_id"] == "test-workflow-1"
        assert escalation_details["customer_phone"] == "+1234567890"
        assert escalation_details["reason"] == EscalationReason.ANGER.value
        assert escalation_details["confidence"] == 0.8
        assert escalation_details["escalation_type"] == "trigger_based"
        assert escalation_details["status"] == "triggered"

    @pytest.mark.asyncio
    async def test_trigger_timeout_escalation(self):
        """Test timeout-based escalation triggering."""
        from app.utils.timeout_monitor import WorkflowTimeout, TimeoutStatus

        timeout = WorkflowTimeout(
            workflow_id="timeout-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=datetime.utcnow() - timedelta(hours=37),
            timeout_threshold=timedelta(hours=36),
            status=TimeoutStatus.EXPIRED
        )

        escalation_details = await self.service._trigger_timeout_escalation(timeout)

        assert escalation_details["workflow_id"] == "timeout-workflow-1"
        assert escalation_details["escalation_type"] == "timeout_based"
        assert escalation_details["reason"] == EscalationReason.DISSATISFACTION.value
        assert escalation_details["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_send_escalation_notifications(self):
        """Test sending escalation notifications to all parties."""
        escalation_details = {
            "escalation_id": "test-escalation-1",
            "workflow_id": "test-workflow-1",
            "customer_phone": "+1234567890",
            "reason": EscalationReason.ANGER.value,
            "confidence": 0.8,
            "timestamp": datetime.utcnow().isoformat(),
            "escalation_type": "trigger_based"
        }

        # Mock the notification methods
        self.service._notify_collections_monitor = AsyncMock()
        self.service._notify_sms_agent = AsyncMock()
        self.service._notify_internal_teams = AsyncMock()

        await self.service._send_escalation_notifications(escalation_details)

        # Verify all notification methods were called
        self.service._notify_collections_monitor.assert_called_once()
        self.service._notify_sms_agent.assert_called_once()
        self.service._notify_internal_teams.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_manual_escalation_request(self):
        """Test processing manual escalation request."""
        request = EscalationRequest(
            workflow_id="manual-workflow-1",
            customer_phone="+1234567890",
            reason="customer_anger",
            notes="Manual escalation requested by agent"
        )

        response = await self.service.process_escalation_request(request)

        assert isinstance(response, EscalationResponse)
        assert response.workflow_id == "manual-workflow-1"
        assert response.status == "escalated"
        assert "escalated" in response.escalation_id
        assert response.timestamp is not None

    @pytest.mark.asyncio
    async def test_get_escalation_statistics(self):
        """Test getting escalation statistics."""
        # Register some test workflows
        await self.service.register_workflow_timeout(
            workflow_id="active-workflow-1",
            customer_phone="+1234567890",
            last_ai_response=datetime.utcnow()
        )

        past_time = datetime.utcnow() - timedelta(hours=37)
        await self.service.register_workflow_timeout(
            workflow_id="expired-workflow-1",
            customer_phone="+1234567891",
            last_ai_response=past_time
        )

        stats = await self.service.get_escalation_statistics()

        assert stats["total_active_workflows"] == 2
        assert stats["expired_workflows"] == 1
        assert stats["timeout_threshold_hours"] == 36
        assert stats["escalation_service_active"] is True

    @pytest.mark.asyncio
    async def test_start_stop_services(self):
        """Test starting and stopping escalation services."""
        # Start services
        await self.service.start_services()
        assert self.service.timeout_monitor._monitoring_task is not None

        # Stop services
        await self.service.stop_services()
        assert self.service.timeout_monitor._monitoring_task.cancelled()

    @pytest.mark.asyncio
    async def test_multiple_triggers_in_single_message(self):
        """Test handling message with multiple escalation triggers."""
        message_text = "I am furious and will contact my lawyer about this unacceptable service!"
        workflow_id = "test-workflow-1"
        customer_phone = "+1234567890"

        should_escalate, trigger = await self.service.analyze_message_for_escalation(
            message_text=message_text,
            workflow_id=workflow_id,
            customer_phone=customer_phone
        )

        assert should_escalate is True
        assert trigger is not None
        # Should get highest confidence trigger (likely legal due to higher base confidence)
        assert trigger.reason in [EscalationReason.ANGER, EscalationReason.LEGAL_REQUEST]

    @pytest.mark.asyncio
    async def test_edge_cases_empty_message(self):
        """Test handling edge cases with empty messages."""
        should_escalate, trigger = await self.service.analyze_message_for_escalation(
            message_text="",
            workflow_id="test-workflow-1",
            customer_phone="+1234567890"
        )

        assert should_escalate is False
        assert trigger is None

    @pytest.mark.asyncio
    async def test_edge_cases_very_long_message(self):
        """Test handling very long messages."""
        message_text = "angry " * 10000  # Very long message
        workflow_id = "test-workflow-1"
        customer_phone = "+1234567890"

        should_escalate, trigger = await self.service.analyze_message_for_escalation(
            message_text=message_text,
            workflow_id=workflow_id,
            customer_phone=customer_phone
        )

        # Should still detect triggers even in long messages
        assert should_escalate is True
        assert trigger is not None
        assert trigger.reason == EscalationReason.ANGER

    @pytest.mark.asyncio
    async def test_error_handling_in_analysis(self):
        """Test error handling during message analysis."""
        # Mock trigger detector to raise exception
        original_detect = self.service.trigger_detector.detect_triggers
        self.service.trigger_detector.detect_triggers = Mock(side_effect=Exception("Test error"))

        with pytest.raises(Exception):
            await self.service.analyze_message_for_escalation(
                message_text="test message",
                workflow_id="test-workflow-1",
                customer_phone="+1234567890"
            )

        # Restore original method
        self.service.trigger_detector.detect_triggers = original_detect

    @pytest.mark.asyncio
    async def test_cleanup_old_timeouts(self):
        """Test cleanup of old timeout entries."""
        # Create old timeout
        old_time = datetime.utcnow() - timedelta(days=10)
        await self.service.register_workflow_timeout(
            workflow_id="old-workflow",
            customer_phone="+1234567890",
            last_ai_response=old_time
        )

        # Mark as escalated to make it eligible for cleanup
        self.service.timeout_monitor.mark_workflow_escalated("old-workflow")

        # Clean up
        removed_count = self.service.timeout_monitor.cleanup_old_timeouts(days_old=7)
        assert removed_count == 1

        # Verify old workflow is removed
        timeout = self.service.timeout_monitor.get_workflow_timeout("old-workflow")
        assert timeout is None