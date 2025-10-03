# Data Models

**WorkflowInstance**

**Purpose:** Tracks the complete lifecycle of each SMS processing workflow from receipt to completion

**Key Attributes:**
- id: UUID - Primary key and workflow identifier
- conversation_id: UUID - Links to SMS conversation in SMS Agent
- workflow_type: String - Type of workflow (sms_processing, payment_plan_validation, escalation)
- status: String - Current state (received, processing, awaiting_approval, sent, escalated, failed, completed)
- tenant_id: String - Tenant identifier from Collections Monitor
- phone_number: String - Tenant phone number
- started_at: Timestamp - Workflow initiation time
- completed_at: Timestamp - Workflow completion time (nullable)
- error_message: String - Error details if workflow failed
- metadata: JSON - Additional workflow-specific data

**Relationships:**
- Has many WorkflowSteps (detailed step tracking)
- Has one AIResponse (for SMS processing workflows)
- Has many PaymentPlanAttempts (if payment plan detected)
- Has many EscalationEvents (if escalation occurred)

**AIResponseQueue**

**Purpose:** Manages AI-generated responses requiring approval or automated processing

**Key Attributes:**
- id: UUID - Primary key
- workflow_id: UUID - Reference to parent workflow
- tenant_message: Text - Original SMS from tenant
- ai_response: Text - Generated AI response
- confidence_score: Decimal - AI confidence level (0.0-1.0)
- status: String - Queue status (pending, approved, modified, escalated, auto_sent)
- approval_action: String - Manager action taken (approve, modify, escalate)
- modified_response: Text - Manager-modified response if applicable
- actioned_by: String - Manager ID who handled the response
- actioned_at: Timestamp - When response was processed
- created_at: Timestamp - Queue entry creation time

**Relationships:**
- Belongs to WorkflowInstance
- Has many ApprovalAuditLog entries

**PaymentPlanAttempt**

**Purpose:** Tracks extracted payment plans and validation results

**Key Attributes:**
- id: UUID - Primary key
- workflow_id: UUID - Reference to parent workflow
- extracted_from: String - Source (tenant_message or ai_response)
- weekly_amount: Decimal - Proposed weekly payment
- duration_weeks: Integer - Number of weeks
- start_date: Date - Proposed start date
- validation_result: JSON - Validation issues and auto-approvable status
- status: String - Validation status (valid, invalid, needs_review)
- created_at: Timestamp - When payment plan was detected

**Relationships:**
- Belongs to WorkflowInstance
- Validated against business rules in PaymentPlanValidator service

**EscalationEvent**

**Purpose:** Records escalation incidents and handling

**Key Attributes:**
- id: UUID - Primary key
- workflow_id: UUID - Reference to parent workflow
- escalation_type: String - Type (hostile_language, payment_dispute, unrealistic_proposal, timeout)
- severity: String - Severity level (low, medium, high, critical)
- reason: Text - Detailed escalation reason
- auto_detected: Boolean - Whether automatically detected
- handled_by: String - Manager ID handling escalation
- resolved_at: Timestamp - Escalation resolution time
- created_at: Timestamp - Escalation creation time

**Relationships:**
- Belongs to WorkflowInstance
- Triggers notifications via NotificationService integration

**WorkflowStep**

**Purpose:** Detailed audit trail of each workflow step for debugging and compliance

**Key Attributes:**
- id: UUID - Primary key
- workflow_id: UUID - Reference to parent workflow
- step_name: String - Descriptive step name
- step_type: String - Step category (api_call, ai_processing, database_operation, notification)
- status: String - Step status (started, completed, failed, skipped)
- input_data: JSON - Step input parameters
- output_data: JSON - Step results
- error_details: JSON - Error information if failed
- started_at: Timestamp - Step start time
- completed_at: Timestamp - Step completion time
- duration_ms: Integer - Step execution duration

**Relationships:**
- Belongs to WorkflowInstance
- Provides detailed audit trail per NFR4 requirements
