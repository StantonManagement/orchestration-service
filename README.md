# System Orchestrator Service

The central orchestration service that coordinates all collections system components. This service is the "brain" that receives incoming SMS, generates contextual AI responses, manages approval workflows, and coordinates outbound communications.

## Features

- 🤖 **AI-Powered Response Generation** - Uses OpenAI to generate contextual responses
- 🔄 **Approval Workflow** - Manager approval for medium-confidence responses
- 📊 **Workflow Tracking** - Complete audit trail of all processing steps
- 🔧 **Circuit Breakers** - Resilient handling of external service failures
- 📈 **Metrics & Monitoring** - Comprehensive service health and performance metrics
- 🔄 **Retry Mechanism** - Manual retry for failed workflows
- 💳 **Payment Plan Detection** - Automatically extract and validate payment plans
- 🚨 **Escalation Handling** - Smart escalation based on content and timing

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                ORCHESTRATOR SERVICE                    │
│                        Port: 8000                       │
└─────────────────┬───────────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Collections│ │  SMS     │ │Notification│
│ Monitor   │ │ Agent    │ │ Service   │
│  Port 8001│ │ Port 8002│ │  Port 8003│
└──────────┘ └──────────┘ └──────────┘
    │             │             │
    └─────────────┼─────────────┘
                  │
                  ▼
          ┌──────────────┐
          │   Supabase   │
          │   Database   │
          └──────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- OpenAI API key
- Supabase project

### Environment Setup

1. **Clone and setup:**
```bash
git clone <repository-url>
cd 3.1_orchestrator_service
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your actual configuration
```

5. **Run database migrations:**
```bash
alembic upgrade head
```

### Running the Service

#### Option 1: Local Development
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Option 2: Docker Compose
```bash
docker-compose up --build
```

### Health Check

```bash
curl http://localhost:8000/health/dependencies
```

## API Endpoints

### 🏥 Health Endpoints

#### 1. Basic Service Health
```bash
curl -X GET "http://localhost:8000/health" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)"
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "timestamp": "2025-01-15T10:30:00Z",
  "service_name": "orchestrator-service"
}
```

#### 2. Detailed Service Health
```bash
curl -X GET "http://localhost:8000/health/detailed" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)"
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "timestamp": "2025-01-15T10:30:00Z",
  "service_name": "orchestrator-service",
  "checks": {
    "database": "healthy",
    "external_services": "healthy",
    "memory": "healthy"
  }
}
```

#### 3. Check Dependencies Health
```bash
curl -X GET "http://localhost:8000/health/dependencies" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)"
```

**Response:**
```json
{
  "collections_monitor": true,
  "sms_agent": true,
  "notification_service": false,
  "supabase": true,
  "openai": true,
  "overall_status": "degraded",
  "degradation_mode": "full"
}
```

### 🎯 Core Orchestration Endpoints

#### 1. SMS Processing (Main Workflow Entry Point)
```bash
curl -X POST "http://localhost:8000/orchestrate/sms-received" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)" \
  -d '{
    "tenant_id": "tenant_12345",
    "phone_number": "+1234567890",
    "content": "I can pay $50 per week for 3 months",
    "conversation_id": "conv_abc123",
    "timestamp": "2025-01-15T10:30:00Z",
    "direction": "inbound"
  }'
```

**Response:**
```json
{
  "status": "processed",
  "conversation_id": "conv_abc123",
  "workflow_id": "workflow-12345678-1234-1234-1234-123456789012",
  "timestamp": "2025-01-15T10:30:05Z"
}
```

#### 2. Manager Approval Workflow
```bash
curl -X POST "http://localhost:8000/orchestrate/approve-response" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)" \
  -d '{
    "response_queue_id": "resp_789def",
    "action": "approve",
    "approved_text": "Thank you for your payment arrangement. We have set up a payment plan of $50 per week for 12 weeks starting next Friday.",
    "manager_id": "manager_456",
    "notes": "Customer agreed to reasonable payment terms"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Response approved and sent successfully",
  "action": "approve",
  "processed_at": "2025-01-15T10:35:00Z"
}
```

