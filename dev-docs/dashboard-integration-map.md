# Orchestration Service ↔ Collections Dashboard Integration Map

## Overview
This document maps each orchestration endpoint to its corresponding place in the Collections Dashboard, showing data flow and UI integration points.

---

## 1. POST /orchestrate/sms-received

### Purpose
Receives incoming SMS from SMS Agent and processes it through AI

### Dashboard Integration
**Does NOT directly integrate with dashboard** - This is called BY the SMS Agent, not the dashboard.

**Data Flow:**
```
SMS Agent → /orchestrate/sms-received → AI Processing → Updates Supabase
                                                              ↓
                                                    Dashboard reads from Supabase
```

**Dashboard Components Affected:**
- `conversations-tab.tsx` - Shows new messages in real-time
- `ai-approvals-tab.tsx` - Displays AI responses queued for approval

**Supabase Tables Updated:**
- `sms_conversations` - Creates/updates conversation records
- `sms_messages` - Stores the incoming message
- `ai_response_queue` - Queues AI response if confidence < 0.85

---

## 2. POST /orchestrate/approve-response

### Purpose
Manager approves/modifies/escalates AI-generated responses

### Dashboard Integration
**DIRECTLY CALLED FROM:** `ai-approvals-tab.tsx`

**UI Location:** AI Approvals Tab → Action Buttons
```
ai-approvals-tab.tsx
  └── Action Buttons (Approve/Modify/Escalate)
       └── Calls: POST /orchestrate/approve-response
```

**Request Payload (from Dashboard):**
```typescript
{
  conversation_id: string,
  phone_number: string,
  action: "approve" | "modify" | "escalate",
  approved_text?: string,    // For approve action
  modified_text?: string,     // For modify action
  escalation_reason?: string  // For escalate action
}
```

**Response Expected:**
```typescript
{
  status: "processed"
}
```

**Dashboard Server File to Modify:**
`server/routes.ts` - Add new route:
```typescript
app.post("/api/orchestrate/approve-response", async (req, res) => {
  try {
    const response = await fetch(
      `${ORCHESTRATOR_URL}/orchestrate/approve-response`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req.body)
      }
    );
    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: "Failed to process approval" });
  }
});
```

**Components to Update:**
1. `ai-approvals-tab.tsx` - Add API call for approve/modify/escalate
2. `server/routes.ts` - Add proxy endpoint

---

## 3. POST /orchestrate/payment-plan-detected

### Purpose
Process detected payment plans and validate against business rules

### Dashboard Integration
**Does NOT directly integrate with dashboard** - This is called BY the orchestrator internally.

**Data Flow:**
```
Orchestrator (during SMS processing) → /orchestrate/payment-plan-detected
                                              ↓
                                   Updates payment_plans table
                                              ↓
                              Dashboard reads from payment_plans
```

**Dashboard Components Affected:**
- `payment-plans-tab.tsx` - Shows detected plans awaiting approval

**Supabase Tables Updated:**
- `payment_plans` - Creates new payment plan record with validation status

---

## 4. POST /orchestrate/escalate

### Purpose
Create escalation for conversations requiring manual intervention

### Dashboard Integration
**CALLED FROM:** Multiple dashboard locations

**UI Locations:**
1. `conversations-tab.tsx` → Escalate Button
2. `ai-approvals-tab.tsx` → Escalate Action
3. `payment-plans-tab.tsx` → Deny → Escalate option

**Request Payload:**
```typescript
{
  conversation_id: string,
  escalation_reason: string,
  priority?: "high" | "medium" | "low"
}
```

**Response Expected:**
```typescript
{
  escalation_id: string,
  status: "created"
}
```

