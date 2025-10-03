"""
Tests for workflow service logic.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from app.services.workflow_service import WorkflowService, WorkflowStateTransitionError
from app.models.workflow import (
    WorkflowInstance, WorkflowStep, WorkflowStatus, WorkflowType,
    StepType, StepStatus, WorkflowDB
)
from app.schemas.workflow import (
    CreateWorkflowRequest, UpdateWorkflowStatusRequest,
    CreateWorkflowStepRequest, UpdateWorkflowStepRequest
)


@pytest.fixture
def mock_workflow_db():
    """Mock workflow database fixture."""
    with patch('app.services.workflow_service.WorkflowDB') as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def workflow_service(mock_workflow_db):
    """Workflow service fixture with mocked database."""
    return WorkflowService()


@pytest.fixture
def sample_workflow_instance():
    """Sample workflow instance fixture."""
    return WorkflowInstance(
        id=uuid4(),
        conversation_id=uuid4(),
        workflow_type=WorkflowType.SMS_PROCESSING,
        status=WorkflowStatus.RECEIVED,
        tenant_id="tenant_123",
        phone_number="+1234567890",
        started_at=datetime.utcnow(),
        metadata={"source": "test"}
    )


@pytest.fixture
def sample_create_workflow_request():
    """Sample create workflow request fixture."""
    return CreateWorkflowRequest(
        conversation_id=uuid4(),
        tenant_id="tenant_123",
        phone_number="+1234567890",
        workflow_type=WorkflowType.SMS_PROCESSING,
        metadata={"test": True}
    )


@pytest.fixture
def sample_create_step_request():
    """Sample create workflow step request fixture."""
    return CreateWorkflowStepRequest(
        step_name="test_step",
        step_type=StepType.API_CALL,
        input_data={"test_param": "test_value"}
    )


class TestWorkflowServiceCreate:
    """Test workflow creation methods."""

    @pytest.mark.asyncio
    async def test_create_workflow_instance_success(self, workflow_service, mock_workflow_db, sample_create_workflow_request):
        """Test successful workflow instance creation."""
        mock_workflow_db.create_workflow_instance = AsyncMock(return_value=Mock())
        mock_workflow_db.create_workflow_step = AsyncMock(return_value=Mock())

        with patch('app.services.workflow_service.WorkflowInstance') as mock_workflow_model, \
             patch('app.services.workflow_service.WorkflowStep') as mock_step_model:

            mock_workflow_instance = Mock()
            mock_workflow_instance.id = uuid4()
            mock_workflow_model.return_value = mock_workflow_instance

            mock_step_instance = Mock()
            mock_step_instance.id = uuid4()
            mock_step_model.return_value = mock_step_instance

            result = await workflow_service.create_workflow_instance(sample_create_workflow_request)

            assert result == mock_workflow_instance
            mock_workflow_db.create_workflow_instance.assert_called_once()
            mock_workflow_db.create_workflow_step.assert_called_once()

            # Verify initial step creation
            step_call_args = mock_workflow_db.create_workflow_step.call_args[0][0]
            assert step_call_args.step_name == "workflow_created"
            assert step_call_args.step_type == StepType.DATABASE_OPERATION

    @pytest.mark.asyncio
    async def test_create_workflow_instance_failure(self, workflow_service, mock_workflow_db, sample_create_workflow_request):
        """Test workflow instance creation failure."""
        mock_workflow_db.create_workflow_instance = AsyncMock(
            side_effect=Exception("Database error")
        )

        with patch('app.services.workflow_service.WorkflowInstance'):
            with pytest.raises(Exception, match="Failed to create workflow instance"):
                await workflow_service.create_workflow_instance(sample_create_workflow_request)

    @pytest.mark.asyncio
    async def test_create_workflow_step_success(self, workflow_service, mock_workflow_db, sample_create_step_request):
        """Test successful workflow step creation."""
        workflow_id = uuid4()
        step_id = uuid4()

        with patch('app.services.workflow_service.WorkflowStep') as mock_step_model:
            mock_step_instance = Mock()
            mock_step_instance.id = step_id
            mock_step_model.return_value = mock_step_instance

            mock_workflow_db.create_workflow_step = AsyncMock(return_value=mock_step_instance)

            result = await workflow_service.create_workflow_step(workflow_id, sample_create_step_request)

            assert result == step_id
            mock_workflow_db.create_workflow_step.assert_called_once()

            # Verify step creation parameters
            step_call_args = mock_workflow_db.create_workflow_step.call_args[0][0]
            assert step_call_args.workflow_id == workflow_id
            assert step_call_args.step_name == sample_create_step_request.step_name
            assert step_call_args.step_type == sample_create_step_request.step_type
            assert step_call_args.status == StepStatus.STARTED


class TestWorkflowServiceUpdate:
    """Test workflow update methods."""

    @pytest.mark.asyncio
    async def test_update_workflow_status_valid_transition(self, workflow_service, mock_workflow_db, sample_workflow_instance):
        """Test successful workflow status update with valid transition."""
        workflow_id = sample_workflow_instance.id
        new_status = WorkflowStatus.PROCESSING
        update_request = UpdateWorkflowStatusRequest(status=new_status)

        mock_workflow_db.get_workflow_by_id = AsyncMock(return_value=sample_workflow_instance)
        mock_workflow_db.update_workflow_status = AsyncMock(return_value=True)
        mock_workflow_db.create_workflow_step = AsyncMock(return_value=Mock())

        result = await workflow_service.update_workflow_status(workflow_id, update_request)

        assert result is True
        mock_workflow_db.update_workflow_status.assert_called_once()
        mock_workflow_db.create_workflow_step.assert_called_once()

        # Verify status update parameters
        update_call_args = mock_workflow_db.update_workflow_status.call_args[0]
        assert update_call_args[0] == workflow_id
        assert update_call_args[1] == new_status

    @pytest.mark.asyncio
    async def test_update_workflow_status_invalid_transition(self, workflow_service, mock_workflow_db, sample_workflow_instance):
        """Test workflow status update with invalid transition."""
        workflow_id = sample_workflow_instance.id
        invalid_status = WorkflowStatus.ESCALATED  # Can't transition directly from RECEIVED
        update_request = UpdateWorkflowStatusRequest(status=invalid_status)

        mock_workflow_db.get_workflow_by_conversation = AsyncMock(return_value=sample_workflow_instance)

        with pytest.raises(WorkflowStateTransitionError, match="Invalid transition"):
            await workflow_service.update_workflow_status(workflow_id, update_request)

    @pytest.mark.asyncio
    async def test_update_workflow_status_not_found(self, workflow_service, mock_workflow_db):
        """Test workflow status update for non-existent workflow."""
        workflow_id = uuid4()
        update_request = UpdateWorkflowStatusRequest(status=WorkflowStatus.PROCESSING)

        mock_workflow_db.get_workflow_by_conversation = AsyncMock(return_value=None)

        result = await workflow_service.update_workflow_status(workflow_id, update_request)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_workflow_step_success(self, workflow_service, mock_workflow_db):
        """Test successful workflow step update."""
        step_id = uuid4()
        update_request = UpdateWorkflowStepRequest(
            status=StepStatus.COMPLETED,
            output_data={"result": "success"}
        )

        mock_workflow_db.update_step_status = AsyncMock(return_value=True)

        result = await workflow_service.update_workflow_step(step_id, update_request)

        assert result is True
        mock_workflow_db.update_step_status.assert_called_once_with(
            step_id, StepStatus.COMPLETED, {"result": "success"}, None
        )

    @pytest.mark.asyncio
    async def test_update_workflow_step_failure(self, workflow_service, mock_workflow_db):
        """Test workflow step update failure."""
        step_id = uuid4()
        update_request = UpdateWorkflowStepRequest(status=StepStatus.FAILED)

        mock_workflow_db.update_step_status = AsyncMock(return_value=False)

        result = await workflow_service.update_workflow_step(step_id, update_request)

        assert result is False


class TestWorkflowServiceGet:
    """Test workflow retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_workflow_status_success(self, workflow_service, mock_workflow_db):
        """Test successful workflow status retrieval."""
        conversation_id = uuid4()
        workflow_id = uuid4()

        # Mock workflow instance
        mock_workflow = Mock()
        mock_workflow.id = workflow_id
        mock_workflow.status = WorkflowStatus.PROCESSING
        mock_workflow.started_at = datetime.utcnow()
        mock_workflow.completed_at = None
        mock_workflow.metadata = {"test": "data"}

        # Mock workflow steps
        mock_steps = [
            Mock(id=uuid4(), step_name="step1", status=StepStatus.COMPLETED,
                 started_at=datetime.utcnow(), completed_at=datetime.utcnow(), duration_ms=100),
            Mock(id=uuid4(), step_name="step2", status=StepStatus.STARTED,
                 started_at=datetime.utcnow(), completed_at=None, duration_ms=None)
        ]

        mock_workflow_db.get_workflow_by_id = AsyncMock(return_value=mock_workflow)
        mock_workflow_db.get_workflow_steps = AsyncMock(return_value=mock_steps)

        result = await workflow_service.get_workflow_status(conversation_id)

        assert result is not None
        assert result.conversation_id == conversation_id
        assert result.workflow_id == workflow_id
        assert result.status == WorkflowStatus.PROCESSING
        assert result.steps_completed == 1
        assert len(result.workflow_steps) == 2
        assert result.current_step == "step2"

    @pytest.mark.asyncio
    async def test_get_workflow_status_not_found(self, workflow_service, mock_workflow_db):
        """Test workflow status retrieval for non-existent conversation."""
        conversation_id = uuid4()

        mock_workflow_db.get_workflow_by_conversation = AsyncMock(return_value=None)

        result = await workflow_service.get_workflow_status(conversation_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_workflow_status_with_estimated_completion(self, workflow_service, mock_workflow_db):
        """Test workflow status retrieval with estimated completion calculation."""
        conversation_id = uuid4()

        # Mock workflow instance
        mock_workflow = Mock()
        mock_workflow.id = uuid4()
        mock_workflow.status = WorkflowStatus.PROCESSING
        mock_workflow.started_at = datetime.utcnow()
        mock_workflow.completed_at = None

        # Mock completed steps with durations
        mock_steps = [
            Mock(status=StepStatus.COMPLETED, duration_ms=150),
            Mock(status=StepStatus.COMPLETED, duration_ms=250),
            Mock(status=StepStatus.COMPLETED, duration_ms=200)
        ]

        mock_workflow_db.get_workflow_by_id = AsyncMock(return_value=mock_workflow)
        mock_workflow_db.get_workflow_steps = AsyncMock(return_value=mock_steps)

        result = await workflow_service.get_workflow_status(conversation_id)

        assert result is not None
        assert result.estimated_completion is not None
        # Should be in the future based on average step duration
        assert result.estimated_completion > datetime.utcnow()


class TestWorkflowServiceRecovery:
    """Test workflow recovery methods."""

    @pytest.mark.asyncio
    async def test_handle_workflow_recovery_retry(self, workflow_service, mock_workflow_db):
        """Test workflow recovery with retry strategy."""
        workflow_id = uuid4()
        error_context = {"recovery_strategy": "retry", "error": "timeout"}

        mock_workflow = Mock()
        mock_workflow.status = WorkflowStatus.FAILED

        mock_workflow_db.get_workflow_by_id = AsyncMock(return_value=mock_workflow)
        mock_workflow_db.update_workflow_status = AsyncMock(return_value=True)
        mock_workflow_db.create_workflow_step = AsyncMock(return_value=Mock())

        result = await workflow_service.handle_workflow_recovery(workflow_id, error_context)

        assert result is True
        mock_workflow_db.update_workflow_status.assert_called_once()

        # Verify recovery step creation
        recovery_step = mock_workflow_db.create_workflow_step.call_args[0][0]
        assert recovery_step.step_name == "workflow_recovery"

    @pytest.mark.asyncio
    async def test_handle_workflow_recovery_escalate(self, workflow_service, mock_workflow_db):
        """Test workflow recovery with escalate strategy."""
        workflow_id = uuid4()
        error_context = {"recovery_strategy": "escalate", "error": "low_confidence"}

        mock_workflow = Mock()
        mock_workflow.status = WorkflowStatus.FAILED

        mock_workflow_db.get_workflow_by_id = AsyncMock(return_value=mock_workflow)

        # Mock the update_workflow_status method call
        with patch.object(workflow_service, 'update_workflow_status', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = True

            result = await workflow_service.handle_workflow_recovery(workflow_id, error_context)

            assert result is True
            mock_update.assert_called_once()

            # Verify escalation
            update_call_args = mock_update.call_args[0]
            assert update_call_args[0] == workflow_id
            assert update_call_args[1].status == WorkflowStatus.ESCALATED

    @pytest.mark.asyncio
    async def test_handle_workflow_recovery_not_failed(self, workflow_service, mock_workflow_db):
        """Test workflow recovery for non-failed workflow."""
        workflow_id = uuid4()
        error_context = {"recovery_strategy": "retry"}

        mock_workflow = Mock()
        mock_workflow.status = WorkflowStatus.PROCESSING  # Not failed

        mock_workflow_db.get_workflow_by_id = AsyncMock(return_value=mock_workflow)

        result = await workflow_service.handle_workflow_recovery(workflow_id, error_context)

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_workflow_recovery_not_found(self, workflow_service, mock_workflow_db):
        """Test workflow recovery for non-existent workflow."""
        workflow_id = uuid4()
        error_context = {"recovery_strategy": "retry"}

        mock_workflow_db.get_workflow_by_conversation = AsyncMock(return_value=None)

        result = await workflow_service.handle_workflow_recovery(workflow_id, error_context)

        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_old_workflows(self, workflow_service, mock_workflow_db):
        """Test cleanup of old workflows."""
        days_to_keep = 30
        cleaned_count = 15

        mock_workflow_db.cleanup_old_workflows = AsyncMock(return_value=cleaned_count)

        result = await workflow_service.cleanup_old_workflows(days_to_keep)

        assert result == cleaned_count
        mock_workflow_db.cleanup_old_workflows.assert_called_once_with(days_to_keep)


class TestWorkflowStateTransitions:
    """Test workflow state transition validation."""

    def test_valid_state_transitions(self, workflow_service):
        """Test all valid state transitions."""
        valid_transitions = {
            WorkflowStatus.RECEIVED: [WorkflowStatus.PROCESSING, WorkflowStatus.FAILED],
            WorkflowStatus.PROCESSING: [
                WorkflowStatus.AWAITING_APPROVAL, WorkflowStatus.SENT,
                WorkflowStatus.ESCALATED, WorkflowStatus.FAILED, WorkflowStatus.COMPLETED
            ],
            WorkflowStatus.AWAITING_APPROVAL: [
                WorkflowStatus.SENT, WorkflowStatus.ESCALATED, WorkflowStatus.FAILED
            ],
            WorkflowStatus.SENT: [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED],
            WorkflowStatus.ESCALATED: [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED],
            WorkflowStatus.FAILED: [WorkflowStatus.PROCESSING, WorkflowStatus.ESCALATED],
            WorkflowStatus.COMPLETED: []  # Terminal state
        }

        for current_status, next_statuses in valid_transitions.items():
            for next_status in next_statuses:
                assert workflow_service._validate_state_transition(current_status, next_status) is True

    def test_invalid_state_transitions(self, workflow_service):
        """Test invalid state transitions."""
        invalid_transitions = [
            (WorkflowStatus.RECEIVED, WorkflowStatus.COMPLETED),
            (WorkflowStatus.RECEIVED, WorkflowStatus.ESCALATED),
            (WorkflowStatus.PROCESSING, WorkflowStatus.RECEIVED),
            (WorkflowStatus.AWAITING_APPROVAL, WorkflowStatus.PROCESSING),
            (WorkflowStatus.SENT, WorkflowStatus.AWAITING_APPROVAL),
            (WorkflowStatus.ESCALATED, WorkflowStatus.PROCESSING),
            (WorkflowStatus.COMPLETED, WorkflowStatus.PROCESSING)  # Terminal state
        ]

        for current_status, next_status in invalid_transitions:
            assert workflow_service._validate_state_transition(current_status, next_status) is False

    def test_same_state_transition(self, workflow_service):
        """Test transition to same state (should be allowed)."""
        for status in WorkflowStatus:
            assert workflow_service._validate_state_transition(status, status) is True