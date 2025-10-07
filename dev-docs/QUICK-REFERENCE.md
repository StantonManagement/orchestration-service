# Quick Reference: Orchestration Endpoints → Dashboard Integration

## Endpoints the Dashboard Calls Directly

| Orchestration Endpoint | Dashboard File | UI Component | Action |
|------------------------|----------------|--------------|---------|
| `POST /orchestrate/approve-response` | `server/routes.ts` → `ai-approvals-tab.tsx` | AI Approvals Tab | Approve/Modify/Escalate AI response |
| `POST /orchestrate/escalate` | `server/routes.ts` → `conversations-tab.tsx`<br>`payment-plans-tab.tsx`<br>`escalations-tab.tsx` | Multiple tabs | Create escalation |
| `GET /orchestrate/workflow/:id/status` | `server/routes.ts` → `modals/ConversationModal.tsx` | Conversation Modal | Show workflow status |
| `POST /orchestrate/retry/:workflowId` | `server/routes.ts` → `escalations-tab.tsx` | Escalations Tab | Retry failed workflow |
| `GET /health/dependencies` | `server/routes.ts` → `pages/settings.tsx` | Settings Page | System health check |
| `GET /orchestrate/metrics` | `server/routes.ts` → `pages/dashboard.tsx` | Dashboard (optional) | Performance metrics |

## Endpoints Dashboard Does NOT Call

| Orchestration Endpoint | Why Not |
|------------------------|---------|
| `POST /orchestrate/sms-received` | Called by SMS Agent, not dashboard |
| `POST /orchestrate/payment-plan-detected` | Internal orchestrator logic only |

---

## File Structure Map

```
CollectionsDashboard/
├── server/
│   └── routes.ts                          ← ADD 6 NEW PROXY ROUTES HERE
│
└── client/src/
    ├── components/
    │   ├── ai-approvals-tab.tsx          ← Wire approve/modify/escalate buttons
    │   ├── conversations-tab.tsx         ← Wire escalate button
    │   ├── payment-plans-tab.tsx         ← Wire escalate on deny
    │   ├── escalations-tab.tsx           ← Wire retry button
    │   └── modals/
    │       └── ConversationModal.tsx     ← Fetch workflow status
    │
    └── pages/
        ├── dashboard.tsx                  ← Display metrics (optional)
        └── settings.tsx                   ← Display system health

```

---

## What to Add to server/routes.ts

```typescript
// Add these 6 new routes at the bottom of registerRoutes()

const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL || "http://localhost:8000";

// 1. Approve AI Response
app.post("/api/orchestrate/approve-response", async (req, res) => {
  const response = await fetch(`${ORCHESTRATOR_URL}/orchestrate/approve-response`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req.body)
  });
  res.json(await response.json());
});

// 2. Create Escalation
app.post("/api/orchestrate/escalate", async (req, res) => {
  const response = await fetch(`${ORCHESTRATOR_URL}/orchestrate/escalate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req.body)
  });
  res.json(await response.json());
});

// 3. Get Workflow Status
app.get("/api/orchestrate/workflow/:conversationId/status", async (req, res) => {
  const response = await fetch(
    `${ORCHESTRATOR_URL}/orchestrate/workflow/${req.params.conversationId}/status`
  );
  res.json(await response.json());
});

// 4. Retry Workflow
app.post("/api/orchestrate/retry/:workflowId", async (req, res) => {
  const response = await fetch(
    `${ORCHESTRATOR_URL}/orchestrate/retry/${req.params.workflowId}`,
    { method: "POST" }
  );
  res.json(await response.json());
});

// 5. System Health
app.get("/api/system/health", async (req, res) => {
  const response = await fetch(`${ORCHESTRATOR_URL}/health/dependencies`);
  res.json(await response.json());
});

