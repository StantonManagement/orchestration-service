"""
AI service for generating contextual responses using OpenAI API.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import openai
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import settings
from app.models.ai_response import AIResponse, AIResponseQueue
from app.core.exceptions import (
    AIServiceError,
    AIServiceTimeoutError,
    AIServiceRateLimitError,
)
from app.utils.confidence_scoring import ConfidenceScorer
from app.utils.payment_plan_extraction import PaymentPlanExtractor

logger = structlog.get_logger(__name__)


class AIService:
    """Service for generating AI responses using OpenAI API."""

    def __init__(self):
        self.client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key, timeout=settings.openai_timeout
        )
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature
        self.max_tokens = settings.openai_max_tokens
        self.confidence_scorer = ConfidenceScorer()
        self.payment_plan_extractor = PaymentPlanExtractor()
        self._request_timestamps = []  # For rate limiting

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, exp_base=2, max=10),
        retry=retry_if_exception_type((AIServiceTimeoutError, AIServiceRateLimitError)),
    )
    async def generate_response(
        self,
        tenant_context: Dict[str, Any],
        conversation_history: Optional[Dict[str, Any]] = None,
        message: str = "",
        language_preference: str = "en",
        correlation_id: Optional[str] = None,
    ) -> AIResponse:
        """
        Generate AI response for tenant communication.

        Args:
            tenant_context: Tenant payment and communication context
            conversation_history: Recent conversation history
            message: Original message from tenant
            language_preference: Tenant's preferred language
            correlation_id: Request correlation ID for logging

        Returns:
            AIResponse object with generated response and metadata

        Raises:
            AIServiceError: If AI generation fails
            AIServiceTimeoutError: If API call times out
            AIServiceRateLimitError: If rate limit is exceeded
        """
        correlation_id = correlation_id or f"ai_{datetime.utcnow().timestamp()}"

        try:
            # Check rate limit
            await self._check_rate_limit(correlation_id)

            # Generate system prompt
            system_prompt = self.generate_system_prompt(
                tenant_context, conversation_history, language_preference
            )

            # Prepare messages for OpenAI
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ]

            # Add conversation history if available
            if conversation_history and conversation_history.get("recent_messages"):
                for msg in conversation_history["recent_messages"][
                    -5:
                ]:  # Last 5 messages
                    messages.insert(
                        1,
                        {
                            "role": msg.get("sender", "user"),
                            "content": msg.get("text", ""),
                        },
                    )

            logger.info(
                "Generating AI response",
                correlation_id=correlation_id,
                tenant_id=tenant_context.get("tenant_id"),
                language=language_preference,
                model=self.model,
            )

            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            # Extract response content
            response_text = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens

            # Check for payment plan markers in AI response
            payment_plan_detected = self.detect_payment_plan_in_response(response_text)
            payment_plan_data = None

            if payment_plan_detected:
                payment_plan_data = self.extract_payment_plan_from_response(response_text)
                if payment_plan_data:
                    # Convert payment plan to dict for storage
                    payment_plan_data = {
                        "weekly_amount": float(payment_plan_data.weekly_amount) if payment_plan_data.weekly_amount else None,
                        "duration_weeks": payment_plan_data.duration_weeks,
                        "start_date": payment_plan_data.start_date.isoformat() if payment_plan_data.start_date else None,
                        "confidence_score": payment_plan_data.confidence_score,
                        "extracted_from": payment_plan_data.extracted_from.value,
                        "extraction_patterns": payment_plan_data.extraction_patterns
                    }

            # Format response for SMS
            formatted_response = self.format_response_for_sms(
                response_text, language_preference
            )

            # Calculate confidence score
            confidence_score = self.confidence_scorer.calculate_confidence(
                formatted_response,
                tenant_context,
                conversation_history,
                language_preference,
            )

            # Create AI response object
            ai_response = AIResponse(
                response_text=formatted_response,
                confidence_score=confidence_score,
                language_preference=language_preference,
                tokens_used=tokens_used,
                payment_plan_detected=payment_plan_detected,
                payment_plan_data=payment_plan_data,
                response_metadata={
                    "correlation_id": correlation_id,
                    "model": self.model,
                    "temperature": self.temperature,
                    "original_response": response_text,
                    "formatted_length": len(formatted_response),
                    "payment_plan_detected": payment_plan_detected,
                },
            )

            logger.info(
                "AI response generated successfully",
                correlation_id=correlation_id,
                confidence_score=float(confidence_score),
                tokens_used=tokens_used,
                response_length=len(formatted_response),
            )

            return ai_response

        except openai.RateLimitError as e:
            logger.error(
                "OpenAI rate limit exceeded",
                correlation_id=correlation_id,
                error=str(e),
            )
            raise AIServiceRateLimitError(f"Rate limit exceeded: {str(e)}")

        except openai.APITimeoutError as e:
            logger.error(
                "OpenAI API timeout", correlation_id=correlation_id, error=str(e)
            )
            raise AIServiceTimeoutError(f"API timeout: {str(e)}")

        except openai.APIError as e:
            logger.error(
                "OpenAI API error", correlation_id=correlation_id, error=str(e)
            )
            raise AIServiceError(f"API error: {str(e)}")

        except Exception as e:
            logger.error(
                "Unexpected error in AI response generation",
                correlation_id=correlation_id,
                error=str(e),
            )
            raise AIServiceError(f"Unexpected error: {str(e)}")

    def generate_system_prompt(
        self,
        tenant_context: Dict[str, Any],
        conversation_history: Optional[Dict[str, Any]] = None,
        language_preference: str = "en",
    ) -> str:
        """
        Generate system prompt for AI based on tenant context and conversation history.

        Args:
            tenant_context: Tenant payment and communication context
            conversation_history: Recent conversation history
            language_preference: Tenant's preferred language

        Returns:
            System prompt string
        """
        # Base prompt template
        base_prompt = f"""You are a helpful collections assistant responding to tenants via SMS. Your role is to:
