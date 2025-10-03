"""
Database connection and operations for the System Orchestrator Service.
"""
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from app.models.ai_response import AIResponseQueue, ApprovalAuditLog
import structlog

logger = structlog.get_logger(__name__)


class DatabaseService:
    """
    Database service for approval queue and audit log operations.

    Currently implements in-memory storage for development.
    In production, this would integrate with Supabase/PostgreSQL.
    """

    def __init__(self):
        # In-memory storage for demo purposes
        self._approval_queue: Dict[UUID, AIResponseQueue] = {}
        self._audit_logs: List[ApprovalAuditLog] = []

    async def create_queue_entry(self, queue_entry: AIResponseQueue) -> AIResponseQueue:
        """
        Create a new approval queue entry.

        Args:
            queue_entry: Approval queue entry to create

        Returns:
            Created queue entry with generated ID
        """
        # In production: INSERT INTO ai_response_queue ...
        self._approval_queue[queue_entry.id] = queue_entry

        logger.info(
            "Created queue entry in database",
            queue_id=str(queue_entry.id),
            workflow_id=str(queue_entry.workflow_id),
            tenant_id=queue_entry.tenant_id,
            confidence_score=float(queue_entry.confidence_score),
        )

        return queue_entry

    async def update_queue_status(
        self,
        queue_id: UUID,
        status: str,
        approval_action: Optional[str] = None,
        modified_response: Optional[str] = None,
        actioned_by: Optional[str] = None,
        actioned_at: Optional[datetime] = None,
    ) -> bool:
        """
        Update approval queue entry status.

        Args:
            queue_id: Queue entry ID
            status: New status
            approval_action: Manager action taken
            modified_response: Modified response text
            actioned_by: Manager ID
            actioned_at: Action timestamp

        Returns:
            True if successful, False otherwise
        """
        if queue_id not in self._approval_queue:
            logger.warning(
                "Queue entry not found for status update",
                queue_id=str(queue_id),
                status=status,
            )
            return False

        # In production: UPDATE ai_response_queue SET ...
        queue_entry = self._approval_queue[queue_id]
        queue_entry.status = status
        if approval_action:
            queue_entry.approval_action = approval_action
        if modified_response:
            queue_entry.modified_response = modified_response
        if actioned_by:
            queue_entry.actioned_by = actioned_by
        if actioned_at:
            queue_entry.actioned_at = actioned_at

        logger.info(
            "Updated queue entry status",
            queue_id=str(queue_id),
            new_status=status,
            approval_action=approval_action,
            actioned_by=actioned_by,
        )

        return True

    async def get_queue_entry(self, queue_id: UUID) -> Optional[AIResponseQueue]:
        """
        Get approval queue entry by ID.

        Args:
            queue_id: Queue entry ID

        Returns:
            Queue entry if found, None otherwise
        """
        # In production: SELECT * FROM ai_response_queue WHERE id = $1
        return self._approval_queue.get(queue_id)

    async def get_pending_approvals(self) -> List[AIResponseQueue]:
        """
        Get all pending approval requests.

        Returns:
            List of pending approval queue entries
        """
        # In production: SELECT * FROM ai_response_queue WHERE status = 'pending' ORDER BY created_at
        pending_approvals = [
            entry
            for entry in self._approval_queue.values()
            if entry.status == "pending"
        ]

        # Sort by creation time (oldest first)
        pending_approvals.sort(key=lambda x: x.created_at)

        logger.info(
            "Retrieved pending approvals from database", count=len(pending_approvals)
        )

        return pending_approvals

    async def get_entries_by_workflow(self, workflow_id: UUID) -> List[AIResponseQueue]:
        """
        Get all approval queue entries for a workflow.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            List of queue entries for the workflow
        """
        # In production: SELECT * FROM ai_response_queue WHERE workflow_id = $1
        entries = [
            entry
            for entry in self._approval_queue.values()
            if entry.workflow_id == workflow_id
        ]

        entries.sort(key=lambda x: x.created_at)
        return entries

    async def create_approval_audit_log(
        self, audit_log: ApprovalAuditLog
    ) -> ApprovalAuditLog:
        """
        Create an approval audit log entry.

        Args:
            audit_log: Audit log entry to create

        Returns:
            Created audit log entry
        """
        # In production: INSERT INTO approval_audit_log ...
        self._audit_logs.append(audit_log)

        logger.info(
            "Created audit log entry",
            audit_id=str(audit_log.id),
            queue_id=str(audit_log.response_queue_id),
            action=audit_log.action,
            approved_by=audit_log.approved_by,
        )

        return audit_log

    async def get_audit_logs(
        self,
        queue_id: Optional[UUID] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[ApprovalAuditLog]:
        """
        Get audit logs with optional filtering.

        Args:
            queue_id: Optional queue ID to filter logs
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            List of audit log entries
        """
        # In production: SELECT * FROM approval_audit_log WHERE response_queue_id = $1 ORDER BY created_at DESC
        logs = self._audit_logs.copy()

        if queue_id:
            logs = [log for log in logs if log.response_queue_id == queue_id]

        # Sort by creation time (newest first)
        logs.sort(key=lambda x: x.created_at, reverse=True)

        # Apply pagination
        if offset:
            logs = logs[offset:]
        if limit:
            logs = logs[:limit]

        logger.info(
            "Retrieved audit logs from database",
            count=len(logs),
            queue_id_filter=str(queue_id) if queue_id else None,
            limit=limit,
            offset=offset,
        )

        return logs

    async def get_approval_statistics(self) -> Dict[str, Any]:
        """
        Get approval workflow statistics.

        Returns:
            Dictionary with approval statistics
        """
        total_entries = len(self._approval_queue)
        pending_count = sum(
            1 for entry in self._approval_queue.values() if entry.status == "pending"
        )
        approved_count = sum(
            1 for entry in self._approval_queue.values() if entry.status == "approved"
        )
        modified_count = sum(
            1 for entry in self._approval_queue.values() if entry.status == "modified"
        )
        escalated_count = sum(
            1 for entry in self._approval_queue.values() if entry.status == "escalated"
        )
        auto_sent_count = sum(
            1 for entry in self._approval_queue.values() if entry.status == "auto_sent"
        )

        total_audit_logs = len(self._audit_logs)

        stats = {
            "total_queue_entries": total_entries,
            "pending_approvals": pending_count,
            "approved_responses": approved_count,
            "modified_responses": modified_count,
            "escalated_responses": escalated_count,
            "auto_sent_responses": auto_sent_count,
            "total_audit_logs": total_audit_logs,
            "approval_rate": round((approved_count / total_entries) * 100, 2)
            if total_entries > 0
            else 0,
            "escalation_rate": round((escalated_count / total_entries) * 100, 2)
            if total_entries > 0
            else 0,
        }

        logger.info("Retrieved approval statistics", stats=stats)

        return stats

    async def cleanup_old_entries(self, days_old: int = 30) -> int:
        """
        Clean up old queue entries and audit logs.

        Args:
            days_old: Age in days for entries to be considered old

        Returns:
            Number of entries cleaned up
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        # Clean up old queue entries
        old_queue_ids = [
            queue_id
            for queue_id, entry in self._approval_queue.items()
            if entry.created_at < cutoff_date
            and entry.status in ["approved", "modified", "escalated", "auto_sent"]
        ]

        for queue_id in old_queue_ids:
            del self._approval_queue[queue_id]

        # Clean up old audit logs
        self._audit_logs = [
            log for log in self._audit_logs if log.created_at >= cutoff_date
        ]

        total_cleaned = len(old_queue_ids)

        logger.info(
            "Cleaned up old database entries",
            days_old=days_old,
            queue_entries_cleaned=len(old_queue_ids),
            audit_logs_kept=len(self._audit_logs),
        )

        return total_cleaned

    async def health_check(self) -> bool:
        """
        Check database connectivity.

        Returns:
            True if database is healthy, False otherwise
        """
        # In production: Check actual database connection
        try:
            # For in-memory storage, always healthy
            logger.info("Database health check passed")
            return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False


def get_supabase_client():
    """
    Get Supabase client for database operations.

    Returns:
        Supabase client instance
    """
    # This is a placeholder - in production, this would initialize
    # the actual Supabase client with proper authentication
    from app.config import settings

    # For now, return a mock client that will be replaced
    # with actual Supabase integration
    class MockSupabaseClient:
        def __init__(self):
            pass

        def table(self, table_name):
            return MockTableQuery(table_name)

    class MockTableQuery:
        def __init__(self, table_name):
            self.table_name = table_name
            self.data = []

        def select(self, columns="*"):
            return self

        def insert(self, data):
            return MockResponse([data])

        def update(self, data):
            return MockResponse([data])

        def delete(self):
            return MockResponse([{"deleted": 1}])

        def eq(self, column, value):
            return self

        def single(self):
            return self

        def order(self, column):
            return self

        def lt(self, column, value):
            return self

        def execute(self):
            return MockResponse(self.data)

    class MockResponse:
        def __init__(self, data):
            self.data = data

    return MockSupabaseClient()


# Global database service instance
database_service = DatabaseService()
