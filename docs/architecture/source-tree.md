# Source Tree

```plaintext
system-orchestrator-service/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application entry point
│   ├── config.py                   # Environment variables and settings
│   ├── database.py                 # Supabase connection setup
│   ├── models/
│   │   ├── __init__.py
│   │   ├── workflow.py             # WorkflowInstance model
│   │   ├── ai_response.py          # AIResponseQueue model
│   │   ├── payment_plan.py         # PaymentPlanAttempt model
│   │   ├── escalation.py           # EscalationEvent model
│   │   └── workflow_step.py        # WorkflowStep model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── incoming_sms.py         # IncomingSMS request schema
│   │   ├── approval.py             # ResponseApproval schema
│   │   ├── payment_plan.py         # PaymentPlanDetected schema
│   │   ├── escalation.py           # EscalationRequest schema
│   │   └── workflow.py             # WorkflowStatus schema
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py               # Health check endpoints
│   │   ├── orchestration.py        # Main SMS processing endpoints
│   │   ├── approval.py             # Approval workflow endpoints
│   │   ├── payment_plan.py         # Payment plan endpoints
│   │   ├── escalation.py           # Escalation endpoints
│   │   └── metrics.py              # Metrics endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_service.py           # OpenAI integration
│   │   ├── collections_monitor.py  # Collections Monitor client
│   │   ├── sms_agent.py            # SMS Agent client
│   │   ├── notification_service.py # Notification Service client
│   │   ├── approval_service.py     # Approval workflow logic
│   │   ├── payment_plan_service.py # Payment plan processing
│   │   ├── escalation_service.py   # Escalation handling
│   │   └── metrics_service.py      # Metrics collection
│   ├── core/
│   │   ├── __init__.py
│   │   ├── circuit_breaker.py      # Circuit breaker implementation
│   │   ├── retry.py                # Retry logic with tenacity
│   │   ├── exceptions.py           # Custom exception classes
│   │   └── logging.py              # Structured logging setup
│   └── utils/
│       ├── __init__.py
│       ├── confidence_scoring.py   # AI confidence calculation
│       ├── payment_plan_extraction.py # Pattern matching
│       ├── escalation_triggers.py  # Escalation detection
│       └── timeout_monitor.py      # 36-hour timeout checking
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest configuration
│   ├── test_api/
│   │   ├── test_health.py
│   │   ├── test_orchestration.py
│   │   ├── test_approval.py
│   │   ├── test_payment_plan.py
│   │   ├── test_escalation.py
│   │   └── test_metrics.py
│   ├── test_services/
│   │   ├── test_ai_service.py
│   │   ├── test_approval_service.py
│   │   ├── test_payment_plan_service.py
│   │   └── test_escalation_service.py
│   └── test_utils/
│       ├── test_confidence_scoring.py
│       ├── test_payment_plan_extraction.py
│       └── test_escalation_triggers.py
├── migrations/                     # Database migrations (if needed)
├── requirements.txt                # Python dependencies
├── requirements-dev.txt            # Development dependencies
├── .env.example                    # Environment variables template
├── .gitignore
├── README.md
├── Dockerfile
├── docker-compose.yml              # Local development with dependencies
└── pyproject.toml                  # Project configuration
```
