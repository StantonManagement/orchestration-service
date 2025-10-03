# Epic Details

## Epic 1 Foundation & Core SMS Workflow

This epic establishes the core orchestrator service infrastructure and implements the essential SMS processing workflow that coordinates all external services. The goal is to create a working end-to-end system that can receive tenant SMS messages, generate AI responses, handle approvals, and send responses back to tenants.

### Story 1.1: Service Setup & Basic Health Endpoints
As a developer, I want to set up the basic FastAPI service structure with health endpoints and SMS reception, so that the orchestrator can be monitored and receive incoming SMS data from the SMS Agent.

**Acceptance Criteria:**
1. FastAPI service is initialized with basic health check endpoint (`GET /health`)
2. POST `/orchestrate/sms-received` endpoint is implemented to receive SMS data
3. SMS data model validation is implemented for tenant_id, phone_number, content, and conversation_id
4. Basic logging and error handling for malformed SMS data
5. Service can be started and responds to both health and SMS endpoints
6. Basic health endpoint returns service status, version, and basic health indicators

**Documentation Required:**
- API documentation for `/health` and `/orchestrate/sms-received` endpoints with request/response examples
- Pydantic model documentation for IncomingSMS data structure
- Environment variables configuration guide
- Service startup and basic deployment instructions

**Test Cases:**
```bash
# Basic health check
curl http://localhost:8000/health

# SMS reception endpoint
curl -X POST http://localhost:8000/orchestrate/sms-received \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345",
    "phone_number": "+1234567890",
    "content": "I can pay $200 per week",
    "conversation_id": "conv-uuid-123"
  }'

# Test validation error
curl -X POST http://localhost:8000/orchestrate/sms-received \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+1234567890",
    "content": "test message"
  }'
```

### Story 1.2: External Service Integration
As a developer, I want to integrate with Collections Monitor and SMS Agent services, so that I can retrieve tenant context and conversation history for AI processing.

**Acceptance Criteria:**
1. Service client classes implemented for Collections Monitor and SMS Agent
2. GET `/monitor/tenant/{tenant_id}` integration to retrieve tenant context data
3. GET `/conversations/{phone_number}` integration to retrieve conversation history
4. Error handling and timeout configuration for external service calls
5. Service health check validates connectivity to both external services

**Documentation Required:**
- External service integration documentation
- Service client usage examples
- Error handling and retry configuration guide
- Service dependency health check documentation

**Test Cases:**
```bash
# Test service health with dependencies
curl http://localhost:8000/health/dependencies

# Test with mock external services running
# (Assuming Collections Monitor on 8001, SMS Agent on 8002)
curl http://localhost:8001/monitor/tenant/12345
curl http://localhost:8002/conversations/%2B1234567890
```

### Story 1.3: AI Response Generation
As a developer, I want to integrate with OpenAI API to generate contextual responses, so that tenant communications are personalized and relevant to their situation.

**Acceptance Criteria:**
1. OpenAI client integration with API key configuration
2. System prompt generation using tenant context and conversation history
3. AI response generation with confidence score calculation
4. Response formatting to meet SMS character limits and language preferences
5. Error handling for OpenAI API failures with retry logic

**Documentation Required:**
- OpenAI integration configuration guide
- System prompt template documentation
- Confidence score calculation methodology
- Response formatting and language preference handling

**Test Cases:**
```bash
# Test AI response generation (requires valid OpenAI key)
# This would be tested through the main SMS endpoint
curl -X POST http://localhost:8000/orchestrate/sms-received \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345",
    "phone_number": "+1234567890",
    "content": "When can I pay?",
    "conversation_id": "conv-uuid-456"
  }'
```

### Story 1.4: Approval Workflow Implementation
As a developer, I want to implement the approval workflow endpoints and routing logic, so that AI responses can be automatically sent, queued for approval, or escalated based on confidence scores.

**Acceptance Criteria:**
1. POST `/orchestrate/approve-response` endpoint implemented for manager approvals
2. Confidence-based routing logic (>85% auto-send, 60-84% approval, <60% escalation)
3. Approval queue data model and database storage implemented
4. POST `/sms/send` integration to send approved responses to tenants
5. POST `/notifications/send` integration to notify managers of required approvals

