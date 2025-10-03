"""
SMS Agent service client for conversation history retrieval.
"""
from typing import Dict, Any, List
import re
import structlog
from datetime import datetime
from app.config import settings
from app.core.circuit_breaker import ServiceClient, CircuitBreakerConfig
from app.core.retry import get_external_service_retry_config, create_async_retry_decorator
from app.core.exceptions import ServiceUnavailableError, ExternalServiceError

logger = structlog.get_logger(__name__)


class SMSAgentClient:
    """Client for SMS Agent service integration."""

    def __init__(self):
        self.service_name = "SMS Agent"

        # Create circuit breaker configuration
        circuit_config = CircuitBreakerConfig(
            failure_threshold=getattr(settings, 'sms_agent_failure_threshold', 5),
            timeout=getattr(settings, 'circuit_breaker_timeout', 60),
            success_threshold=3,
            half_open_max_calls=5,
        )

        # Create service client with circuit breaker
        self.service_client = ServiceClient(
            service_name=self.service_name,
            base_url=settings.sms_agent_url,
            timeout_seconds=getattr(settings, 'sms_agent_timeout', 30),
            circuit_breaker_config=circuit_config,
        )

        # Create retry decorator
        retry_config = get_external_service_retry_config()
        self.retry_decorator = create_async_retry_decorator(
            config=retry_config,
            service_name=self.service_name,
        )

    def _validate_phone_number(self, phone_number: str) -> None:
        """
        Validate phone_number parameter.

        Args:
            phone_number: Phone number to validate

        Raises:
            ValueError: If phone_number is invalid
        """
        if not isinstance(phone_number, str):
            raise ValueError("Phone number must be a string")

        if not phone_number:
            raise ValueError("Phone number cannot be empty")

        # Basic phone number validation - allows E.164 format and common formats
        # Accepts formats like: +1234567890, 123-456-7890, (123) 456-7890
        if not re.match(
            r"^\+?[1-9]\d{1,14}$|^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$", phone_number
        ):
            raise ValueError("Phone number format is invalid")

        logger.info("Phone number validated", phone_number=phone_number)

    async def send_sms(self, phone_number: str, message: str) -> str:
        """
        Send SMS message to tenant via SMS Agent service.

        Args:
            phone_number: Phone number to send SMS to
            message: SMS message content to send

        Returns:
            Message ID from SMS Agent

        Raises:
            ServiceUnavailableError: If service is unavailable or circuit is open
            httpx.HTTPError: For HTTP-related errors
            ValueError: If phone_number or message is invalid
        """
        self._validate_phone_number(phone_number)

        if not isinstance(message, str):
            raise ValueError("Message must be a string")

        if not message.strip():
            raise ValueError("Message cannot be empty")

        return await self.circuit_breaker.call_async(
            self._send_sms_internal, phone_number, message
        )

    async def _send_sms_internal(self, phone_number: str, message: str) -> str:
        """Execute SMS sending."""
        url = f"{self.base_url}/sms/send"
        payload = {"phone_number": phone_number, "message": message}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(
                    "Sending SMS message",
                    service="SMS Agent",
                    phone_number=phone_number,
                    url=url,
                    message_length=len(message),
                )

                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()

                # Extract message ID from response
                message_id = data.get("message_id") or data.get("id")
                if not message_id:
                    message_id = f"msg-{datetime.utcnow().timestamp()}"
                    logger.warning(
                        "No message ID in SMS Agent response, generating local ID",
                        service="SMS Agent",
                        phone_number=phone_number,
                        generated_id=message_id,
                    )

                logger.info(
                    "SMS sent successfully",
                    service="SMS Agent",
                    phone_number=phone_number,
                    message_id=message_id,
                )

                return message_id

        except httpx.TimeoutException as e:
            logger.error(
                "Timeout sending SMS",
                service="SMS Agent",
                phone_number=phone_number,
                timeout=self.timeout,
                error=str(e),
            )
            raise ServiceUnavailableError(
                "SMS Agent", f"Request timeout after {self.timeout} seconds"
            )

        except httpx.ConnectError as e:
            logger.error(
                "Connection error to SMS Agent",
                phone_number=phone_number,
                url=url,
                error=str(e),
            )
            raise ServiceUnavailableError("SMS Agent", f"Connection error: {str(e)}")

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error from SMS Agent",
                phone_number=phone_number,
                status_code=e.response.status_code,
                error=str(e),
            )
            if e.response.status_code >= 500:
                raise ServiceUnavailableError(
                    "SMS Agent", f"Server error: {e.response.status_code}"
                )
            else:
                raise  # Re-raise 4xx errors as-is

        except Exception as e:
            logger.error(
                "Unexpected error sending SMS",
                service="SMS Agent",
                phone_number=phone_number,
                error=str(e),
            )
            raise ServiceUnavailableError("SMS Agent", f"Unexpected error: {str(e)}")

    async def get_conversation_history(self, phone_number: str) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history from SMS Agent service.

        Args:
            phone_number: Phone number to fetch conversation history for

        Returns:
            List of conversation messages/entries

        Raises:
            ServiceUnavailableError: If service is unavailable or circuit is open
            httpx.HTTPError: For HTTP-related errors
            ValueError: If phone_number is invalid
        """
        self._validate_phone_number(phone_number)

        return await self.circuit_breaker.call_async(
            self._get_conversation_history_internal, phone_number
        )

    async def _get_conversation_history_internal(
        self, phone_number: str
    ) -> List[Dict[str, Any]]:
        """Execute conversation history retrieval."""
        url = f"{self.base_url}/conversations/{phone_number}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(
                    "Fetching conversation history",
                    service="SMS Agent",
                    phone_number=phone_number,
                    url=url,
                )

                response = await client.get(url)
                response.raise_for_status()

                data = response.json()

                # Ensure we return a list, even if service returns single object
                if isinstance(data, list):
                    conversation_history = data
                elif isinstance(data, dict):
                    # If service returns {"messages": [...]} or similar structure
                    if "messages" in data:
                        conversation_history = data["messages"]
                    elif "conversations" in data:
                        conversation_history = data["conversations"]
                    else:
                        conversation_history = [data]
                else:
                    conversation_history = []

                logger.info(
                    "Successfully retrieved conversation history",
                    service="SMS Agent",
                    phone_number=phone_number,
                    message_count=len(conversation_history),
                )

                return conversation_history

        except httpx.TimeoutException as e:
            logger.error(
                "Timeout retrieving conversation history",
                service="SMS Agent",
                phone_number=phone_number,
                timeout=self.timeout,
                error=str(e),
            )
            raise ServiceUnavailableError(
                "SMS Agent", f"Request timeout after {self.timeout} seconds"
            )

        except httpx.ConnectError as e:
            logger.error(
                "Connection error to SMS Agent",
                phone_number=phone_number,
                url=url,
                error=str(e),
            )
            raise ServiceUnavailableError("SMS Agent", f"Connection error: {str(e)}")

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error from SMS Agent",
                phone_number=phone_number,
                status_code=e.response.status_code,
                error=str(e),
            )
            if e.response.status_code >= 500:
                raise ServiceUnavailableError(
                    "SMS Agent", f"Server error: {e.response.status_code}"
                )
            else:
                raise  # Re-raise 4xx errors as-is

        except Exception as e:
            logger.error(
                "Unexpected error retrieving conversation history",
                service="SMS Agent",
                phone_number=phone_number,
                error=str(e),
            )
            raise ServiceUnavailableError("SMS Agent", f"Unexpected error: {str(e)}")

    async def health_check(self) -> bool:
        """
        Check if SMS Agent service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/health"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                is_healthy = response.status_code == 200

                logger.info(
                    "SMS Agent health check",
                    healthy=is_healthy,
                    status_code=response.status_code,
                )

                return is_healthy

        except Exception as e:
            logger.warning("SMS Agent health check failed", error=str(e))
            return False

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """
        Get current circuit breaker status.
        Returns:
            Circuit breaker status information
        """
        return self.service_client.get_circuit_status()

    async def close(self):
        """Close the service client."""
        await self.service_client.close()
