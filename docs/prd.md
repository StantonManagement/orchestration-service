# System Orchestrator Service Product Requirements Document (PRD)

## Goals and Background Context

### Goals
- Build the central orchestration service that coordinates all collections system components into a working end-to-end system
- Implement AI-powered response generation with confidence scoring for tenant communications
- Create an approval workflow for manager oversight of AI-generated responses
- Extract and process payment plans from tenant conversations automatically
- Handle escalations intelligently based on conversation content and timing
- Provide comprehensive metrics and monitoring for the collections workflow

### Background Context
The collections system currently has individual services (SMS Agent, Collections Monitor, Notification Service) but lacks a central coordinator to make them work together. This orchestrator service will be the "brain" that receives incoming SMS, generates contextual AI responses using tenant data, manages approval workflows, and coordinates outbound communications. Without this component, the existing services cannot function as a complete collections workflow, leaving tenant communications unprocessed and payment plan negotiations unautomated.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-02 | 1.0 | Initial PRD creation based on Kurt's orchestration specification | John (PM) |
| 2025-10-02 | 1.1 | Updated endpoint alignment and added missing endpoints from Kurt's spec | Sarah (PO) |

## Requirements

### Functional Requirements

FR1: The orchestrator shall expose a POST `/orchestrate/sms-received` endpoint that receives incoming SMS data from the SMS Agent and initiates the complete workflow processing

FR2: The orchestrator shall call `GET /monitor/tenant/{tenant_id}` on the Collections Monitor service to retrieve tenant context information for each incoming SMS

FR3: The orchestrator shall call `GET /conversations/{phone_number}` on the SMS Agent service to retrieve conversation history for AI context generation

FR4: The orchestrator shall integrate with OpenAI API to generate contextual responses for tenant communications using tenant data and conversation history

FR5: The orchestrator shall calculate confidence scores for AI-generated responses and route them based on threshold values (>85% auto-send, 60-84% manual approval, <60% escalation)

FR6: The orchestrator shall expose a POST `/orchestrate/approve-response` endpoint for managers to approve, modify, or escalate AI-generated responses

FR7: The orchestrator shall call `POST /sms/send` on the SMS Agent service to send approved responses to tenants

FR8: The orchestrator shall call `POST /notifications/send` on the Notification service to alert managers when manual approval or escalation is required

FR9: The orchestrator shall automatically extract payment plan information from tenant messages using pattern matching and AI response parsing

FR10: The orchestrator shall expose a POST `/orchestrate/payment-plan-detected` endpoint to process extracted payment plans and validate them against business rules

FR11: The orchestrator shall implement automatic escalation logic based on triggers like hostile language, payment disputes, unrealistic proposals, and timeout periods

FR12: The orchestrator shall expose a POST `/orchestrate/escalate` endpoint to handle manual and automatic escalations

FR13: The orchestrator shall expose a GET `/orchestrate/workflow/{conversation_id}/status` endpoint to track workflow status for individual conversations

FR14: The orchestrator shall expose a GET `/orchestrate/metrics` endpoint providing metrics on SMS volume, response times, approval rates, and escalations

FR15: The orchestrator shall expose a GET `/health` endpoint for basic service health checks and service status verification

FR16: The orchestrator shall expose a GET `/health/dependencies` endpoint to monitor the health of all connected services

FR17: The orchestrator shall expose a POST `/orchestrate/retry/{workflow_id}` endpoint to manually retry failed workflows

FR18: The orchestrator shall implement circuit breaker patterns and retry logic for resilient communication with external services

### Non-Functional Requirements

NFR1: The orchestrator shall process each incoming SMS within 2 seconds of receipt

NFR2: The orchestrator shall handle 100 concurrent SMS processing operations without degradation

NFR3: The orchestrator shall achieve 99.9% uptime with automated failover and recovery mechanisms

NFR4: The orchestrator shall maintain comprehensive audit logs of all workflow steps, decisions, and API calls

NFR5: The orchestrator shall secure all API endpoints with appropriate authentication and authorization mechanisms

