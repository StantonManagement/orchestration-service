"""
Tests for the approval workflow service.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from app.services.approval_service import ApprovalService
from app.models.ai_response import AIResponse, AIResponseQueue, ApprovalAuditLog
from app.core.exceptions import ServiceUnavailableError


class TestApprovalService:
    """Test cases for ApprovalService."""

    @pytest.fixture
    def approval_service(self):
        """Create approval service instance."""
        return ApprovalService()

    @pytest.fixture
    def sample_ai_response(self):
        """Create sample AI response."""
        return AIResponse(
            response_text="Thank you for your payment arrangement.",
            confidence_score=Decimal("0.75"),
            language_preference="en",
            tokens_used=50,
        )

    @pytest.fixture
    def sample_workflow_id(self):
        """Create sample workflow ID."""
        return uuid4()

    def test_route_response_by_confidence_auto_send(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test confidence-based routing for auto-send (>85%)."""
        sample_ai_response.confidence_score = Decimal("0.90")

        action = approval_service.route_response_by_confidence(
            sample_ai_response, sample_workflow_id
        )

        assert action == "auto_send"

    def test_route_response_by_confidence_queue_approval(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test confidence-based routing for approval (60-84%)."""
        sample_ai_response.confidence_score = Decimal("0.75")

        action = approval_service.route_response_by_confidence(
            sample_ai_response, sample_workflow_id
        )

        assert action == "queue_for_approval"

    def test_route_response_by_confidence_escalate(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test confidence-based routing for escalation (<60%)."""
        sample_ai_response.confidence_score = Decimal("0.45")

        action = approval_service.route_response_by_confidence(
            sample_ai_response, sample_workflow_id
        )

        assert action == "escalate"

    @pytest.mark.asyncio
    async def test_create_approval_queue_entry(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test creating approval queue entry."""
        tenant_id = "tenant_123"
        phone_number = "+1234567890"
        tenant_message = "I need help with my payment"

        with patch.object(
            approval_service, "_notify_managers_for_approval", new_callable=AsyncMock
        ) as mock_notify:
            mock_notify.return_value = True

            queue_entry = await approval_service.create_approval_queue_entry(
                workflow_id=sample_workflow_id,
                tenant_id=tenant_id,
                phone_number=phone_number,
                tenant_message=tenant_message,
                ai_response=sample_ai_response,
            )

            assert queue_entry.workflow_id == sample_workflow_id
            assert queue_entry.tenant_id == tenant_id
            assert queue_entry.phone_number == phone_number
            assert queue_entry.tenant_message == tenant_message
            assert queue_entry.ai_response == sample_ai_response.response_text
            assert queue_entry.confidence_score == sample_ai_response.confidence_score
            assert queue_entry.status == "pending"
            assert queue_entry.id in approval_service._approval_queue
            assert len(approval_service._approval_queue) == 1

            mock_notify.assert_called_once_with(queue_entry)

    @pytest.mark.asyncio
    async def test_process_approval_action_approve(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test processing approval action - approve."""
        # Create queue entry first
        queue_entry = await approval_service.create_approval_queue_entry(
            workflow_id=sample_workflow_id,
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test message",
            ai_response=sample_ai_response,
        )

        with patch.object(
            approval_service, "_send_approved_response", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            success = await approval_service.process_approval_action(
                queue_id=queue_entry.id, action="approve", manager_id="manager_456"
            )

            assert success is True
            assert queue_entry.status == "approved"
            assert queue_entry.approval_action == "approve"
            assert queue_entry.actioned_by == "manager_456"
            assert queue_entry.actioned_at is not None
            assert len(approval_service._audit_logs) == 1

            audit_log = approval_service._audit_logs[0]
            assert audit_log.response_queue_id == queue_entry.id
            assert audit_log.action == "approve"
            assert audit_log.approved_by == "manager_456"

            mock_send.assert_called_once_with(queue_entry)

    @pytest.mark.asyncio
    async def test_process_approval_action_modify(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test processing approval action - modify."""
        queue_entry = await approval_service.create_approval_queue_entry(
            workflow_id=sample_workflow_id,
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test message",
            ai_response=sample_ai_response,
        )

        with patch.object(
            approval_service, "_send_approved_response", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            success = await approval_service.process_approval_action(
                queue_id=queue_entry.id,
                action="modify",
                manager_id="manager_456",
                modified_text="Modified response text",
            )

            assert success is True
            assert queue_entry.status == "modified"
            assert queue_entry.approval_action == "modify"
            assert queue_entry.modified_response == "Modified response text"
            assert queue_entry.actioned_by == "manager_456"
            assert len(approval_service._audit_logs) == 1

            audit_log = approval_service._audit_logs[0]
            assert audit_log.action == "modify"
            assert audit_log.final_response == "Modified response text"

            mock_send.assert_called_once_with(queue_entry)

    @pytest.mark.asyncio
    async def test_process_approval_action_escalate(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test processing approval action - escalate."""
        queue_entry = await approval_service.create_approval_queue_entry(
            workflow_id=sample_workflow_id,
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test message",
            ai_response=sample_ai_response,
        )

        with patch.object(
            approval_service, "_send_escalation_notification", new_callable=AsyncMock
        ) as mock_notify:
            mock_notify.return_value = True

            success = await approval_service.process_approval_action(
                queue_id=queue_entry.id,
                action="escalate",
                manager_id="manager_456",
                escalation_reason="Tenant disputes amount",
            )

            assert success is True
            assert queue_entry.status == "escalated"
            assert queue_entry.approval_action == "escalate"
            assert queue_entry.actioned_by == "manager_456"
            assert len(approval_service._audit_logs) == 1

            audit_log = approval_service._audit_logs[0]
            assert audit_log.action == "escalate"
            assert audit_log.reason == "Tenant disputes amount"

            mock_notify.assert_called_once_with(queue_entry, "Tenant disputes amount")

    @pytest.mark.asyncio
    async def test_process_approval_action_invalid_queue_id(self, approval_service):
        """Test processing approval action with invalid queue ID."""
        success = await approval_service.process_approval_action(
            queue_id=uuid4(), action="approve", manager_id="manager_456"
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_process_approval_action_invalid_action(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test processing approval action with invalid action."""
        queue_entry = await approval_service.create_approval_queue_entry(
            workflow_id=sample_workflow_id,
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test message",
            ai_response=sample_ai_response,
        )

        success = await approval_service.process_approval_action(
            queue_id=queue_entry.id, action="invalid_action", manager_id="manager_456"
        )

        assert success is False
        assert queue_entry.status == "pending"

    @pytest.mark.asyncio
    async def test_process_approval_action_modify_without_text(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test modify action without providing modified text."""
        queue_entry = await approval_service.create_approval_queue_entry(
            workflow_id=sample_workflow_id,
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test message",
            ai_response=sample_ai_response,
        )

        success = await approval_service.process_approval_action(
            queue_id=queue_entry.id, action="modify", manager_id="manager_456"
        )

        assert success is False
        assert queue_entry.status == "pending"

    @pytest.mark.asyncio
    async def test_process_approval_action_already_processed(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test processing approval action on already processed entry."""
        queue_entry = await approval_service.create_approval_queue_entry(
            workflow_id=sample_workflow_id,
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test message",
            ai_response=sample_ai_response,
        )

        # Mark as already processed
        queue_entry.status = "approved"

        success = await approval_service.process_approval_action(
            queue_id=queue_entry.id, action="approve", manager_id="manager_456"
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_send_approved_response_success(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test successful sending of approved response."""
        queue_entry = await approval_service.create_approval_queue_entry(
            workflow_id=sample_workflow_id,
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test message",
            ai_response=sample_ai_response,
        )

        with patch.object(
            approval_service.sms_client, "send_sms", new_callable=AsyncMock
        ) as mock_sms:
            mock_sms.return_value = "msg_12345"

            success = await approval_service._send_approved_response(queue_entry)

            assert success is True
            mock_sms.assert_called_once_with(
                phone_number="+1234567890", message=sample_ai_response.response_text
            )

    @pytest.mark.asyncio
    async def test_send_approved_response_service_unavailable(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test sending approved response when SMS service is unavailable."""
        queue_entry = await approval_service.create_approval_queue_entry(
            workflow_id=sample_workflow_id,
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test message",
            ai_response=sample_ai_response,
        )

        with patch.object(
            approval_service.sms_client, "send_sms", new_callable=AsyncMock
        ) as mock_sms:
            mock_sms.side_effect = ServiceUnavailableError("SMS Agent", "Service down")

            success = await approval_service._send_approved_response(queue_entry)

            assert success is False

    @pytest.mark.asyncio
    async def test_get_pending_approvals(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test getting pending approvals."""
        # Create multiple queue entries
        entries = []
        for i in range(3):
            entry = await approval_service.create_approval_queue_entry(
                workflow_id=uuid4(),
                tenant_id=f"tenant_{i}",
                phone_number=f"+123456789{i}",
                tenant_message=f"Test message {i}",
                ai_response=sample_ai_response,
            )
            entries.append(entry)

        # Mark one as approved
        entries[1].status = "approved"

        pending = await approval_service.get_pending_approvals()

        assert len(pending) == 2
        assert pending[0].id == entries[0].id  # Should be sorted by created_at
        assert pending[1].id == entries[2].id

    @pytest.mark.asyncio
    async def test_check_approval_timeouts(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test checking for approval timeouts."""
        # Create an old queue entry
        old_entry = await approval_service.create_approval_queue_entry(
            workflow_id=sample_workflow_id,
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test message",
            ai_response=sample_ai_response,
        )

        # Manually set old creation time (24 hours ago + 1 hour)
        old_entry.created_at = datetime.utcnow() - timedelta(hours=25)

        with patch.object(
            approval_service, "_send_escalation_notification", new_callable=AsyncMock
        ) as mock_notify:
            mock_notify.return_value = True

            timed_out = await approval_service.check_approval_timeouts()

            assert len(timed_out) == 1
            assert timed_out[0].id == old_entry.id
            assert timed_out[0].status == "escalated"
            assert timed_out[0].approval_action == "auto_escalate"
            assert timed_out[0].actioned_by == "system"
            assert len(approval_service._audit_logs) == 1  # Only timeout entry

            mock_notify.assert_called_once()

    def test_get_queue_entry(
        self, approval_service, sample_ai_response, sample_workflow_id
    ):
        """Test getting queue entry by ID."""
        # This would need to be adapted to use the async create_approval_queue_entry
        # For now, test with manual entry creation
        queue_id = uuid4()
        queue_entry = AIResponseQueue(
            id=queue_id,
            workflow_id=sample_workflow_id,
            tenant_id="tenant_123",
            phone_number="+1234567890",
            tenant_message="Test message",
            ai_response="Test response",
            confidence_score=Decimal("0.75"),
        )

        approval_service._approval_queue[queue_id] = queue_entry

        retrieved = approval_service.get_queue_entry(queue_id)
        assert retrieved is not None
        assert retrieved.id == queue_id

        # Test non-existent entry
        non_existent = approval_service.get_queue_entry(uuid4())
        assert non_existent is None

    def test_get_audit_logs(self, approval_service):
        """Test getting audit logs."""
        # Create test audit logs
        queue_id = uuid4()
        audit_log1 = ApprovalAuditLog(
            response_queue_id=queue_id,
            action="approve",
            original_response="Original",
            final_response="Final",
            approved_by="manager_123",
        )
        audit_log2 = ApprovalAuditLog(
            response_queue_id=uuid4(),
            action="modify",
            original_response="Original2",
            final_response="Final2",
            approved_by="manager_456",
        )

        approval_service._audit_logs.extend([audit_log1, audit_log2])

        # Get all logs
        all_logs = approval_service.get_audit_logs()
        assert len(all_logs) == 2

        # Get logs filtered by queue ID
        filtered_logs = approval_service.get_audit_logs(queue_id)
        assert len(filtered_logs) == 1
        assert filtered_logs[0].response_queue_id == queue_id
