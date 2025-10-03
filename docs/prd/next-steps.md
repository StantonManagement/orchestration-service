# Next Steps

## UX Expert Prompt
*This PRD does not require UX expertise as it is a backend API service with no user interface components.*

## Architect Prompt
Create the system architecture for the System Orchestrator Service based on this PRD. Focus on the FastAPI service structure, database schema for workflow tracking and approval queues, external service integration patterns, and the circuit breaker/retry logic. The service needs to coordinate between Collections Monitor (port 8001), SMS Agent (port 8002), and Notification Service (port 8003) while implementing the core SMS processing workflow with AI integration and approval mechanisms.