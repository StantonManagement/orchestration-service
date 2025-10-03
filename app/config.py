"""
Configuration and environment variables for the System Orchestrator Service.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Service Configuration
    app_name: str = "System Orchestrator Service"
    version: str = "1.0.0"
    debug: bool = False

    # API Configuration
    api_prefix: str = "/api/v1"

    # Host and Port
    host: str = "0.0.0.0"
    port: int = 8000

    # Logging
    log_level: str = "INFO"

    # External Service URLs
    monitor_url: str = "http://localhost:8001"
    sms_agent_url: str = "http://localhost:8002"
    notification_url: str = "http://localhost:8003"

    # External Service Timeouts (seconds)
    monitor_timeout: int = 60
    sms_agent_timeout: int = 30
    notification_timeout: int = 30

    # Circuit Breaker Configuration
    monitor_failure_threshold: int = 5
    sms_agent_failure_threshold: int = 3
    notification_failure_threshold: int = 3
    circuit_breaker_timeout: int = 300  # 5 minutes

    # Retry Configuration
    max_retry_attempts: int = 3

    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-4-turbo"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 200
    openai_timeout: int = 30
    openai_rate_limit: int = 3500  # requests per minute

    # Approval Workflow Configuration
    approval_timeout: int = 24  # hours before pending approvals escalate
    auto_approval_threshold: float = 0.85  # confidence threshold for auto-send
    escalation_threshold: float = 0.60  # confidence threshold for escalation

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env file


# Global settings instance
settings = Settings()
