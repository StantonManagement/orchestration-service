# Requirements

## Functional Requirements

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

## Non-Functional Requirements

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
