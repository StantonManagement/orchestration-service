# Orchestrator Integration Guide - Exact Endpoints to Call

## Quick Answer: What Endpoints You Need

### Collections Monitor (Your First Project)
```
GET  /monitor/tenant/{tenant_id}     - Get tenant context
GET  /monitor/delinquent             - Get delinquent list
GET  /monitor/stats                  - Get dashboard stats
```

### SMS Foundation Agent (Your Second Project)
```
POST /sms/send                       - Send SMS to tenant
GET  /conversations/{phone_number}   - Get message history
GET  /health                         - Health check
```

### Notification Service (Port 8003)
```
POST /notifications/send              - Send notification to manager
```

**Based on your orchestrator spec, it's port 8003**


## Service Integration Map

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Your Job)               │
│                         Port: 8000                       │
└─────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ Collections  │ │     SMS      │ │ Notification │
    │   Monitor    │ │    Agent     │ │   Service    │
    │   Port 8001  │ │  Port 8002   │ │  Port 8003   │
    └──────────────┘ └──────────────┘ └──────────────┘
            │               │               │
            └───────────────┴───────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │   Supabase   │
                    │   Database   │
                    └──────────────┘
```

---

## 1. Collections Monitor Endpoints (Port 8001)

### GET /monitor/tenant/{tenant_id}

**Purpose:** Get all tenant info for AI context

**Call it like this:**
```python
import httpx

async def get_tenant_context(tenant_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8001/monitor/tenant/{tenant_id}"
        )
        return response.json()
```

**You get back:**
```json
{
  "success": true,
  "data": {
    "tenant_info": {
      "tenant_id": 12345,
      "tenant_name": "John Smith",
      "current_balance": 1500.00,
      "days_late": 15
    },
    "payment_history": {
      "reliability_score": 7,
      "failed_plans": 0
    }
  }
}
```

**When to call:** Every time you receive an SMS

---

### GET /monitor/delinquent

**Purpose:** Get list of all delinquent tenants

**Call it like this:**
```python
async def get_delinquent_tenants():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8001/monitor/delinquent?limit=100"
        )
        return response.json()
```

**When to call:** Not often - mainly for dashboard queries

---

## 2. SMS Agent Endpoints (Port 8002)

### POST /sms/send

**Purpose:** Send AI-generated response to tenant

**Call it like this:**
```python
async def send_sms(to: str, body: str, conv_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/sms/send",
            json={
                "to": to,
                "body": body,
                "conversation_id": conv_id
            }
        )
        return response.json()
```

**When to call:** 
- After AI generates high-confidence response (>85%)
- After manager approves a response

---

### GET /conversations/{phone_number}

**Purpose:** Get message history for AI context

**Call it like this:**
```python
async def get_conversation_history(phone: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8002/conversations/{phone}"
        )
        return response.json()
```

**You get back:**
```json
{
  "success": true,
  "conversation_id": "uuid",
  "messages": [
    {
      "direction": "outbound",
      "content": "Hi John, your rent is late...",
      "timestamp": "2025-01-01T09:00:00Z"
    },
    {
      "direction": "inbound",
      "content": "I can pay $200/week",
      "timestamp": "2025-01-01T10:00:00Z"
    }
  ]
}
```

**When to call:** Before sending to OpenAI - need conversation context

---

## 3. Notification Service Endpoints (Port 8003)

### POST /notifications/send

**Purpose:** Alert managers when approval needed

**Call it like this:**
```python
async def notify_manager(subject: str, body: str, metadata: dict = None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8003/notifications/send",
            json={
                "channel": "email",
                "recipient": "manager@company.com",
                "content": {"subject": subject, "body": body},
                "priority": "normal",
                "metadata": metadata or {}
            }
        )
        return response.json()
```

**When to call:**
- AI confidence 60-84% (needs approval)
- Payment plan detected
- Escalation triggered

**Expected response:**
```json
{
  "tracking_id": "uuid"
}
```

---

## 4. Webhook Validator - NOT USED BY YOU

**This service validates incoming Twilio webhooks.**

You don't call it. It sits in front of SMS Agent.

```
Twilio → Webhook Validator → SMS Agent → Orchestrator
         (checks signature)