1. Be empathetic and professional
2. Address their payment situation respectfully
3. Provide helpful options and information
4. Keep responses concise and SMS-friendly
5. Respond in {language_preference}"""

        # Add tenant-specific context
        if tenant_context:
            context_prompt = f"""
Tenant Context:
- Outstanding Balance: {tenant_context.get('outstanding_balance', 'N/A')}
- Payment History: {tenant_context.get('payment_history', 'No recent payments')}
- Language Preference: {tenant_context.get('language_preference', language_preference)}
- Communication Preference: {tenant_context.get('communication_preference', 'SMS')}
"""
            base_prompt += context_prompt

        # Add conversation context
        if conversation_history and conversation_history.get("recent_messages"):
            base_prompt += "\n\nRecent conversation context shows tenant has been discussing payment arrangements."

        # Add SMS-specific guidelines
        sms_guidelines = """
SMS Guidelines:
- Keep responses under 160 characters when possible
- Be clear and direct
- Include helpful contact information if needed
- Maintain professional and empathetic tone
- Avoid complex jargon
- Focus on solutions and options
"""

        base_prompt += sms_guidelines

        # Add language-specific instructions
        if language_preference != "en":
            language_instructions = f"""
Language Instructions:
- Respond primarily in {language_preference}
- Use simple, clear language appropriate for SMS
- Be culturally sensitive and appropriate
"""
            base_prompt += language_instructions

        return base_prompt

    def format_response_for_sms(
        self, response: str, language_preference: str = "en"
    ) -> str:
        """
        Format AI response for SMS delivery.

        Args:
            response: Original AI response
            language_preference: Tenant's preferred language

        Returns:
            SMS-formatted response
        """
        # Clean up response
        formatted = response.strip()

        # Remove excessive whitespace
        formatted = " ".join(formatted.split())

        # Check if response is too long for standard SMS
        if len(formatted) > 160:
            # Try to truncate at sentence boundary
            sentences = formatted.split(". ")
            truncated = ""
            for sentence in sentences:
                if len(truncated + sentence + ". ") <= 160:
                    truncated += sentence + ". "
                else:
                    break

            if not truncated:
                # No sentence fits, truncate at word boundary
                words = formatted.split()
                truncated = ""
                for word in words:
                    if len(truncated + word + " ") <= 156:  # Leave room for "..."
                        truncated += word + " "
                    else:
                        break
                truncated = truncated.strip() + "..."

            formatted = truncated.strip()

            # Add contact info for truncated responses, ensuring final length stays under 160
            contact_info = ""
            if language_preference == "es":
                contact_info = " Llame para más info."
            elif language_preference == "fr":
                contact_info = " Appelez pour plus d'infos."
            else:
                contact_info = " Call for more info."

            # Truncate further if contact info would exceed limit
            if len(formatted) + len(contact_info) > 160:
                # Remove characters to make room for contact info + ellipsis
                max_text_length = (
                    160 - len(contact_info) - 3
                )  # Extra space for ellipsis
                if max_text_length > 0:
                    formatted = formatted[:max_text_length].rstrip() + "..."
                else:
                    # Just use contact info if text is too long
                    formatted = ""

            formatted += contact_info

        return formatted

    def detect_payment_plan_in_response(self, response_text: str) -> Dict[str, Any]:
        """
        Detect payment plan information in AI response.

        Args:
            response_text: The AI-generated response text to analyze

        Returns:
            Dictionary with payment plan detection results
        """
        try:
            # Extract payment plan using our utility
            extracted_plan = self.payment_plan_extractor.extract_payment_plan(response_text)

            # Check for structured markers
            has_payment_plan_marker = any([
                "PAYMENT_PLAN:" in response_text.upper(),
                "payment plan" in response_text.lower(),
                "$" in response_text and any(word in response_text.lower()
                                          for word in ["week", "weekly", "per week"]),
            ])

            detection_result = {
                "payment_plan_detected": has_payment_plan_marker or extracted_plan.is_complete(),
                "extracted_plan": extracted_plan.to_dict() if extracted_plan.is_complete() else None,
                "has_structured_marker": has_payment_plan_marker,
                "confidence_level": extracted_plan.confidence.value if extracted_plan else "low"
            }

            if detection_result["payment_plan_detected"]:
                logger.info(
                    "Payment plan detected in AI response",
                    confidence=detection_result["confidence_level"],
                    has_structured_marker=detection_result["has_structured_marker"],
                    is_complete=extracted_plan.is_complete() if extracted_plan else False
                )

            return detection_result

        except Exception as e:
            logger.error(
                "Error detecting payment plan in AI response",
                error=str(e)
            )
            return {
                "payment_plan_detected": False,
                "extracted_plan": None,
                "has_structured_marker": False,
                "confidence_level": "low",
                "error": str(e)
            }

    async def _check_rate_limit(self, correlation_id: str) -> None:
        """Check if we're within rate limits."""
        now = datetime.utcnow()

        # Remove old timestamps (older than 1 minute)
        self._request_timestamps = [
            ts for ts in self._request_timestamps if (now - ts).total_seconds() < 60
        ]

        # Check current rate
        current_rate = len(self._request_timestamps)
        max_rate = settings.openai_rate_limit

        if current_rate >= max_rate:
            logger.warning(
                "Rate limit reached, waiting",
                correlation_id=correlation_id,
                current_rate=current_rate,
                max_rate=max_rate,
            )
            # Wait for a bit before allowing more requests
            await asyncio.sleep(1.0)

        # Add current timestamp
        self._request_timestamps.append(now)

    async def process_queue_item(self, queue_item: AIResponseQueue) -> AIResponse:
        """
        Process an item from the AI response queue.

        Args:
            queue_item: Queue item containing all necessary context

        Returns:
            Generated AI response
        """
        correlation_id = (
            f"queue_{queue_item.id or 'unknown'}_{datetime.utcnow().timestamp()}"
        )

        logger.info(
            "Processing AI queue item",
            correlation_id=correlation_id,
            tenant_id=queue_item.tenant_id,
            phone_number=queue_item.phone_number,
        )

        try:
            response = await self.generate_response(
                tenant_context=queue_item.tenant_context,
                conversation_history=queue_item.conversation_history,
                message=queue_item.original_message,
                language_preference=queue_item.language_preference,
                correlation_id=correlation_id,
            )

            # Update queue item with processed timestamp
            queue_item.processed_at = datetime.utcnow()

            return response

        except Exception as e:
            logger.error(
                "Failed to process queue item",
                correlation_id=correlation_id,
                tenant_id=queue_item.tenant_id,
                error=str(e),
            )
            raise

    def detect_payment_plan_in_response(self, response_text: str) -> bool:
        """
        Detect if AI response contains payment plan information.

        Args:
            response_text: AI-generated response text

        Returns:
            True if payment plan markers are detected
        """
        try:
            # Use the payment plan extractor to check for payment plans
            payment_plan = self.payment_plan_extractor.extract_from_ai_response(response_text)
            return payment_plan is not None

        except Exception as e:
            logger.error(f"Error detecting payment plan in response: {str(e)}")
            return False

    def extract_payment_plan_from_response(self, response_text: str):
        """
        Extract payment plan from AI response.

        Args:
            response_text: AI-generated response text

        Returns:
            Extracted payment plan or None
        """
        try:
            return self.payment_plan_extractor.extract_from_ai_response(response_text)
        except Exception as e:
            logger.error(f"Error extracting payment plan from response: {str(e)}")
            return None