#### 3. Payment Plan Detection
```bash
curl -X POST "http://localhost:8000/orchestrate/payment-plan-detected" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)" \
  -d '{
    "conversation_id": "conv_abc123",
    "tenant_id": "tenant_12345",
    "message_content": "I can pay $50 per week for 3 months",
    "ai_response": "That sounds like a reasonable payment arrangement. I have noted your payment plan proposal.",
    "weekly_amount": 50.0,
    "weeks": 12,
    "start_date": "2025-01-22T00:00:00Z",
    "confidence": 0.92
  }'
```

**Response:**
```json
{
  "success": true,
  "payment_plan_id": "pp_456ghi",
  "status": "validated",
  "validation_details": {
    "is_valid": true,
    "issues": [],
    "auto_approvable": true,
    "total_amount": 600.0,
    "covers_debt": true
  },
  "processed_at": "2025-01-15T10:32:00Z"
}
```

#### 4. Conversation Escalation
```bash
curl -X POST "http://localhost:8000/orchestrate/escalate" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)" \
  -d '{
    "conversation_id": "conv_abc123",
    "workflow_id": "workflow-12345678-1234-1234-1234-123456789012",
    "escalation_type": "manual",
    "reason": "Customer requested supervisor assistance regarding payment terms",
    "severity": "medium",
    "auto_detected": false,
    "escalated_by": "manager_456",
    "metadata": {
      "original_request": "Modification to payment plan terms",
      "customer_phone": "+1234567890"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "escalation_id": "esc_789jkl",
  "conversation_id": "conv_abc123",
  "status": "escalated_processed",
  "escalated_at": "2025-01-15T10:40:00Z",
  "assigned_to": "supervisor_team"
}
```

#### 5. Workflow Status Check
```bash
curl -X GET "http://localhost:8000/orchestrate/workflow/conv_abc123/status" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)"
```

**Response:**
```json
{
  "conversation_id": "conv_abc123",
  "workflow_id": "workflow-12345678-1234-1234-1234-123456789012",
  "status": "completed",
  "current_step": "response_sent",
  "steps_completed": [
    "sms_received",
    "ai_response_generated",
    "manager_approval",
    "response_sent"
  ],
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:35:00Z",
  "metadata": {
    "processing_time_seconds": 300,
    "ai_confidence": 0.87,
    "auto_approved": false
  }
}
```

#### 6. Failed Workflow Retry
```bash
curl -X POST "http://localhost:8000/orchestrate/retry/workflow-12345678-1234-1234-1234-123456789012" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)" \
  -d '{
    "reason": "External service temporarily unavailable, now recovered",
    "force_retry": false,
    "recovery_strategy": "wait_and_retry",
    "notes": "Customer service confirmed the issue has been resolved"
  }'
```

**Response:**
```json
{
  "success": true,
  "workflow_id": "workflow-12345678-1234-1234-1234-123456789012",
  "status": "retry_initiated",
  "retry_attempted_at": "2025-01-15T10:45:00Z",
  "message": "Workflow retry initiated successfully. Monitoring progress...",
  "retry_id": "retry_456mno"
}
```

#### 7. Service Metrics
```bash
curl -X GET "http://localhost:8000/orchestrate/metrics?hours=24&format=json" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)"
```

