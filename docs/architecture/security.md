# Security

**Input Validation:**
- **Validation Library:** Pydantic models for API request validation
- **Validation Location:** At API boundary before processing
- **Required Rules:**
  - All external inputs MUST be validated
  - Validation at API boundary before processing
  - Whitelist approach preferred over blacklist

**Authentication & Authorization:**
- **Auth Method:** JWT tokens for internal service communication
- **Session Management:** Stateless JWT with short expiration
- **Required Patterns:**
  - Validate JWT token on protected endpoints
  - Include service identity in token claims
  - Log authentication events for audit

**Secrets Management:**
- **Development:** .env file with .env.example template
- **Production:** Environment variables or secret management service
- **Code Requirements:**
  - NEVER hardcode secrets
  - Access via config module only
  - No secrets in logs or error messages

**API Security:**
- **Rate Limiting:** Built-in rate limiting per service
- **CORS Policy:** Restricted to internal services only
- **Security Headers:** Basic security headers via FastAPI middleware
- **HTTPS Enforcement:** Required for production deployment

**Data Protection:**
- **Encryption at Rest:** Supabase encryption at rest
- **Encryption in Transit:** HTTPS/TLS for all external communication
- **PII Handling:** Minimal PII storage, audit logging per NFR4
- **Logging Restrictions:** No sensitive data in structured logs

**Dependency Security:**
- **Scanning Tool:** Safety for Python dependency scanning
- **Update Policy:** Regular dependency updates in CI/CD
- **Approval Process:** Manual review for new dependencies

**Security Testing:**
- **SAST Tool:** Bandit for static code analysis
- **DAST Tool:** OWASP ZAP for API security testing
- **Penetration Testing:** Manual testing for critical deployments
