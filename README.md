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
curl http://localhost:8000/health
```

## API Endpoints

### Health Endpoints
- `GET /health` - Basic service health
- `GET /health/dependencies` - External service dependency health

### Orchestration Endpoints
- `POST /orchestrate/sms-received` - Main SMS processing endpoint
- `POST /orchestrate/approve-response` - Manager approval workflow
- `POST /orchestrate/payment-plan-detected` - Process detected payment plan
- `POST /orchestrate/escalate` - Handle conversation escalation
- `POST /orchestrate/retry/{workflow_id}` - Retry failed workflow
- `GET /orchestrate/workflow/{conversation_id}/status` - Get workflow status
- `GET /orchestrate/metrics` - Service metrics

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

- **Health checks**: `/health` endpoint
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