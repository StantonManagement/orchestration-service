# Error Handling Strategy

**General Approach:**
- **Error Model:** Structured error responses with correlation IDs
- **Exception Hierarchy:** Custom exceptions for different error categories
- **Error Propagation:** Async error propagation with proper logging

**Logging Standards:**
- **Library:** structlog 23+
- **Format:** JSON with correlation ID, timestamp, level, message, context
- **Levels:** DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Required Context:**
  - Correlation ID: UUID per request for tracing
  - Service Context: service name, version, environment
  - User Context: tenant_id, conversation_id, workflow_id

**Error Handling Patterns:**

**External API Errors:**
- **Retry Policy:** Exponential backoff with tenacity (3 attempts, 1s/2s/4s intervals)
- **Circuit Breaker:** 5 failure threshold, 60-second timeout, half-open retry
- **Timeout Configuration:** 30-second HTTP timeout per PRD
- **Error Translation:** External service errors mapped to internal error codes

**Business Logic Errors:**
- **Custom Exceptions:** ValidationException, BusinessRuleException, WorkflowException
- **User-Facing Errors:** Standardized error messages for managers/tenants
- **Error Codes:** ORC_001 (validation), ORC_002 (business rule), ORC_003 (workflow)

**Data Consistency:**
- **Transaction Strategy:** Database transactions for critical operations
- **Compensation Logic:** Workflow status updates on failure
- **Idempotency:** Idempotent workflow creation based on conversation_id