**Documentation Required:**
- Approval workflow documentation with flow diagram
- Confidence scoring thresholds and routing logic
- Approval queue data model documentation
- Manager approval API usage guide

**Test Cases:**
```bash
# Test approval endpoint
curl -X POST http://localhost:8000/orchestrate/approve-response \
  -H "Content-Type: application/json" \
  -d '{
    "response_queue_id": "queue-uuid-123",
    "action": "approve",
    "approved_text": "Thank you for your payment arrangement.",
    "manager_id": "manager-001"
  }'

# Test modify action
curl -X POST http://localhost:8000/orchestrate/approve-response \
  -H "Content-Type: application/json" \
  -d '{
    "response_queue_id": "queue-uuid-123",
    "action": "modify",
    "modified_text": "Thank you. We can arrange $200/week for 8 weeks starting next Friday.",
    "manager_id": "manager-001"
  }'

# Test escalate action
curl -X POST http://localhost:8000/orchestrate/approve-response \
  -H "Content-Type: application/json" \
  -d '{
    "response_queue_id": "queue-uuid-123",
    "action": "escalate",
    "escalation_reason": "Tenant disputes amount owed",
    "manager_id": "manager-001"
  }'
```

### Story 1.5: Workflow Status Tracking
As a developer, I want to track workflow status and provide visibility into processing states, so that managers can monitor the progress of tenant conversations.

**Acceptance Criteria:**
1. GET `/orchestrate/workflow/{conversation_id}/status` endpoint implemented
2. Workflow state machine with status tracking (received, processing, awaiting_approval, sent, escalated)
3. Database schema for workflow tracking with audit trail
4. Status updates at each step of the SMS processing workflow
5. Error handling with workflow state recovery capabilities

**Documentation Required:**
- Workflow state diagram documentation
- Database schema for workflow tracking
- Status API usage examples
- Audit trail documentation

**Test Cases:**
```bash
# Test workflow status endpoint
curl http://localhost:8000/orchestrate/workflow/conv-uuid-123/status

# Test non-existent conversation
curl http://localhost:8000/orchestrate/workflow/non-conv/status
```

## Epic 2 Payment Plan Processing & Escalation

This epic implements the business logic for automatically detecting and processing payment plans from tenant conversations, along with the escalation mechanisms for handling problematic situations that require human intervention.

### Story 2.1: Payment Plan Detection
As a collections system, I want to automatically detect payment plan offers in tenant messages, so that payment arrangements can be processed efficiently without manual intervention.

**Acceptance Criteria:**
1. Payment plan extraction logic with pattern matching for weekly amounts and durations
2. POST `/orchestrate/payment-plan-detected` endpoint to process extracted payment plans
3. Payment plan validation against business rules (max 12 weeks, minimum $25/week)
4. Integration with AI response parsing to identify structured payment plans
5. Database storage of detected payment plans with validation results

**Documentation Required:**
- Payment plan extraction pattern documentation
- Business rules validation documentation
- Payment plan data model specification
- Integration workflow documentation

**Test Cases:**
```bash
# Test payment plan detection endpoint
curl -X POST http://localhost:8000/orchestrate/payment-plan-detected \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv-uuid-123",
    "tenant_id": "12345",
    "message_content": "I can pay $200 per week for 8 weeks",
    "ai_response": "PAYMENT_PLAN: weekly=200, weeks=8, start=2025-01-08"
  }'

# Test invalid payment plan
curl -X POST http://localhost:8000/orchestrate/payment-plan-detected \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv-uuid-456",
    "tenant_id": "12345",
    "message_content": "I can only pay $10 per week",
    "ai_response": "This payment plan is too low"
  }'
```

### Story 2.2: Escalation Logic Implementation
As a collections system, I want to automatically escalate conversations based on content and timing triggers, so that problematic situations receive appropriate human attention.

**Acceptance Criteria:**
1. POST `/orchestrate/escalate` endpoint implemented for manual and automatic escalations
2. Escalation trigger detection for hostile language, payment disputes, and unrealistic proposals
3. 36-hour timeout escalation for conversations with no tenant response
4. POST `/notifications/send` integration to alert managers of escalations
5. Escalation tracking and audit trail in the database

**Documentation Required:**
- Escalation trigger rules documentation
- Timeout escalation logic documentation
- Escalation types and severity levels
- Manager notification workflow documentation

