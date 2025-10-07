"""Application configuration and settings."""

import os
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Service Configuration
    service_name: str = Field(default="orchestrator", env="SERVICE_NAME")
    service_version: str = Field(default="1.0.0", env="SERVICE_VERSION")
    port: int = Field(default=8000, env="PORT")
    host: str = Field(default="::", env="HOST")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # External Service URLs
    sms_agent_url: AnyHttpUrl = Field(..., env="SMS_AGENT_URL")
    collections_monitor_url: AnyHttpUrl = Field(..., env="COLLECTIONS_MONITOR_URL")
    notification_service_url: AnyHttpUrl = Field(..., env="NOTIFICATION_SERVICE_URL")

    # Service URL Aliases for dependency injection
    sms_agent_service_url: str = Field(..., env="SMS_AGENT_URL")
    collections_monitor_service_url: str = Field(..., env="COLLECTIONS_MONITOR_URL")
    notification_service_url: str = Field(..., env="NOTIFICATION_SERVICE_URL")

    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", env="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.7, env="OPENAI_TEMPERATURE")
    openai_max_tokens: int = Field(default=200, env="OPENAI_MAX_TOKENS")

    # Supabase Configuration
    supabase_url: AnyHttpUrl = Field(..., env="SUPABASE_URL")
    supabase_key: str = Field(..., env="SUPABASE_KEY")
    supabase_db_url: Optional[str] = Field(None, env="SUPABASE_DB_URL")

    # Business Rules Configuration
    max_payment_weeks: int = Field(default=12, env="MAX_PAYMENT_WEEKS")
    min_weekly_payment: float = Field(default=25.0, env="MIN_WEEKLY_PAYMENT")
    auto_approval_confidence: float = Field(default=0.85, env="AUTO_APPROVAL_CONFIDENCE")
    manual_approval_min_confidence: float = Field(default=0.60, env="MANUAL_APPROVAL_MIN_CONFIDENCE")
    escalation_hours: int = Field(default=36, env="ESCALATION_HOURS")

    # Circuit Breaker Configuration
    circuit_breaker_failure_threshold: int = Field(default=5, env="CIRCUIT_BREAKER_FAILURE_THRESHOLD")
    circuit_breaker_timeout_seconds: int = Field(default=60, env="CIRCUIT_BREAKER_TIMEOUT_SECONDS")
    retry_max_attempts: int = Field(default=3, env="RETRY_MAX_ATTEMPTS")
    retry_base_delay_seconds: int = Field(default=1, env="RETRY_BASE_DELAY_SECONDS")

    # Security Configuration
    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # Monitoring and Metrics
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    health_check_interval_seconds: int = Field(default=30, env="HEALTH_CHECK_INTERVAL_SECONDS")

    # Manager Notifications
    manager_email: str = Field(default="manager@company.com", env="MANAGER_EMAIL")
    approval_notification_enabled: bool = Field(default=True, env="APPROVAL_NOTIFICATION_ENABLED")
    escalation_notification_enabled: bool = Field(default=True, env="ESCALATION_NOTIFICATION_ENABLED")

    # Development Settings
    development_mode: bool = Field(default=True, env="DEVELOPMENT_MODE")
    mock_external_services: bool = Field(default=False, env="MOCK_EXTERNAL_SERVICES")
    enable_cors: bool = Field(default=True, env="ENABLE_CORS")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @field_validator("auto_approval_confidence", "manual_approval_min_confidence")
    @classmethod
    def validate_confidence_thresholds(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence thresholds must be between 0.0 and 1.0")
        return v

    @field_validator("openai_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("OpenAI temperature must be between 0.0 and 2.0")
        return v

    model_config = {
        "env_file": ".env",
        "case_sensitive": False
    }


# Create global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings