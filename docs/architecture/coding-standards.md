# Coding Standards

**Core Standards:**
- **Languages & Runtimes:** Python 3.11+ with type hints
- **Style & Linting:** black for formatting, ruff for linting
- **Test Organization:** pytest with test files in tests/ directory mirroring app/ structure

**Naming Conventions:**
(Only include if deviating from language defaults)

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `workflow_service.py` |
| Classes | PascalCase | `WorkflowInstance` |
| Functions | snake_case | `process_sms_message()` |
| Variables | snake_case | `tenant_context` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRY_ATTEMPTS` |

**Critical Rules:**
- **No console.log in production code:** Use structured logging with correlation IDs
- **Always validate external inputs:** Use Pydantic models for API request validation
- **Database operations through services:** Never direct database access from API routes
- **External service calls through circuit breaker:** Use ServiceClient wrapper with circuit breaker
- **All workflows must create audit trail:** Log every workflow step for compliance
- **Never hardcode API keys:** Use environment variables through config module
- **Error responses must follow standard format:** Use ApiResponse wrapper for consistency