```

**Ignore this for your orchestrator.**

---

## Complete Flow with Exact Calls

### Scenario: Tenant sends "I can pay $200/week"

```python
# STEP 1: SMS Agent calls YOU
# You need to expose: POST /orchestrate/sms-received
@router.post("/orchestrate/sms-received")
async def receive_sms(data: IncomingSMS):
    
    # STEP 2: Call Collections Monitor
    tenant = await get_tenant_context(data.tenant_id)
    # Calls: GET http://localhost:8001/monitor/tenant/12345
    
    # STEP 3: Call SMS Agent for history
    conversation = await get_conversation_history(data.phone_number)
    # Calls: GET http://localhost:8002/conversations/+1234567890
    
    # STEP 4: Call OpenAI (not a Kurt service)
    ai_response = await openai_client.chat.completions.create(...)
    
    # STEP 5: Decide what to do
    if ai_response.confidence > 0.85:
        # Send it automatically
        await send_sms(
            to=data.phone_number,
            body=ai_response.content,
            conv_id=data.conversation_id
        )
        # Calls: POST http://localhost:8002/sms/send
        
    elif ai_response.confidence > 0.60:
        # Need manager approval
        await notify_manager(
            subject="Response needs approval",
            body=f"AI wants to say: {ai_response.content}",
            metadata={"conversation_id": data.conversation_id}
        )
        # Calls: POST http://localhost:8003/notifications/send
        
    else:
        # Too uncertain - escalate
        await notify_manager(
            subject="Manual response needed",
            body="AI confidence too low",
            metadata={"conversation_id": data.conversation_id}
        )
        # Calls: POST http://localhost:8003/notifications/send
```

---

## Your Service Client Class

```python
import httpx
import os

