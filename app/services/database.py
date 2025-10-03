"""Database service integration with Supabase."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from supabase import create_client

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class DatabaseService:
    """Service for database operations using Supabase."""

    def __init__(self):
        self.client = None
        try:
            self.client = create_client(str(settings.supabase_url), settings.supabase_key)
            self._ensure_tables_exist()
        except Exception as e:
            logger.warning("Database connection failed, running in mock mode", error=str(e))

    def _ensure_tables_exist(self):
        """Ensure required tables exist in the database."""
        try:
            # Check if tables exist by attempting to query them
            self.client.table('orchestration_workflows').select('id').limit(1).execute()
            self.client.table('ai_response_queue').select('id').limit(1).execute()
            self.client.table('approval_audit_log').select('id').limit(1).execute()
            logger.info("Database tables verified successfully")
        except Exception as e:
            logger.warning("Database tables may not exist. Run migrations to create them.", error=str(e))

    # Orchestration Workflows
    async def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new orchestration workflow."""
        if not self.client:
            logger.warning("Mock mode: creating workflow", workflow_id=workflow_data.get("id"))
            return {"id": workflow_data.get("id"), "status": "created_mock"}

        try:
            workflow_data["started_at"] = datetime.utcnow().isoformat()
            response = self.client.table('orchestration_workflows').insert(workflow_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error("Failed to create workflow", error=str(e))
            raise

    async def get_workflow(self, workflow_id: UUID) -> Optional[Dict[str, Any]]:
        """Get workflow by ID."""
        try:
            response = self.client.table('orchestration_workflows').select('*').eq('id', str(workflow_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error("Failed to get workflow", workflow_id=str(workflow_id), error=str(e))
            return None

    async def get_workflow_by_conversation(self, conversation_id: UUID) -> Optional[Dict[str, Any]]:
        """Get workflow by conversation ID."""
        try:
            response = self.client.table('orchestration_workflows').select('*').eq('conversation_id', str(conversation_id)).order('created_at', desc=True).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error("Failed to get workflow by conversation", conversation_id=str(conversation_id), error=str(e))
            return None

    async def update_workflow(self, workflow_id: UUID, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update workflow status and metadata."""
        try:
            update_data["updated_at"] = datetime.utcnow().isoformat()
            response = self.client.table('orchestration_workflows').update(update_data).eq('id', str(workflow_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error("Failed to update workflow", workflow_id=str(workflow_id), error=str(e))
            raise

    async def list_workflows(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List workflows with optional filtering."""
        try:
            query = self.client.table('orchestration_workflows').select('*').order('started_at', desc=True)

            if status:
                query = query.eq('status', status)

            query = query.range(offset, offset + limit - 1)
            response = query.execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error("Failed to list workflows", error=str(e))
            return []

    # AI Response Queue
    async def create_ai_response_queue(self, queue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new AI response queue entry."""
        try:
            queue_data["created_at"] = datetime.utcnow().isoformat()
            response = self.client.table('ai_response_queue').insert(queue_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error("Failed to create AI response queue entry", error=str(e))
            raise

    async def get_pending_responses(self) -> List[Dict[str, Any]]:
        """Get all pending AI responses awaiting approval."""
        try:
            response = self.client.table('ai_response_queue').select('*').eq('status', 'pending').order('created_at').execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error("Failed to get pending responses", error=str(e))
            return []

    async def get_response_queue(self, queue_id: UUID) -> Optional[Dict[str, Any]]:
        """Get response queue entry by ID."""
        try:
            response = self.client.table('ai_response_queue').select('*').eq('id', str(queue_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error("Failed to get response queue entry", queue_id=str(queue_id), error=str(e))
            return None

    async def update_response_queue(self, queue_id: UUID, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update response queue entry."""
        try:
            if 'actioned_at' not in update_data:
                update_data['actioned_at'] = datetime.utcnow().isoformat()

            response = self.client.table('ai_response_queue').update(update_data).eq('id', str(queue_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error("Failed to update response queue", queue_id=str(queue_id), error=str(e))
            raise

    # Approval Audit Log
    async def create_approval_audit_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create approval audit log entry."""
        try:
            log_data["created_at"] = datetime.utcnow().isoformat()
            response = self.client.table('approval_audit_log').insert(log_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error("Failed to create approval audit log", error=str(e))
            raise

    async def get_approval_logs(self, response_queue_id: UUID) -> List[Dict[str, Any]]:
        """Get approval logs for a response queue entry."""
        try:
            response = self.client.table('approval_audit_log').select('*').eq('response_queue_id', str(response_queue_id)).order('created_at').execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error("Failed to get approval logs", response_queue_id=str(response_queue_id), error=str(e))
            return []

    # Health Check
    async def health_check(self) -> bool:
        """Check database connectivity."""
        if not self.client:
            return False  # Mock mode - not healthy

        try:
            # Simple query to test connectivity
            self.client.table('orchestration_workflows').select('id').limit(1).execute()
            return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False

    # Metrics
    async def get_workflow_metrics(self) -> Dict[str, Any]:
        """Get workflow metrics for monitoring."""
        try:
            # Get today's workflows
            today = datetime.utcnow().date()
            today_iso = today.isoformat()

            # Total workflows today
            total_response = self.client.table('orchestration_workflows').select('id').gte('started_at', today_iso).execute()
            total_today = len(total_response.data) if total_response.data else 0

            # Workflows by status
            status_response = self.client.table('orchestration_workflows').select('status').gte('started_at', today_iso).execute()
            status_breakdown = {}
            if status_response.data:
                for workflow in status_response.data:
                    status = workflow.get('status', 'unknown')
                    status_breakdown[status] = status_breakdown.get(status, 0) + 1

            # Pending approvals
            pending_response = self.client.table('ai_response_queue').select('id').eq('status', 'pending').execute()
            pending_approvals = len(pending_response.data) if pending_response.data else 0

            # Escalations today
            escalation_response = self.client.table('orchestration_workflows').select('id').eq('status', 'escalated').gte('started_at', today_iso).execute()
            escalations_today = len(escalation_response.data) if escalation_response.data else 0

            return {
                "total_workflows_today": total_today,
                "status_breakdown": status_breakdown,
                "pending_approvals": pending_approvals,
                "escalations_today": escalations_today
            }

        except Exception as e:
            logger.error("Failed to get workflow metrics", error=str(e))
            return {}

    # Retry tracking
    async def create_retry_attempt(self, workflow_id: UUID, reason: str) -> Dict[str, Any]:
        """Create retry attempt record."""
        try:
            retry_data = {
                "workflow_id": str(workflow_id),
                "reason": reason,
                "attempted_at": datetime.utcnow().isoformat()
            }
            response = self.client.table('workflow_retry_attempts').insert(retry_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error("Failed to create retry attempt", workflow_id=str(workflow_id), error=str(e))
            raise

    async def get_retry_attempts(self, workflow_id: UUID) -> List[Dict[str, Any]]:
        """Get retry attempts for a workflow."""
        try:
            response = self.client.table('workflow_retry_attempts').select('*').eq('workflow_id', str(workflow_id)).order('attempted_at').execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error("Failed to get retry attempts", workflow_id=str(workflow_id), error=str(e))
            return []


# Create global database service instance
db_service = DatabaseService()