**Response:**
```json
{
  "timeframe": {
    "timeframe_hours": 24,
    "sms_metrics": {
      "received": 145,
      "processed": 142,
      "failed": 3,
      "rate_per_hour": 6.0
    },
    "ai_metrics": {
      "responses": 142,
      "avg_response_time_ms": 1250,
      "avg_confidence": 0.84,
      "response_rate": 0.98
    },
    "approval_metrics": {
      "total": 85,
      "approved": 78,
      "rejected": 7,
      "auto_approval_rate": 0.42,
      "avg_approval_time_ms": 1800
    },
    "escalation_metrics": {
      "total": 12,
      "by_type": {
        "low_confidence": 8,
        "manual": 3,
        "timeout": 1
      },
      "by_severity": {
        "medium": 9,
        "high": 3
      },
      "rate_per_hour": 0.5,
      "avg_resolution_time_ms": 45000
    },
    "payment_plan_metrics": {
      "detected": 28,
      "validated": 25,
      "auto_approved": 20,
      "detection_rate": 0.20,
      "validation_rate": 0.89
    }
  },
  "dashboard": {
    "last_hour": {
      "sms_received": 6,
      "ai_responses": 6,
      "approvals_pending": 2,
      "escalations": 0
    },
    "today": {
      "total_conversations": 145,
      "completed_workflows": 142,
      "payment_plans": 28,
      "escalations": 12
    },
    "system_health": {
      "collections_monitor": {
        "healthy": 140,
        "unhealthy": 5,
        "availability": 0.97,
        "response_time_ms": 150.0,
        "last_check": "2025-01-15T10:45:00Z"
      },
      "sms_agent": {
        "healthy": 143,
        "unhealthy": 2,
        "availability": 0.99,
        "response_time_ms": 85.0,
        "last_check": "2025-01-15T10:45:00Z"
      }
    }
  },
  "generated_at": "2025-01-15T10:45:00Z",
  "filters_applied": {
    "hours": 24,
    "tenant_id": null
  }
}
```

### 💳 Payment Plan Management Endpoints

#### 8. Get Payment Plans by Conversation ID
```bash
curl -X GET "http://localhost:8000/orchestrate/payment-plans/conv_abc123" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)"
```

**Response:**
```json
{
  "conversation_id": "conv_abc123",
  "payment_plans": [
    {
      "payment_plan_id": "pp_456ghi",
      "weekly_amount": 50.0,
      "weeks": 12,
      "start_date": "2025-01-22T00:00:00Z",
      "status": "active",
      "total_amount": 600.0,
      "created_at": "2025-01-15T10:32:00Z",
      "validation_details": {
        "is_valid": true,
        "auto_approvable": true,
        "covers_debt": true
      }
    }
  ],
  "total_plans": 1,
  "active_plans": 1
}
```

#### 9. Get Specific Payment Plan Details
```bash
curl -X GET "http://localhost:8000/orchestrate/payment-plans/pp_456ghi" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)"
```

**Response:**
```json
{
  "payment_plan_id": "pp_456ghi",
  "conversation_id": "conv_abc123",
  "tenant_id": "tenant_12345",
  "weekly_amount": 50.0,
  "weeks": 12,
  "start_date": "2025-01-22T00:00:00Z",
  "end_date": "2025-04-16T00:00:00Z",
  "status": "active",
  "total_amount": 600.0,
  "amount_paid": 150.0,
  "amount_remaining": 450.0,
  "payment_history": [
    {
      "payment_date": "2025-01-22T00:00:00Z",
      "amount": 50.0,
      "status": "paid",
      "payment_method": "auto_draft"
    },
    {
      "payment_date": "2025-01-29T00:00:00Z",
      "amount": 50.0,
      "status": "paid",
      "payment_method": "auto_draft"
    },
    {
      "payment_date": "2025-02-05T00:00:00Z",
      "amount": 50.0,
      "status": "paid",
      "payment_method": "auto_draft"
    }
  ],
  "created_at": "2025-01-15T10:32:00Z",
  "updated_at": "2025-02-05T10:30:00Z",
  "validation_details": {
    "is_valid": true,
    "issues": [],
    "auto_approvable": true,
    "total_amount": 600.0,
    "covers_debt": true
  }
}
```

### 🚨 Escalation Management Endpoints

