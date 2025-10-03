"""
Pytest configuration and fixtures for the System Orchestrator Service.
"""
import pytest
import asyncio
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.config import settings


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """
    Create a test client for the FastAPI application.

    This fixture provides a synchronous TestClient for basic API testing.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async test client for the FastAPI application.

    This fixture provides an AsyncClient for async API testing.
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_sms_data() -> dict:
    """Sample valid SMS data for testing."""
    return {
        "tenant_id": "12345",
        "phone_number": "+1234567890",
        "content": "I can pay $200 per week",
        "conversation_id": "conv-uuid-123",
    }


@pytest.fixture
def sample_invalid_sms_data() -> dict:
    """Sample invalid SMS data for testing validation errors."""
    return {
        "tenant_id": "",  # Empty tenant_id
        "phone_number": "123",  # Too short phone number
        "content": "",  # Empty content
        "conversation_id": "a",  # Invalid conversation_id format
    }


@pytest.fixture
def sample_headers() -> dict:
    """Sample request headers with correlation ID."""
    return {
        "X-Correlation-ID": "test-correlation-123",
        "Content-Type": "application/json",
    }


@pytest.fixture
def api_prefix() -> str:
    """Get the API prefix from settings."""
    return settings.api_prefix