**Dashboard Server File to Modify:**
`server/routes.ts` - Add new route:
```typescript
app.post("/api/orchestrate/escalate", async (req, res) => {
  try {
    const response = await fetch(
      `${ORCHESTRATOR_URL}/orchestrate/escalate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req.body)
      }
    );
    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: "Failed to create escalation" });
  }
});
```

**Components to Update:**
1. `conversations-tab.tsx` - Add escalate button handler
2. `payment-plans-tab.tsx` - Add escalate option on deny
3. `escalations-tab.tsx` - Display escalated items
4. `server/routes.ts` - Add proxy endpoint

---

## 5. GET /orchestrate/workflow/{conversation_id}/status

### Purpose
Get current workflow status for a conversation

### Dashboard Integration
**CALLED FROM:** `ConversationModal.tsx`

**UI Location:** When viewing conversation details

**Request:**
```
GET /orchestrate/workflow/{conversation_id}/status
```

**Response Expected:**
```typescript
{
  conversation_id: string,
  workflow_type: string,
  status: "pending" | "processing" | "completed" | "failed",
  current_step: string,
  ai_confidence?: number,
  escalation_triggered: boolean,
  last_updated: string
}
```

**Dashboard Server File to Modify:**
`server/routes.ts` - Add new route:
```typescript
app.get("/api/orchestrate/workflow/:conversationId/status", async (req, res) => {
  try {
    const response = await fetch(
      `${ORCHESTRATOR_URL}/orchestrate/workflow/${req.params.conversationId}/status`
    );
    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: "Failed to fetch workflow status" });
  }
});
```

**Components to Update:**
1. `modals/ConversationModal.tsx` - Display workflow status
2. `server/routes.ts` - Add proxy endpoint

---

## 6. GET /health/dependencies

### Purpose
Check health status of all connected services

### Dashboard Integration
**CALLED FROM:** Dashboard health check / settings page

**UI Location:** Settings page → System Status section

**Request:**
```
GET /health/dependencies
```

**Response Expected:**
```typescript
{
  orchestrator: "healthy" | "degraded" | "down",
  sms_agent: "healthy" | "down",
  collections_monitor: "healthy" | "down",
  supabase: "healthy" | "down",
  openai: "healthy" | "down"
}
```

**Dashboard Server File to Modify:**
`server/routes.ts` - Add new route:
```typescript
app.get("/api/system/health", async (req, res) => {
  try {
    const response = await fetch(
      `${ORCHESTRATOR_URL}/health/dependencies`
    );
    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(503).json({ 
      error: "Health check failed",
      orchestrator: "down" 
    });
  }
});
```

**Components to Update:**
1. `pages/settings.tsx` - Add system health section
2. `server/routes.ts` - Add proxy endpoint

---

## 7. POST /orchestrate/retry/{workflow_id}

### Purpose
Retry a failed workflow

### Dashboard Integration
**CALLED FROM:** `escalations-tab.tsx` → Retry button for failed workflows

**UI Location:** Escalations Tab → Failed workflows → Retry button

**Request:**
```
POST /orchestrate/retry/{workflow_id}
```

**Response Expected:**
```typescript
{
  workflow_id: string,
  status: "retrying" | "failed",
  message: string
}
```

**Dashboard Server File to Modify:**
`server/routes.ts` - Add new route:
```typescript
app.post("/api/orchestrate/retry/:workflowId", async (req, res) => {
  try {
    const response = await fetch(
      `${ORCHESTRATOR_URL}/orchestrate/retry/${req.params.workflowId}`,
      { method: "POST" }
    );
    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: "Failed to retry workflow" });
  }
});
```

**Components to Update:**
1. `escalations-tab.tsx` - Add retry button for failed items
2. `server/routes.ts` - Add proxy endpoint

---

## 8. GET /orchestrate/metrics

### Purpose
Get orchestrator performance metrics

### Dashboard Integration
**CALLED FROM:** Dashboard stats / admin view

**UI Location:** Dashboard page → Performance metrics section (future)

**Request:**
```
GET /orchestrate/metrics
```

**Response Expected:**
```typescript
{
  last_hour: {
    sms_received: number,
    ai_responses: number,
    auto_approval_rate: number,
    avg_response_time: number
  },
  today: {
    total_messages: number,
    escalations: number,
    payment_plans: number
  }
}
```

**Dashboard Server File to Modify:**
`server/routes.ts` - Add new route:
```typescript
app.get("/api/metrics/orchestrator", async (req, res) => {
  try {
    const response = await fetch(
      `${ORCHESTRATOR_URL}/orchestrate/metrics`
    );
    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: "Failed to fetch metrics" });
  }
});
```

**Components to Update:**
1. `pages/dashboard.tsx` - Add metrics display (optional)
2. `server/routes.ts` - Add proxy endpoint

---

## Summary: Files That Need Updates

### Dashboard Files to Modify:

#### 1. `server/routes.ts` (Primary Integration Point)
Add these new routes:
- `POST /api/orchestrate/approve-response`
- `POST /api/orchestrate/escalate`
- `GET /api/orchestrate/workflow/:conversationId/status`
- `GET /api/system/health`
- `POST /api/orchestrate/retry/:workflowId`
- `GET /api/metrics/orchestrator`

#### 2. `client/src/components/ai-approvals-tab.tsx`
Add handlers for:
- Approve button → calls `/api/orchestrate/approve-response`
- Modify button → calls `/api/orchestrate/approve-response`
- Escalate button → calls `/api/orchestrate/escalate`

#### 3. `client/src/components/conversations-tab.tsx`
Add handlers for:
- Escalate button → calls `/api/orchestrate/escalate`
- Show workflow status → calls `/api/orchestrate/workflow/:id/status`

#### 4. `client/src/components/payment-plans-tab.tsx`
Add handlers for:
- Escalate on deny → calls `/api/orchestrate/escalate`

#### 5. `client/src/components/escalations-tab.tsx`
Add handlers for:
- Retry button → calls `/api/orchestrate/retry/:workflowId`

#### 6. `client/src/modals/ConversationModal.tsx`
Add:
- Workflow status display → fetches from `/api/orchestrate/workflow/:id/status`

#### 7. `client/src/pages/settings.tsx`
Add:
- System health status → fetches from `/api/system/health`

---

## Environment Variables to Add

### In Dashboard `.env`:
```env
ORCHESTRATOR_URL=http://localhost:8000
```

### In server/index.ts:
```typescript
const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL || "http://localhost:8000";
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   Collections Dashboard                      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ AI Approvals │  │Conversations │  │  Escalations │     │
│  │     Tab      │  │     Tab      │  │     Tab      │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│         │ Approve/Modify   │ Escalate         │ Retry       │
│         │                  │                  │              │
└─────────┼──────────────────┼──────────────────┼──────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
    ┌─────────────────────────────────────────────────┐
    │           server/routes.ts (Proxy Layer)        │
    └─────────────────┬───────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────────────┐
    │         Orchestration Service                   │
    │                                                  │
    │  • POST /orchestrate/approve-response           │
    │  • POST /orchestrate/escalate                   │
    │  • GET  /orchestrate/workflow/:id/status        │
    │  • POST /orchestrate/retry/:workflowId          │
    │  • GET  /health/dependencies                    │
    │  • GET  /orchestrate/metrics                    │
    └─────────────────┬───────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────────────┐
    │  SMS Agent | Collections Monitor | OpenAI       │
    └─────────────────────────────────────────────────┘