NFR6: The orchestrator shall handle service dependencies gracefully with circuit breakers and retry logic

NFR7: The orchestrator shall achieve 80% test coverage including unit, integration, and load tests

NFR8: The orchestrator shall support multi-language tenant communications based on language preference data

NFR9: The orchestrator shall validate all payment plans against configurable business rules (max weeks, minimum payments, coverage requirements)

NFR10: The orchestrator shall maintain database state for workflow tracking, approval queues, and audit trails using Supabase

NFR11: The orchestrator shall provide comprehensive error handling and recovery mechanisms for failed workflows including manual retry capabilities

## Technical Assumptions

### Repository Structure: Monorepo
The orchestrator service will be developed as a standalone FastAPI service within its own repository, as it's a distinct microservice with clear boundaries and dependencies.

### Service Architecture: Microservices
The orchestrator follows a microservices pattern, coordinating between existing services (Collections Monitor, SMS Agent, Notification Service) via HTTP APIs. This service acts as the central coordinator but maintains separation of concerns from other services.

### Testing Requirements: Full Testing Pyramid
Unit tests for individual components (AI prompt generation, payment plan extraction), integration tests for service-to-service communication, end-to-end tests for complete workflows, and load tests for performance validation. Target 80% coverage as specified in requirements.

### Additional Technical Assumptions and Requests

- **Framework**: FastAPI with Python 3.11+ for async support and automatic OpenAPI documentation
- **Database**: Supabase (PostgreSQL) for workflow tracking, approval queues, and audit logs
- **AI Integration**: OpenAI API with GPT-4-turbo for response generation
- **HTTP Client**: httpx for async HTTP communication with external services
- **Circuit Breaker**: Custom implementation using tenacity for retry logic
- **Authentication**: JWT-based authentication for internal service communication
- **Monitoring**: Prometheus metrics with structured logging
- **Environment Configuration**: All external service URLs and API keys configured via environment variables
- **Containerization**: Docker with multi-stage builds for deployment
- **Error Handling**: Comprehensive error handling with custom exception classes and standardized error responses
- **Timeout Configuration**: 30-second timeouts for external service calls with configurable retry policies
- **Background Tasks**: FastAPI BackgroundTasks for non-blocking operations
- **Port Configuration**: Orchestrator will run on port 8000 to avoid conflicts with existing services (8001-8003)

## Epic List

### Epic 1: Foundation & Core SMS Workflow
Establish the orchestrator service with the primary SMS processing workflow - receiving SMS, integrating with external services, and implementing the core approval mechanism.

### Epic 2: Payment Plan Processing & Escalation
Implement automated payment plan extraction, validation, and escalation handling to complete the business logic capabilities.

### Epic 3: Monitoring & Reliability
Add comprehensive error handling, circuit breakers, retry logic, and metrics collection to ensure the service is production-ready and observable.

## Epic Details

### Epic 1 Foundation & Core SMS Workflow

This epic establishes the core orchestrator service infrastructure and implements the essential SMS processing workflow that coordinates all external services. The goal is to create a working end-to-end system that can receive tenant SMS messages, generate AI responses, handle approvals, and send responses back to tenants.

#### Story 1.0: Project Infrastructure Setup
As a developer, I want to set up the complete project infrastructure, so that I have a solid foundation for building the orchestrator service.

**Acceptance Criteria:**
1. Python virtual environment created and activated (Python 3.11+)
2. requirements.txt created with all dependencies (FastAPI, httpx, openai, supabase, tenacity, pydantic)
3. .env.example file created with all required environment variables
4. .env file created from template with placeholder values
5. Basic FastAPI project structure established (app/main.py, app/models/, app/services/, app/api/)
6. Dockerfile created with multi-stage build configuration
7. docker-compose.yml created for local development environment
8. Basic pyproject.toml or setup.py for project configuration

**Documentation Required:**
- Development environment setup guide
- Environment variables configuration reference
- Docker usage instructions
- Project structure documentation
- Dependency installation guide

