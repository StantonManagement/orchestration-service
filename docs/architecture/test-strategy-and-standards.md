# Test Strategy and Standards

**Testing Philosophy:**
- **Approach:** Test-after development with comprehensive coverage
- **Coverage Goals:** 80% code coverage per PRD NFR7
- **Test Pyramid:** Unit tests (70%), Integration tests (20%), E2E tests (10%)

**Test Types and Organization:**

**Unit Tests:**
- **Framework:** pytest 7.4+ with pytest-asyncio
- **File Convention:** `test_*.py` matching source files
- **Location:** `tests/test_*/` mirroring `app/` structure
- **Mocking Library:** pytest-mock for external dependencies
- **Coverage Requirement:** 80% line coverage for critical paths

**AI Agent Requirements:**
- Generate tests for all public methods in services
- Cover edge cases and error conditions
- Follow AAA pattern (Arrange, Act, Assert)
- Mock all external dependencies (OpenAI, external APIs)

**Integration Tests:**
- **Scope:** API endpoints + database operations + external service mocks
- **Location:** `tests/test_integration/`
- **Test Infrastructure:**
  - **Database:** pytest-postgresql with test database
  - **External APIs:** httpx MockTransport for service mocking
  - **OpenAI:** Mock responses for test scenarios

**End-to-End Tests:**
- **Framework:** pytest with Testcontainers for full stack testing
- **Scope:** Complete SMS workflow from API to database
- **Environment:** Docker Compose with all services
- **Test Data:** Factory Boy for realistic test data generation

**Test Data Management:**
- **Strategy:** Factory Boy factories for model creation
- **Fixtures:** pytest fixtures for common test setups
- **Factories:** Separate factory classes for each model
- **Cleanup:** Database transactions rolled back after each test

**Continuous Testing:**
- **CI Integration:** pytest in GitHub Actions with coverage reporting
- **Performance Tests:** pytest-benchmark for response time validation
- **Security Tests:** Bandit for static analysis, pytest for auth testing