#### 10. Manual Escalation Trigger
```bash
curl -X POST "http://localhost:8000/escalations/trigger" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-$(uuidgen)" \
  -d '{
    "conversation_id": "conv_abc123",
    "workflow_id": "workflow-12345678-1234-1234-1234-123456789012",
    "escalation_type": "manual",
    "reason": "Customer requested supervisor regarding account dispute",
    "severity": "high",
    "auto_detected": false,
    "metadata": {
      "triggered_by": "customer_service_manager",
      "department": "collections",
      "urgent": true
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "escalation_id": "esc_789jkl",
  "conversation_id": "conv_abc123",
  "workflow_id": "workflow-12345678-1234-1234-1234-123456789012",
  "status": "escalation_created",
  "escalation_type": "manual",
  "severity": "high",
  "escalated_at": "2025-01-15T11:00:00Z",
  "assigned_to": "supervisor_team",
  "priority": "high",
  "expected_resolution_time": "2025-01-15T12:00:00Z"
}
```

## Configuration

### Environment Variables

Key configuration options:

```bash
# External Services
SMS_AGENT_URL=http://localhost:8002
COLLECTIONS_MONITOR_URL=http://localhost:8001
NOTIFICATION_SERVICE_URL=http://localhost:8003

# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4-turbo-preview

# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-key-here

# Business Rules
AUTO_APPROVAL_CONFIDENCE=0.85
MANUAL_APPROVAL_MIN_CONFIDENCE=0.60
MAX_PAYMENT_WEEKS=12
MIN_WEEKLY_PAYMENT=25
```

### Business Rules Configuration

- **Auto-approval**: Responses with confidence ≥ 85% are sent automatically
- **Manual approval**: Responses with confidence 60-84% require manager approval
- **Escalation**: Responses with confidence < 60% are escalated
- **Payment plans**: Maximum 12 weeks, minimum $25/week
- **Timeout escalation**: 36 hours with no tenant response

## Development

### Project Structure

```
app/
├── core/           # Configuration and logging
├── models/         # Pydantic schemas and database models
├── services/       # Business logic and external service clients
└── api/            # API route handlers
migrations/        # Database migration files
tests/             # Test files
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_orchestration.py
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .

# Type checking
mypy app/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Deployment

### Docker Production

```bash
# Build production image
docker build -t orchestrator:latest .

# Run with production configuration
docker run -d \
  --name orchestrator \
  -p 8000:8000 \
  --env-file .env.prod \
  orchestrator:latest
```

### Monitoring

- **Health checks**: `/health/dependencies` endpoint
- **Metrics**: `/orchestrate/metrics` endpoint
- **Logs**: Structured JSON logging with correlation IDs
- **Prometheus**: Available on port 9090 with Docker Compose

## External Service Dependencies

The orchestrator integrates with:

1. **Collections Monitor** (Port 8001)
   - `GET /monitor/tenant/{tenant_id}` - Get tenant context
   - `GET /monitor/delinquent` - Get delinquent tenant list

2. **SMS Agent** (Port 8002)
   - `POST /sms/send` - Send SMS message
   - `GET /conversations/{phone_number}` - Get conversation history

3. **Notification Service** (Port 8003)
   - `POST /notifications/send` - Send notifications to managers

4. **OpenAI API**
   - AI response generation with confidence scoring

5. **Supabase**
   - Workflow tracking and audit logging

## Security Considerations

- All API endpoints should be protected with authentication in production
- Environment variables contain sensitive data - never commit to version control
- Use HTTPS in production
- Implement rate limiting for SMS endpoints
- Regular security updates for all dependencies

## Troubleshooting

### Common Issues

1. **Database connection failed**
   - Check Supabase URL and key in .env
   - Verify network connectivity to Supabase

2. **OpenAI API errors**
   - Verify API key is valid and has credits
   - Check model availability in your region

3. **External service timeouts**
   - Check service health endpoints
   - Verify network connectivity between services

4. **Circuit breaker activated**
   - Check external service status
   - Wait for timeout period or restart service

### Logs

```bash
# View logs in Docker
docker-compose logs -f orchestrator

# View specific log level
docker-compose logs orchestrator | grep ERROR
```

## Contributing

1. Follow the existing code style
2. Add tests for new functionality
3. Update documentation
4. Ensure all tests pass before submitting

## Support

For issues and questions:
- Check the troubleshooting section
- Review API documentation at `/docs`
- Check service health endpoints
- Review logs for detailed error information