**Test Cases:**
```bash
# Verify Python version
python --version  # Should show 3.11+

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify FastAPI installation
python -c "import fastapi; print(fastapi.__version__)"

# Test Docker setup
docker build -t orchestrator .
docker run --rm orchestrator python --version

# Test docker-compose
docker-compose up --build
```

#### Story 1.1: Service Setup & Basic Health Endpoints
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

#### Story 1.2: External Service Integration & Database Setup
As a developer, I want to integrate with external services and set up the database, so that I can retrieve tenant context, store workflow data, and enable the core orchestration functionality.

**Acceptance Criteria:**
1. Service client classes implemented for Collections Monitor and SMS Agent
2. GET `/monitor/tenant/{tenant_id}` integration to retrieve tenant context data
3. GET `/conversations/{phone_number}` integration to retrieve conversation history
4. Supabase database connection established and configured
5. Database schema created for orchestration_workflows, ai_response_queue, and approval_audit_log tables
6. Database migration system set up (alembic or similar)
7. Error handling and timeout configuration for external service calls
8. Service health check validates connectivity to external services and database

**Documentation Required:**
- External service integration documentation
- Service client usage examples
- Database schema documentation and migration guide
- Supabase integration and configuration guide
- Error handling and retry configuration guide
- Service dependency health check documentation

**Test Cases:**
```bash
# Test service health with dependencies
curl http://localhost:8000/health/dependencies

# Test database connection
curl http://localhost:8000/health  # Should include database status

# Test with mock external services running
# (Assuming Collections Monitor on 8001, SMS Agent on 8002)
curl http://localhost:8001/monitor/tenant/12345
curl http://localhost:8002/conversations/%2B1234567890

# Test database connectivity manually
python -c "
import os
from supabase import create_client
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
print('Database connection successful')
"
```

#### Story 1.3: AI Response Generation
As a developer, I want to integrate with OpenAI API to generate contextual responses, so that tenant communications are personalized and relevant to their situation.

**Acceptance Criteria:**
1. OpenAI client integration with API key configuration and validation
2. Environment variable setup for OPENAI_API_KEY with proper validation
3. System prompt generation using tenant context and conversation history
4. AI response generation with confidence score calculation
5. Response formatting to meet SMS character limits and language preferences
6. Error handling for OpenAI API failures with retry logic
7. OpenAI API connectivity validation in health checks

**Documentation Required:**
- OpenAI integration configuration guide
- API key setup and security best practices
- System prompt template documentation
- Confidence score calculation methodology
- Response formatting and language preference handling

**Test Cases:**
```bash
# Test OpenAI connectivity (requires valid OpenAI key)
curl http://localhost:8000/health  # Should include OpenAI status

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

# Test OpenAI key validation
python -c "
import os
import openai
client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
print('OpenAI connection successful')
"
```

#### Story 1.4: Approval Workflow Implementation
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

#### Story 1.5: Workflow Status Tracking
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

#### Story 1.6: Workflow Retry Mechanism
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

### Epic 2 Payment Plan Processing & Escalation

This epic implements the business logic for automatically detecting and processing payment plans from tenant conversations, along with the escalation mechanisms for handling problematic situations that require human intervention.

#### Story 2.1: Payment Plan Detection
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

#### Story 2.2: Escalation Logic Implementation
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

### Epic 3 Monitoring & Reliability

This epic ensures the orchestrator service is production-ready with comprehensive error handling, retry mechanisms, circuit breakers, and observability features to maintain reliable operation in a production environment.

#### Story 3.1: Error Handling & Circuit Breakers
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

#### Story 3.2: Metrics & Monitoring
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


## Next Steps

### UX Expert Prompt
*This PRD does not require UX expertise as it is a backend API service with no user interface components.*

### Architect Prompt
Create the system architecture for the System Orchestrator Service based on this PRD. Focus on the FastAPI service structure, database schema for workflow tracking and approval queues, external service integration patterns, and the circuit breaker/retry logic. The service needs to coordinate between Collections Monitor (port 8001), SMS Agent (port 8002), and Notification Service (port 8003) while implementing the core SMS processing workflow with AI integration and approval mechanisms.