// 6. Orchestrator Metrics
app.get("/api/metrics/orchestrator", async (req, res) => {
  const response = await fetch(`${ORCHESTRATOR_URL}/orchestrate/metrics`);
  res.json(await response.json());
});
```

---

## Implementation Priority

### Must Have (MVP)
1. ✅ `POST /api/orchestrate/approve-response` - AI approvals tab
2. ✅ `POST /api/orchestrate/escalate` - Escalation buttons

### Should Have (Week 2)
3. ✅ `GET /api/system/health` - System status visibility
4. ✅ `GET /api/orchestrate/workflow/:id/status` - Conversation details

### Nice to Have (Future)
5. ⭕ `POST /api/orchestrate/retry/:workflowId` - Retry failed items
6. ⭕ `GET /api/metrics/orchestrator` - Performance tracking

---

## Data Flow Quick Reference

### Approve AI Response Flow
```
User clicks "Approve" in ai-approvals-tab.tsx
    ↓
Dashboard calls: POST /api/orchestrate/approve-response
    ↓
server/routes.ts proxies to: Orchestrator
    ↓
Orchestrator → SMS Agent (sends message)
    ↓
Dashboard refreshes → Shows message sent
```

### Create Escalation Flow
```
User clicks "Escalate" in conversations-tab.tsx
    ↓
Dashboard calls: POST /api/orchestrate/escalate
    ↓
server/routes.ts proxies to: Orchestrator
    ↓
Orchestrator → Creates escalation in Supabase
    ↓
Dashboard refreshes → Shows in escalations-tab.tsx
```

### View Workflow Status Flow
```
User opens ConversationModal.tsx
    ↓
Dashboard calls: GET /api/orchestrate/workflow/:id/status
    ↓
server/routes.ts proxies to: Orchestrator
    ↓
Orchestrator → Returns current workflow state
    ↓
Modal displays: Processing step & confidence score
```

---

## Testing Strategy

### 1. Test Orchestrator Standalone
```bash
cd orchestration-service
python -m pytest tests/
```

### 2. Test Dashboard Routes (Mock Orchestrator)
```typescript
// In dashboard tests, mock fetch to orchestrator
global.fetch = jest.fn(() => 
  Promise.resolve({
    json: () => Promise.resolve({ status: "processed" })
  })
);
```

### 3. Test End-to-End
```bash
# Terminal 1: Start orchestrator
cd orchestration-service
uvicorn app.main:app --reload

# Terminal 2: Start dashboard
cd CollectionsDashboard
npm run dev

# Terminal 3: Test flows
curl -X POST http://localhost:5000/api/orchestrate/approve-response \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"123","action":"approve"}'
```

---

## Environment Setup

### Dashboard .env
```env
ORCHESTRATOR_URL=http://localhost:8000
```

### Orchestrator .env
```env
SMS_AGENT_URL=http://localhost:8002
MONITOR_URL=http://localhost:8001
NOTIFICATION_URL=http://localhost:8003
SUPABASE_URL=https://[project].supabase.co
SUPABASE_KEY=[service-key]
OPENAI_API_KEY=sk-...
```

---

## Kurt's Action Items

### Step 1: Add Routes to Dashboard
- [ ] Open `CollectionsDashboard/server/routes.ts`
- [ ] Add the 6 proxy endpoints at the bottom
- [ ] Add `ORCHESTRATOR_URL` environment variable

### Step 2: Wire Up UI Components (Priority Order)
1. [ ] `ai-approvals-tab.tsx` - Connect approve/modify buttons
2. [ ] `conversations-tab.tsx` - Connect escalate button
3. [ ] `escalations-tab.tsx` - Display escalated items
4. [ ] `settings.tsx` - Show system health
5. [ ] `ConversationModal.tsx` - Show workflow status

### Step 3: Test Integration
- [ ] Start orchestrator service
- [ ] Start dashboard
- [ ] Click through approval workflow
- [ ] Verify escalations work
- [ ] Check health status displays

---

## Questions?

If anything is unclear:
1. Check the detailed mapping: `dashboard-integration-map.md`
2. Review orchestrator spec: `kurt-orchestration-spec.md`
3. Look at existing dashboard routes in `server/routes.ts`

The pattern is consistent: Dashboard proxies all orchestrator calls through `server/routes.ts` to avoid CORS issues.
