# Technical Assumptions

## Repository Structure: Monorepo
The orchestrator service will be developed as a standalone FastAPI service within its own repository, as it's a distinct microservice with clear boundaries and dependencies.

## Service Architecture: Microservices
The orchestrator follows a microservices pattern, coordinating between existing services (Collections Monitor, SMS Agent, Notification Service) via HTTP APIs. This service acts as the central coordinator but maintains separation of concerns from other services.

## Testing Requirements: Full Testing Pyramid
Unit tests for individual components (AI prompt generation, payment plan extraction), integration tests for service-to-service communication, end-to-end tests for complete workflows, and load tests for performance validation. Target 80% coverage as specified in requirements.

## Additional Technical Assumptions and Requests

- **Framework**: FastAPI with Python 3.11+ for async support and automatic OpenAPI documentation
- **Database**: Supabase (PostgreSQL) for workflow tracking, approval queues, and audit logs
- **AI Integration**: OpenAI API with GPT-4-turbo for response generation
- **HTTP Client**: httpx for async HTTP communication with external services
- **Circuit Breaker**: Custom implementation using tenacity for retry logic
- **Authentication**: JWT-based authentication for internal service communication
- **Monitoring**: Prometheus metrics with structured logging
- **Environment Configuration**: All external service URLs and API keys configured via environment variables
- **Containerization**: Docker with multi-stage builds for deployment
- **Error Handling**: Comprehensive error handling with custom exception classes and standardized error responses
- **Timeout Configuration**: 30-second timeouts for external service calls with configurable retry policies
- **Background Tasks**: FastAPI BackgroundTasks for non-blocking operations
- **Port Configuration**: Orchestrator will run on port 8000 to avoid conflicts with existing services (8001-8003)
