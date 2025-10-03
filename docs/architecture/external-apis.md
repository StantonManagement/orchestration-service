# External APIs

**Collections Monitor API** (Port 8001)

- **Purpose:** Retrieve tenant context information for AI personalization and workflow processing
- **Documentation:** Available in project specification and necessary-services.md
- **Base URL:** `http://localhost:8001` (configurable via `MONITOR_URL`)
- **Authentication:** Internal service communication (JWT tokens for production)

**Key Endpoints Used:**
- `GET /monitor/tenant/{tenant_id}` - Fetch tenant context, payment history, language preference
- `GET /monitor/delinquent` - (Optional) Dashboard metrics and delinquent tenant lists

**Integration Notes:** Critical dependency - SMS processing cannot proceed without tenant context. Circuit breaker with 5 failure threshold and 60-second timeout. Retry with exponential backoff up to 3 attempts.

**SMS Agent API** (Port 8002)

- **Purpose:** Send AI-generated responses to tenants and retrieve conversation history for context
- **Documentation:** Available in project specification and necessary-services.md
- **Base URL:** `http://localhost:8002` (configurable via `SMS_AGENT_URL`)
- **Authentication:** Internal service communication (JWT tokens for production)

**Key Endpoints Used:**
- `POST /sms/send` - Send approved AI responses to tenants (expects 202 Accepted)
- `GET /conversations/{phone_number}` - Retrieve message history for AI context
- `GET /health` - Service health verification

**Integration Notes:** Send endpoint is business-critical - requires 202 response with message ID. Conversation history essential for AI context generation. Circuit breaker with 3 failure threshold due to high volume.

**Notification Service API** (Port 8003)

- **Purpose:** Alert managers when responses require approval or escalations occur
- **Documentation:** Available in project specification and necessary-services.md
- **Base URL:** `http://localhost:8003` (configurable via `NOTIFICATION_URL`)
- **Authentication:** Internal service communication (JWT tokens for production)

**Key Endpoints Used:**
- `POST /notifications/send` - Send email notifications to managers for approvals/escalations

**Integration Notes:** Important for workflow continuity but not blocking - notifications can be retried later. Uses standard notification payload with tracking ID for audit trail.

**OpenAI API**

- **Purpose:** Generate contextual responses for tenant communications using GPT-4-turbo
- **Documentation:** https://platform.openai.com/docs/api-reference
- **Base URL:** `https://api.openai.com/v1`
- **Authentication:** API key (configured via `OPENAI_API_KEY`)

**Key Endpoints Used:**
- `POST /chat/completions` - Generate AI responses with gpt-4-turbo model

**Integration Notes:** Critical for core functionality. Rate limits: 3500 requests/minute for gpt-4-turbo. Temperature 0.7 for consistency, max_tokens 200 for SMS limits. Confidence scoring based on response analysis and tenant context match.

**Supabase API**

- **Purpose:** Persistent storage for workflow tracking, approval queues, audit logs, and timeout-based escalation monitoring
- **Documentation:** https://supabase.com/docs/reference
- **Base URL:** `https://[project].supabase.co` (configured via `SUPABASE_URL`)
- **Authentication:** Service key (configured via `SUPABASE_KEY`)

**Key Endpoints Used:**
- `POST /rest/v1/workflow_instances` - Create workflow records
- `GET /rest/v1/workflow_instances?status=awaiting_approval&last_message_at=lt.{timestamp}` - Find timeout escalations
- `POST /rest/v1/ai_response_queue` - Queue responses for approval
- `PATCH /rest/v1/ai_response_queue` - Update approval status
- `POST /rest/v1/escalation_events` - Record escalations

**Integration Notes:** Enhanced to handle timeout escalations via periodic queries. FastAPI BackgroundTasks for non-blocking operations instead of separate task queue.
