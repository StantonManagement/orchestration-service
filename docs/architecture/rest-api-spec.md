# REST API Spec

```yaml
openapi: 3.0.0
info:
  title: System Orchestrator Service API
  version: 1.0.0
  description: Central orchestration service for collections system workflow management
servers:
  - url: http://localhost:8000
    description: Development server
  - url: https://orchestrator.stanton.com
    description: Production server

paths:
  /health:
    get:
      summary: Basic health check
      tags: [Health]
      responses:
        '200':
          description: Service is healthy
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: "healthy"
                  version:
                    type: string
                    example: "1.0.0"

  /health/dependencies:
    get:
      summary: Check external service dependencies
      tags: [Health]
      responses:
        '200':
          description: Dependency health status
          content:
            application/json:
              schema:
                type: object
                properties:
                  collections_monitor:
                    type: boolean
                  sms_agent:
                    type: boolean
                  notification_service:
                    type: boolean
                  supabase:
                    type: boolean
                  openai:
                    type: boolean

  /orchestrate/sms-received:
    post:
      summary: Process incoming SMS message
      tags: [Orchestration]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [tenant_id, phone_number, content, conversation_id]
              properties:
                tenant_id:
                  type: string
                  example: "12345"
                phone_number:
                  type: string
                  example: "+1234567890"
                content:
                  type: string
                  example: "I can pay $200 per week"
                conversation_id:
                  type: string
                  format: uuid
                  example: "conv-uuid-123"
      responses:
        '200':
          description: SMS processed successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: "processed"
                  conversation_id:
                    type: string
                    example: "conv-uuid-123"
                  workflow_id:
                    type: string
                    format: uuid
        '400':
          description: Invalid SMS data
        '500':
          description: Processing error

  /orchestrate/approve-response:
    post:
      summary: Approve, modify, or escalate AI response
      tags: [Approval]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [response_queue_id, action, manager_id]
              properties:
                response_queue_id:
                  type: string
                  format: uuid
                action:
                  type: string
                  enum: [approve, modify, escalate]
                approved_text:
                  type: string
                  example: "Thank you for your payment arrangement."
                modified_text:
                  type: string
                  example: "Thank you. We can arrange $200/week for 8 weeks starting next Friday."
                escalation_reason:
                  type: string
                  example: "Tenant disputes amount owed"
                manager_id:
                  type: string
                  example: "manager-001"
      responses:
        '200':
          description: Response processed
        '404':
          description: Response queue item not found
        '400':
          description: Invalid approval data

  /orchestrate/payment-plan-detected:
    post:
      summary: Process detected payment plan
      tags: [Payment Plans]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [conversation_id, tenant_id, message_content]
              properties:
                conversation_id:
                  type: string
                  format: uuid
                tenant_id:
                  type: string
                message_content:
                  type: string
                  example: "I can pay $200 per week for 8 weeks"
                ai_response:
                  type: string
                  example: "PAYMENT_PLAN: weekly=200, weeks=8, start=2025-01-08"
      responses:
        '200':
          description: Payment plan processed
        '400':
          description: Invalid payment plan data

  /orchestrate/escalate:
    post:
      summary: Create manual or automatic escalation
      tags: [Escalation]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [conversation_id, escalation_type, severity]
              properties:
                conversation_id:
                  type: string
                  format: uuid
                escalation_type:
                  type: string
                  enum: [hostile_language, payment_dispute, unrealistic_proposal, no_response]
                reason:
                  type: string
                  example: "Tenant mentioned lawyer and legal action"
                severity:
                  type: string
                  enum: [low, medium, high, critical]
                auto_detected:
                  type: boolean
                  default: false
      responses:
        '200':
          description: Escalation created
        '400':
          description: Invalid escalation data

  /orchestrate/workflow/{conversation_id}/status:
    get:
      summary: Get workflow status for conversation
      tags: [Monitoring]
      parameters:
        - name: conversation_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Workflow status
          content:
            application/json:
              schema:
                type: object
                properties:
                  conversation_id:
                    type: string
                    format: uuid
                  workflow_id:
                    type: string
                    format: uuid
                  status:
                    type: string
                    enum: [received, processing, awaiting_approval, sent, escalated, failed, completed]
                  started_at:
                    type: string
                    format: date-time
                  last_updated:
                    type: string
                    format: date-time
        '404':
          description: Workflow not found

  /orchestrate/retry/{workflow_id}:
    post:
      summary: Manually retry failed workflow
      tags: [Operations]
      parameters:
        - name: workflow_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                reason:
                  type: string
                  example: "Temporary external service failure resolved"
      responses:
        '200':
          description: Workflow retry initiated
        '404':
          description: Workflow not found
        '400':
          description: Workflow cannot be retried

  /orchestrate/metrics:
    get:
      summary: Get system metrics
      tags: [Monitoring]
      responses:
        '200':
          description: System metrics
          content:
            application/json:
              schema:
                type: object
                properties:
                  last_hour:
                    type: object
                    properties:
                      sms_received:
                        type: integer
                      ai_responses:
                        type: integer
                      auto_approval_rate:
                        type: number
                      avg_response_time_ms:
                        type: integer
                  today:
                    type: object
                    properties:
                      total_messages:
                        type: integer
                      escalations:
                        type: integer
                      payment_plans:
                        type: integer
```
