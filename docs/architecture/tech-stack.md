# Tech Stack

**Cloud Infrastructure:**
- **Provider:** Local development (Docker) + Cloud-agnostic deployment
- **Key Services:** Supabase (PostgreSQL), OpenAI API, Docker containerization
- **Deployment Regions:** TBD based on client infrastructure preferences

**Technology Stack Table:**

| Category | Technology | Version | Purpose | Rationale |
|----------|------------|---------|---------|-----------|
| **Language** | Python | 3.11+ | Primary development language | Async support, excellent AI/ML ecosystem, FastAPI compatibility |
| **Framework** | FastAPI | 0.104+ | Web framework | Automatic OpenAPI docs, async support, performance, matches PRD spec |
| **HTTP Client** | httpx | 0.25+ | Async external service calls | Native async support, modern HTTP/2, timeout configuration |
| **Database** | Supabase (PostgreSQL) | 15+ | Workflow tracking, audit logs, timeout monitoring | Managed service, REST API, real-time capabilities per PRD |
| **AI Integration** | OpenAI API | gpt-4-turbo | Response generation | Specified in PRD, proven model, API reliability |
| **Background Tasks** | FastAPI BackgroundTasks | Built-in | Non-blocking operations | Simplified architecture, no external dependencies |
| **Circuit Breaker** | Custom + tenacity | 2.0+ | Fault tolerance | Retry logic, circuit breaking, exponential backoff |
| **Authentication** | JWT | 2.8+ | Internal service auth | Stateless, standard for service-to-service communication |
| **Testing** | pytest | 7.4+ | Testing framework | Python standard, async support, comprehensive assertions |
| **Linting** | black + ruff | 23+ / 0.1+ | Code formatting/linting | Industry standard, fast, consistent formatting |
| **Containerization** | Docker | 24+ | Deployment | Consistent environments, per PRD requirements |
| **Monitoring** | Prometheus + structlog | 1.0+ / 23+ | Metrics/logging | Structured logging with correlation IDs, per NFR4 |