```

---

## Implementation Order

### Phase 1: Read-Only Integration
1. Add `GET /health/dependencies` → Display in settings
2. Add `GET /orchestrate/metrics` → Display in dashboard

### Phase 2: Approval Workflow
3. Add `POST /orchestrate/approve-response` → Wire up AI Approvals tab
4. Test approve/modify/escalate actions

### Phase 3: Escalation Management
5. Add `POST /orchestrate/escalate` → Wire up escalate buttons
6. Add `POST /orchestrate/retry/:workflowId` → Wire up retry button

### Phase 4: Status Tracking
7. Add `GET /orchestrate/workflow/:id/status` → Show in conversation modal

---

## Testing Checklist

- [ ] Can approve AI response from dashboard
- [ ] Can modify AI response text before sending
- [ ] Can escalate conversation from multiple places
- [ ] Can retry failed workflows
- [ ] Can see workflow status in conversation details
- [ ] System health shows all services status
- [ ] Metrics display correctly on dashboard

---

## Notes for Kurt

- All endpoints should be proxied through `server/routes.ts` to avoid CORS issues
- The orchestrator runs on port 8000, dashboard on port 5000
- Use the existing error handling pattern in routes.ts
- Add TypeScript types for all new API responses
- The dashboard doesn't need to know about internal orchestrator logic
- Focus on these 6 integration endpoints, not the internal /orchestrate/sms-received

**Priority Order:**
1. `/orchestrate/approve-response` (most critical - approvals)
2. `/orchestrate/escalate` (second priority - escalations)
3. `/health/dependencies` (operational visibility)
4. Other endpoints (nice to have)
