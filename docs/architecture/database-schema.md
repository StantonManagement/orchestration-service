# Database Schema

```sql
-- Workflow tracking
CREATE TABLE orchestration_workflows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL,
    workflow_type varchar(50) NOT NULL DEFAULT 'sms_processing',
    status varchar(50) NOT NULL DEFAULT 'received',
    tenant_id varchar(50) NOT NULL,
    phone_number varchar(20) NOT NULL,
    started_at timestamp with time zone DEFAULT now(),
    completed_at timestamp with time zone,
    last_message_at timestamp with time zone DEFAULT now(),
    error_message text,
    metadata jsonb DEFAULT '{}',
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

-- AI response queue for approvals
CREATE TABLE ai_response_queue (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id uuid REFERENCES orchestration_workflows(id) ON DELETE CASCADE,
    tenant_message text NOT NULL,
    ai_response text NOT NULL,
    confidence_score decimal(5,4) NOT NULL,
    status varchar(50) DEFAULT 'pending',
    approval_action varchar(50),
    modified_response text,
    actioned_by varchar(100),
    actioned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

-- Approval audit log
CREATE TABLE approval_audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    response_queue_id uuid REFERENCES ai_response_queue(id) ON DELETE CASCADE,
    action varchar(50) NOT NULL,
    original_response text NOT NULL,
    final_response text,
    reason text,
    approved_by varchar(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);

-- Payment plan attempts
CREATE TABLE payment_plan_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id uuid REFERENCES orchestration_workflows(id) ON DELETE CASCADE,
    extracted_from varchar(50) NOT NULL, -- 'tenant_message' or 'ai_response'
    weekly_amount decimal(10,2),
    duration_weeks integer,
    start_date date,
    validation_result jsonb,
    status varchar(50) DEFAULT 'detected',
    created_at timestamp with time zone DEFAULT now()
);

-- Escalation events
CREATE TABLE escalation_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id uuid REFERENCES orchestration_workflows(id) ON DELETE CASCADE,
    escalation_type varchar(50) NOT NULL,
    severity varchar(20) NOT NULL,
    reason text NOT NULL,
    auto_detected boolean DEFAULT false,
    handled_by varchar(100),
    resolved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);

-- Workflow step audit trail
CREATE TABLE workflow_steps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id uuid REFERENCES orchestration_workflows(id) ON DELETE CASCADE,
    step_name varchar(100) NOT NULL,
    step_type varchar(50) NOT NULL,
    status varchar(50) NOT NULL DEFAULT 'started',
    input_data jsonb,
    output_data jsonb,
    error_details jsonb,
    started_at timestamp with time zone DEFAULT now(),
    completed_at timestamp with time zone,
    duration_ms integer
);

-- Indexes for performance
CREATE INDEX idx_workflows_conversation_id ON orchestration_workflows(conversation_id);
CREATE INDEX idx_workflows_status ON orchestration_workflows(status);
CREATE INDEX idx_workflows_tenant_id ON orchestration_workflows(tenant_id);
CREATE INDEX idx_workflows_last_message ON orchestration_workflows(last_message_at);
CREATE INDEX idx_response_queue_status ON ai_response_queue(status);
CREATE INDEX idx_response_queue_workflow_id ON ai_response_queue(workflow_id);
CREATE INDEX idx_steps_workflow_id ON workflow_steps(workflow_id);
CREATE INDEX idx_escalations_workflow_id ON escalation_events(workflow_id);

-- RLS (Row Level Security) policies if needed for multi-tenant
ALTER TABLE orchestration_workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_response_queue ENABLE ROW LEVEL SECURITY;
```