**Test Cases:**
```bash
# Test manual escalation
curl -X POST http://localhost:8000/orchestrate/escalate \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv-uuid-123",
    "escalation_type": "hostile_language",
    "reason": "Tenant mentioned lawyer and legal action",
    "severity": "high",
    "auto_detected": false
  }'

# Test timeout escalation
curl -X POST http://localhost:8000/orchestrate/escalate \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv-uuid-456",
    "escalation_type": "no_response",
    "reason": "No response for 36 hours",
    "severity": "medium",
    "auto_detected": true
  }'
```

## Epic 3 Monitoring & Reliability

This epic ensures the orchestrator service is production-ready with comprehensive error handling, retry mechanisms, circuit breakers, and observability features to maintain reliable operation in a production environment.

### Story 3.1: Error Handling & Circuit Breakers
As a developer, I want to implement resilient error handling and circuit breakers, so that temporary failures in external services don't compromise the entire system.

**Acceptance Criteria:**
1. Circuit breaker implementation for external service calls with failure thresholds
2. Retry logic with exponential backoff for transient failures
3. Graceful degradation when external services are unavailable
4. Custom exception classes with standardized error responses
5. GET `/health/dependencies` endpoint showing service health status

**Documentation Required:**
- Circuit breaker configuration documentation
- Retry policy documentation
- Error response format specification
- Degradation mode documentation

**Test Cases:**
```bash
# Test dependency health check
curl http://localhost:8000/health/dependencies

# Test circuit breaker behavior
# (Stop external services and test graceful degradation)
# Stop SMS Agent (port 8002) and test SMS processing
curl -X POST http://localhost:8000/orchestrate/sms-received \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345",
    "phone_number": "+1234567890",
    "content": "test message",
    "conversation_id": "conv-uuid-test"
  }'
```

### Story 3.2: Metrics & Monitoring
As a system administrator, I want to monitor system performance and throughput metrics, so that I can ensure the service is meeting performance requirements and identify issues proactively.

**Acceptance Criteria:**
1. GET `/orchestrate/metrics` endpoint implementation
2. Metrics collection for SMS volume, response times, approval rates, and escalations
3. Structured logging with correlation IDs for request tracing
4. Performance monitoring for processing times and throughput
5. Dashboard-ready metrics format for monitoring systems

**Documentation Required:**
- Metrics format and documentation
- Logging format and correlation ID documentation
- Performance monitoring setup guide
- Dashboard integration documentation

**Test Cases:**
```bash
# Test metrics endpoint
curl http://localhost:8000/orchestrate/metrics

# Generate some traffic and check metrics
for i in {1..5}; do
  curl -X POST http://localhost:8000/orchestrate/sms-received \
    -H "Content-Type: application/json" \
    -d "{
      \"tenant_id\": \"12345\",
      \"phone_number\": \"+1234567890\",
      \"content\": \"test message $i\",
      \"conversation_id\": \"conv-uuid-$i\"
    }"
done

# Check metrics after generating traffic
curl http://localhost:8000/orchestrate/metrics
```

### Story 3.3: Workflow Retry Mechanism
As a system administrator, I want to manually retry failed workflows, so that temporary issues don't permanently block tenant communications.

**Acceptance Criteria:**
1. POST `/orchestrate/retry/{workflow_id}` endpoint implemented for manual workflow retries
2. Failed workflow state validation to ensure retry is appropriate
3. Workflow retry history tracking for audit purposes
4. Retry limit enforcement to prevent infinite retry loops
5. Integration with existing circuit breaker and retry logic

**Documentation Required:**
- Workflow retry mechanism documentation
- Retry state validation rules
- Retry limit configuration guide
- Audit trail documentation for retry attempts

**Test Cases:**
```bash
# Test workflow retry endpoint
curl -X POST http://localhost:8000/orchestrate/retry/workflow-uuid-123 \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Temporary external service failure resolved"
  }'

# Test retry on non-existent workflow
curl -X POST http://localhost:8000/orchestrate/retry/non-existent-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Test retry"
  }'

# Test retry on workflow that cannot be retried
curl -X POST http://localhost:8000/orchestrate/retry/workflow-uuid-completed \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Should not retry completed workflow"
  }'
```