class ServiceClients:
    def __init__(self):
        self.monitor_url = os.getenv("MONITOR_URL", "http://localhost:8001")
        self.sms_url = os.getenv("SMS_AGENT_URL", "http://localhost:8002")
        self.notif_url = os.getenv("NOTIFICATION_URL", "http://localhost:8003")
        self.client = httpx.AsyncClient(timeout=30.0)
    
    # ============ Collections Monitor ============
    
    async def get_tenant(self, tenant_id: str):
        response = await self.client.get(
            f"{self.monitor_url}/monitor/tenant/{tenant_id}"
        )
        response.raise_for_status()
        return response.json()
    
    # ============ SMS Agent ============
    
    async def send_sms(self, to: str, body: str, conv_id: str):
        response = await self.client.post(
            f"{self.sms_url}/sms/send",
            json={
                "to": to,
                "body": body,
                "conversation_id": conv_id
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def get_conversation(self, phone: str):
        response = await self.client.get(
            f"{self.sms_url}/conversations/{phone}"
        )
        response.raise_for_status()
        return response.json()
    
    # ============ Notification Service ============
    
    async def notify_manager(self, subject: str, body: str, metadata: dict = None):
        response = await self.client.post(
            f"{self.notif_url}/notifications/send",
            json={
                "channel": "email",
                "recipient": "manager@company.com",
                "content": {"subject": subject, "body": body},
                "metadata": metadata or {}
            }
        )
        response.raise_for_status()
        return response.json()
```

---

## Environment Variables

```env
# Services
MONITOR_URL=http://localhost:8001
SMS_AGENT_URL=http://localhost:8002
NOTIFICATION_URL=http://localhost:8003

# OpenAI
OPENAI_API_KEY=sk-...

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
```

---

## Testing Each Service

```bash
# Test Collections Monitor
curl http://localhost:8001/health
curl http://localhost:8001/monitor/stats

# Test SMS Agent  
curl http://localhost:8002/health

# Test Notification Service
# (No /health endpoint for Notification Service)

```


## NECESSARY INFROMATION IN COLLECTIONS MONITORING (PAYLOAD AND RESPONSE)
GET /monitor/tenant/{tenant_id}

- Path params: tenant_id: string; required; UUID or [A-Za-z0-9-_] (validated).
- Success 200: TenantDetailsResponse
    - success: boolean
    - data: {"tenant": TenantDetail}
    - id, tenant_id, tenant_name, unit_name, property_name
    - amount_owed: string
    - tenant_portion: string
    - days_late: int
    - priority_score: float
    - status: string
    - language_preference: string
    - created_at: ISO string
    - phone_numbers: string[]
    - payment_reliability_score: float
    - failed_payment_plans: int
    - successful_payment_plans: int
- timestamp: ISO string
- Errors: 400 (invalid tenant_id), 404 (not found), 500/503/504 on backend issues.

GET /monitor/delinquent

- Query params:
    - min_days_late: int ≥ 0 (optional)
    - min_amount_owed: float ≥ 0 (optional)
    - property_name: string (optional; case-insensitive)
    - status: string in [pending, active, completed, escalated] (optional; case-insensitive)
    - page: int ≥ 1 (default 1)
    - page_size: int 1–100 (default 20)
- Success 200: DelinquentTenantsListResponse
    - success: boolean
    - data:
    - tenants: DelinquentTenantResponse[]
      - id, tenant_id, tenant_name, unit_name, property_name
      - amount_owed: string
      - tenant_portion: string
      - days_late: int
      - priority_score: float
      - status: string
      - language_preference: string
      - created_at: ISO string
    - pagination:
      - total_items, page, page_size, total_pages: int
      - has_next, has_prev: boolean
- timestamp: ISO string
- Errors: 400 (validation), 500/503/504 on backend issues.

GET /monitor/stats

- Params: none.
- Success 200: StandardResponse with StatsResponse in data
    - success: boolean
    - data:
    - total_delinquent_tenants: int
    - total_amount_owed: string
    - average_amount_owed: string
    - average_days_late: float
    - status_breakdown: {pending, active, completed, escalated: int}
    - property_breakdown: { [property_name]: int }
    - priority_distribution: {high, medium, low: int}
    - days_late_breakdown: {range_0_30, range_31_60, range_60_plus: int}
- timestamp: ISO string
- Errors: 500/503/504 on backend issues.


## NECESSARY INFROMATION IN SMS SERVICE (PAYLOAD AND RESPONSE)
POST /sms/send

- Request body: JSON
    - to: destination phone number (string)
    - body: message text (string, non-empty)
    - conversation_id: optional (string UUID)
- Success response: 202 Accepted
    - id: message ID (string)
    - twilio_sid: optional Twilio SID (string)
    - conversation_id: optional (string UUID)
- Error responses:
    - 400: validation errors (e.g., empty body or invalid destination via service-level validation)
    - 400–499: provider “permanent” errors (status may mirror provider status if 4xx)
    - 502: provider “transient/exhausted” errors
    - Error payload shape:
    - error: { code, message, details: { category, status_code, correlation_id }, request_id }

GET /conversations/{phone_number}

- Path params:
    - phone_number: raw phone string (normalized internally)
- Query params:
    - page: integer, default 1, min 1
    - limit: integer, default 20, min 1, max 100
    - offset: optional integer, min 0 (defaults to (page-1)*limit)
- Success response: 200 OK
    - phone_number_canonical: normalized number (string)
    - phone_number_original: original number if known (string|null)
    - tenant_id: optional (string|null)
    - workflow_type: optional (string|null)
    - last_message_at: ISO timestamp or null (string|null)
    - messages: array of
    - id (int), direction (string), from_number (string|null), to_number (string|null),
      message_content (string|null), content (string|null, same as message_content),
      twilio_sid (string|null), delivery_status (string|null), created_at (ISO string)
- page (int), limit (int), offset (int), total (int|null)
- Error responses:
    - 404: conversation not found or non-normalizable phone

GET /health

- Params: none
- Success response: 200 OK
    - ok: true (boolean)
    - version: app version from settings (string)
    - checks:
    - config: true (boolean)
    - db: "unknown" (string) by default



## NECESSARY INFROMATION IN NOTIFICATION SERVICE (PAYLOAD AND RESPONSE)
POST /notifications/send

- Input (single): JSON body matching NotificationRequest:
    - channel: one of email|sms|webhook|push
    - recipient: string (email/phone/url/device_id depending on channel)
    - template_id: optional string
    - content: optional object (e.g., subject/body)
    - variables: optional object
    - priority: low|normal|high|critical (default normal)
    - metadata: optional object
- Input (bulk): Alternate JSON body where recipients (array of strings) replaces recipient. Other fields mirror NotificationRequest.
- Output:
    - Single: 200 with {"tracking_id": "<uuid>"}.
    - Bulk: 200 with {"tracking_ids": ["<uuid>", ...], "count": <int>}.
- Notes:
    - Validation errors are handled by FastAPI/Pydantic (invalid/missing fields → 422).



## Summary: Your Integration Checklist

- [ ] Call `GET /monitor/tenant/{id}` when SMS arrives
- [ ] Call `GET /conversations/{phone}` for message history  
- [ ] Call `POST /sms/send` to send AI responses
- [ ] Call `POST /notifications/send` to alert managers for approvals
- [ ] Ignore webhook validator - not your problem
- [ ] Test all three services are running locally
- [ ] Set up environment variables
- [ ] Pick a port for your orchestrator (suggest 8000)

---

This is everything you need. Based on your spec document, the notification service is at port 8003 with endpoint `/notifications/send`.
