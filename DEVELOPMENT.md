# Development Guide

## Getting Started

This guide covers setting up the development environment for the System Orchestrator Service.

## Prerequisites

- Python 3.11+ (required for async/await and modern type hints)
- Docker & Docker Compose
- PostgreSQL (for local development)
- OpenAI API key
- Supabase account

## Initial Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd 3.1_orchestrator_service
```

### 2. Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate (Unix/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### 3. Install Dependencies
```bash
# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -e ".[dev]"
```

### 4. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit with your configuration
nano .env
```

Required environment variables:
```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key

# External Service URLs (for development)
SMS_AGENT_URL=http://localhost:8002
COLLECTIONS_MONITOR_URL=http://localhost:8001
NOTIFICATION_SERVICE_URL=http://localhost:8003
```

### 5. Database Setup

#### Option A: Local PostgreSQL
```bash
# Start PostgreSQL with Docker
docker run -d \
  --name postgres-dev \
  -e POSTGRES_DB=orchestrator \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:15-alpine

# Update .env with local database
SUPABASE_DB_URL=postgresql://postgres:password@localhost:5432/orchestrator
```

#### Option B: Supabase (Recommended)
1. Create a new Supabase project
2. Get your project URL and service key
3. Update .env with Supabase credentials
4. Run the initial schema setup script

### 6. Run Database Migrations
```bash
# Initialize Alembic (first time only)
alembic init migrations

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head
```

## Running the Service

### Development Mode
```bash
# Start with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using python module
python -m app.main
```

### Docker Development
```bash
# Start all services
docker-compose up --build

# Start in background
docker-compose up -d --build

# View logs
docker-compose logs -f orchestrator
```

## Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_orchestration.py

# Run with verbose output
pytest -v
```

### Test Structure
```
tests/
├── unit/           # Unit tests for individual components
├── integration/    # Integration tests between components
├── e2e/           # End-to-end workflow tests
└── fixtures/      # Test data and mocks
```

### Writing Tests
```python
# Example unit test
import pytest
from app.services.openai_service import OpenAIService

@pytest.mark.asyncio
async def test_ai_response_generation():
    service = OpenAIService()

    response = await service.generate_response(
        tenant_context={"tenant_name": "John", "amount_owed": 1000},
        conversation_history=[],
        current_message="I can pay $200 per week",
        language="english"
    )

    assert response.content
    assert 0.0 <= response.confidence <= 1.0
    assert response.language == "english"
```

## Code Quality

### Code Formatting
```bash
# Format code with Black
black .

# Check formatting
black --check .

# Format specific file
black app/main.py
```

### Linting
```bash
# Run ruff linter
ruff check .

# Fix auto-fixable issues
ruff check --fix .

# Check specific file
ruff check app/services/openai_service.py
```

### Type Checking
```bash
# Install mypy for type checking
pip install mypy

# Run type checking
mypy app/

# Check specific module
mypy app/services/
```

## Debugging

### Using the Debugger
```python
# Add breakpoints in your code
import pdb; pdb.set_trace()

# Or use ipdb (better)
import ipdb; ipdb.set_trace()
```

### Logging Configuration
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use structured logging
from app.core.logging import get_logger
logger = get_logger(__name__)
logger.info("Debug message", extra={"key": "value"})
```

### Environment-Specific Settings
```python
# Enable development mode
DEVELOPMENT_MODE=true

# Mock external services
MOCK_EXTERNAL_SERVICES=true

# Enable CORS
ENABLE_CORS=true
```

## External Service Setup

### Running All Services Locally
```bash
# Start all external services with Docker Compose
docker-compose up -d postgres redis

# Start collections monitor
cd ../collections_monitor
python -m app.main

# Start SMS agent
cd ../sms_agent
python -m app.main

# Start notification service
cd ../notification_service
python -m app.main

# Start orchestrator
cd ../orchestrator_service
python -m app.main
```

### Service Health Checks
```bash
# Check orchestrator health
curl http://localhost:8000/health

# Check dependency health
curl http://localhost:8000/health/dependencies

# Check individual services
curl http://localhost:8001/health  # Collections Monitor
curl http://localhost:8002/health  # SMS Agent
curl http://localhost:8003/health  # Notification Service
```

## Database Development

### Creating Migrations
```bash
# Generate migration based on model changes
alembic revision --autogenerate -m "Add payment plans table"

# Review generated migration
cat migrations/versions/<migration_file>.py

# Apply migration
alembic upgrade head
```

### Manual Database Operations
```python
# Use database service directly
from app.services.database import db_service

# Create workflow
workflow = await db_service.create_workflow({
    "conversation_id": uuid.uuid4(),
    "workflow_type": "sms_processing",
    "status": "received"
})

# Query workflows
workflows = await db_service.list_workflows(status="completed")
```

## API Development

### Testing Endpoints
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test SMS orchestration
curl -X POST http://localhost:8000/orchestrate/sms-received \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345",
    "phone_number": "+1234567890",
    "content": "I can pay $200 per week",
    "conversation_id": "conv-uuid-123"
  }'
```

### OpenAPI Documentation
- Visit http://localhost:8000/docs for interactive API docs
- Visit http://localhost:8000/redoc for alternative documentation

## Performance Monitoring

### Profiling
```bash
# Install profiler
pip install py-spy

# Profile running application
py-spy top --pid <process-id>

# Generate flame graph
py-spy record --pid <process-id> -o profile.svg
```

### Load Testing
```bash
# Install locust for load testing
pip install locust

# Create load test
# (See tests/load_test.py for example)

# Run load test
locust -f tests/load_test.py --host=http://localhost:8000
```

## Troubleshooting

### Common Development Issues

1. **Import errors**
   ```bash
   # Check Python path
   python -c "import sys; print(sys.path)"

   # Reinstall in development mode
   pip install -e .
   ```

2. **Database connection issues**
   ```bash
   # Test database connection
   python -c "
   from app.services.database import db_service
   import asyncio
   print(asyncio.run(db_service.health_check()))
   "
   ```

3. **External service connectivity**
   ```bash
   # Test service connectivity
   curl http://localhost:8001/health  # Collections Monitor
   curl http://localhost:8002/health  # SMS Agent
   ```

### Debug Mode Tips
- Set `DEBUG=true` in .env
- Enable detailed logging: `LOG_LEVEL=DEBUG`
- Use VS Code Python debugger
- Add print statements for quick debugging

## Contributing Workflow

1. Create feature branch from main
2. Make changes with tests
3. Run code quality checks:
   ```bash
   black .
   ruff check --fix .
   pytest --cov=app
   ```
4. Update documentation
5. Create pull request
6. Ensure CI passes

## Hot Reloading

The service supports hot reloading during development:
```bash
# Auto-reload on file changes
uvicorn app.main:app --reload --reload-dir app/

# Or using python
python -m app.main --reload
```

## Environment Variables Reference

See `.env.example` for all available configuration options. Key development options:

- `DEBUG=true` - Enable debug mode
- `DEVELOPMENT_MODE=true` - Enable development features
- `MOCK_EXTERNAL_SERVICES=true` - Use mock responses for external services
- `ENABLE_CORS=true` - Enable CORS for frontend development
- `LOG_LEVEL=DEBUG` - Enable detailed logging