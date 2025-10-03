"""OpenAI integration service for AI response generation."""

import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import openai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.schemas import AIResponse

settings = get_settings()
logger = get_logger(__name__)


class PaymentPlanExtractor:
    """Extract payment plan information from messages."""

    PATTERNS = [
        r"pay\s+\$?(\d+)\s+(?:per|a|each)\s+week",
        r"\$?(\d+)\s+(?:weekly|a week|per week)",
        r"pay\s+\$?(\d+)\s+(?:over|in)\s+(\d+)\s+weeks?",
        r"\$?(\d+)\s+(?:for|over)\s+(\d+)\s+weeks?",
        r"(\$?\d+(?:\.\d{2})?)\s*(?:a|per)\s*week",
        r"(\$?\d+(?:\.\d{2})?)\s*\/\s*week",
    ]

    def __init__(self):
        self.max_weeks = settings.max_payment_weeks
        self.min_weekly = settings.min_weekly_payment

    def extract(self, message: str, ai_response: str) -> Optional[Dict[str, Any]]:
        """Extract payment plan from message or AI response."""

        # First check if AI response contains structured payment plan
        if "PAYMENT_PLAN:" in ai_response:
            return self._parse_structured_plan(ai_response)

        # Try to extract from tenant message
        for pattern in self.PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return self._build_plan_from_match(match, message)

        return None

    def _parse_structured_plan(self, ai_response: str) -> Optional[Dict[str, Any]]:
        """Parse structured payment plan from AI response."""
        try:
            plan_match = re.search(r"PAYMENT_PLAN:\s*weekly=([^,]+),\s*weeks=(\d+)", ai_response)
            if plan_match:
                weekly = float(plan_match.group(1).replace('$', ''))
                weeks = int(plan_match.group(2))

                start_match = re.search(r"start=([^,]+)", ai_response)
                start_date = start_match.group(1) if start_match else None

                return {
                    "weekly_amount": weekly,
                    "weeks": weeks,
                    "start_date": start_date,
                    "source": "ai_structured"
                }
        except (ValueError, AttributeError):
            pass

        return None

    def _build_plan_from_match(self, match: re.Match, message: str) -> Optional[Dict[str, Any]]:
        """Build payment plan from regex match."""
        try:
            groups = match.groups()

            if len(groups) >= 2:
                # Pattern captured both amount and weeks
                weekly = float(groups[0].replace('$', ''))
                weeks = int(groups[1])
            else:
                # Pattern only captured amount, infer duration from context
                weekly = float(groups[0].replace('$', ''))
                weeks = self._infer_weeks_from_context(message)

            if weeks and weekly:
                return {
                    "weekly_amount": weekly,
                    "weeks": weeks,
                    "start_date": self._calculate_start_date(),
                    "source": "pattern_match"
                }
        except (ValueError, AttributeError):
            pass

        return None

    def _infer_weeks_from_context(self, message: str) -> Optional[int]:
        """Infer payment duration from message context."""
        # Simple heuristics for duration inference
        message_lower = message.lower()

        if any(word in message_lower for word in ["week", "weekly"]):
            return None  # Duration not specified, leave as None
        elif any(word in message_lower for word in ["month", "monthly"]):
            return 4  # Assume 1 month = 4 weeks
        elif any(word in message_lower for word in ["couple weeks", "2 weeks"]):
            return 2
        elif any(word in message_lower for word in ["few weeks"]):
            return 3

        return None

    def _calculate_start_date(self) -> str:
        """Calculate suggested payment plan start date."""
        # Default to next Friday
        today = datetime.now()
        days_until_friday = (4 - today.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 7  # Next Friday if today is Friday

        start_date = today + timedelta(days=days_until_friday)
        return start_date.strftime("%Y-%m-%d")

    def validate_plan(self, plan: Dict[str, Any], tenant_context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payment plan against business rules."""
        issues = []
        weekly = plan.get("weekly_amount", 0)
        weeks = plan.get("weeks", 0)

        # Validate minimum weekly payment
        if weekly < self.min_weekly:
            issues.append(f"Payment too low: ${weekly}/week (minimum: ${self.min_weekly})")

        # Validate maximum duration
        if weeks > self.max_weeks:
            issues.append(f"Duration too long: {weeks} weeks (maximum: {self.max_weeks})")

        # Validate coverage if tenant amount is available
        tenant_portion = tenant_context.get("tenant_portion")
        if tenant_portion:
            try:
                amount_owed = float(str(tenant_portion).replace('$', ''))
                total_paid = weekly * weeks
                coverage_ratio = total_paid / amount_owed

                if coverage_ratio < 0.9:
                    issues.append(f"Plan covers only {coverage_ratio:.1%} of debt (${total_paid} vs ${amount_owed})")
            except (ValueError, TypeError):
                pass

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "auto_approvable": len(issues) == 0 and weeks <= 4
        }


class EscalationDetector:
    """Detect escalation triggers in messages."""

    HOSTILE_TRIGGERS = [
        "lawyer", "attorney", "sue", "suing", "legal action", "court",
        "complaint", "better business bureau", "bbb", "report you"
    ]

    DISPUTE_TRIGGERS = [
        "wrong amount", "don't owe", "not mine", "already paid",
        "dispute", "incorrect", "error", "mistake"
    ]

    LEGAL_TRIGGERS = HOSTILE_TRIGGERS + [
        "legal rights", "consumer protection", "regulation", "compliance"
    ]

    def __init__(self):
        self.escalation_hours = settings.escalation_hours

    def detect_triggers(self, message: str, ai_response: str) -> List[str]:
        """Detect escalation triggers in messages."""
        triggers = []
        message_lower = message.lower()

        # Check for hostile language
        for trigger in self.HOSTILE_TRIGGERS:
            if trigger in message_lower:
                triggers.append(f"hostile_language: {trigger}")
                break

        # Check for payment disputes
        for trigger in self.DISPUTE_TRIGGERS:
            if trigger in message_lower:
                triggers.append(f"payment_dispute: {trigger}")
                break

        # Check for legal threats
        for trigger in self.LEGAL_TRIGGERS:
            if trigger in message_lower:
                triggers.append(f"legal_threat: {trigger}")
                break

        # Check for unrealistic proposals
        if self._detect_unrealistic_proposal(message, ai_response):
            triggers.append("unrealistic_proposal")

        return triggers

    def _detect_unrealistic_proposal(self, message: str, ai_response: str) -> bool:
        """Detect unrealistic payment proposals."""
        # Look for extremely low payments or very long durations
        extremely_low = re.search(r"\$?[1-9]\s*(?:per|a|each)\s+week", message.lower())
        very_long = re.search(r"(\d{2,})\s+weeks?", message.lower())

        return bool(extremely_low or very_long)

    def check_timeout_escalation(self, last_message_at: datetime) -> bool:
        """Check if conversation should escalate due to timeout."""
        if not last_message_at:
            return False

        time_since_last = datetime.utcnow() - last_message_at
        return time_since_last.total_seconds() > (self.escalation_hours * 3600)


class OpenAIService:
    """Service for OpenAI API integration."""

    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature
        self.max_tokens = settings.openai_max_tokens
        self.payment_extractor = PaymentPlanExtractor()
        self.escalation_detector = EscalationDetector()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_response(
        self,
        tenant_context: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        current_message: str,
        language: str = "english"
    ) -> AIResponse:
        """Generate AI response for tenant message."""
        start_time = time.time()

        try:
            system_prompt = self._build_system_prompt(tenant_context, language)
            messages = self._format_conversation(conversation_history)
            messages.append({"role": "user", "content": current_message})

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            response_text = completion.choices[0].message.content
            processing_time = int((time.time() - start_time) * 1000)

            # Calculate confidence score
            confidence = self._calculate_confidence(response_text, tenant_context)

            # Detect payment plans
            payment_plan = self.payment_extractor.extract(current_message, response_text)
            if payment_plan:
                validation = self.payment_extractor.validate_plan(payment_plan, tenant_context)
                payment_plan["validation"] = validation

            # Detect escalation triggers
            escalation_triggers = self.escalation_detector.detect_triggers(
                current_message, response_text
            )

            return AIResponse(
                content=response_text,
                confidence=confidence,
                language=language,
                model_used=self.model,
                processing_time_ms=processing_time,
                payment_plan_detected=payment_plan,
                escalation_triggers=escalation_triggers
            )

        except Exception as e:
            logger.error("Failed to generate AI response", error=str(e))
            raise

    def _build_system_prompt(self, tenant: Dict[str, Any], language: str) -> str:
        """Build system prompt with tenant context."""
        tenant_name = tenant.get("tenant_name", "Tenant")
        amount_owed = tenant.get("amount_owed", "unknown")
        tenant_portion = tenant.get("tenant_portion", "unknown")
        days_late = tenant.get("days_late", "unknown")
        reliability_score = tenant.get("payment_reliability_score", "unknown")
        failed_plans = tenant.get("failed_payment_plans", "unknown")

        suggested_payment = self._calculate_suggested_payment(tenant_portion)

        return f"""You are a professional collections assistant for Stanton Management.

TENANT CONTEXT:
- Name: {tenant_name}
- Amount Owed: ${amount_owed} (tenant portion: ${tenant_portion})
- Days Late: {days_late}
- Payment Reliability: {reliability_score}/10
- Failed Plans: {failed_plans}
- Language: {language}

PAYMENT PLAN RULES:
- Maximum {settings.max_payment_weeks} weeks duration
- Minimum ${settings.min_weekly_payment}/week payment
- For tenant portion ${tenant_portion}, suggest ${suggested_payment}/week

RESPONSE REQUIREMENTS:
1. Be professional but empathetic
2. Respond in {language}
3. Focus on payment plan negotiation
4. Keep responses under 160 characters (SMS limit)
5. Include specific amounts and timeframes

ESCALATION TRIGGERS (start response with "ESCALATE:"):
- Threats or hostile language
- Unrealistic proposals (>{settings.max_payment_weeks} weeks, <${settings.min_weekly_payment}/week)
- Disputes about amount owed
- Legal threats
- Request for supervisor

If tenant proposes payment plan, include in response:
PAYMENT_PLAN: weekly={{amount}}, weeks={{duration}}, start={{date}}

Current conversation:
{self._format_conversation_history(conversation_history)}

Tenant's message: {{current_message}}"""

    def _format_conversation(self, history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Format conversation history for OpenAI."""
        messages = []

        for msg in history[-10:]:  # Last 10 messages
            role = "user" if msg.get("direction") == "inbound" else "assistant"
            content = msg.get("message_content", msg.get("content", ""))

            if content:
                messages.append({"role": role, "content": content})

        return messages

    def _format_conversation_history(self, history: List[Dict[str, Any]]) -> str:
        """Format conversation history as text for prompt."""
        formatted = []

        for msg in history[-5:]:  # Last 5 messages for context
            direction = "→" if msg.get("direction") == "inbound" else "←"
            content = msg.get("message_content", msg.get("content", ""))
            timestamp = msg.get("created_at", "")

            formatted.append(f"{direction} {content}")

        return "\n".join(formatted) if formatted else "No previous messages"

    def _calculate_confidence(self, response: str, tenant_context: Dict[str, Any]) -> float:
        """Calculate confidence score for AI response."""
        confidence = 0.5  # Base confidence

        # Increase confidence for well-structured responses
        if len(response) > 10 and len(response) < 160:
            confidence += 0.1

        # Increase confidence if response includes specific amounts
        if re.search(r"\$\d+(?:\.\d{2})?", response):
            confidence += 0.15

        # Increase confidence if response includes timeframes
        if re.search(r"\d+\s*(?:week|day|month)", response):
            confidence += 0.1

        # Decrease confidence for escalation triggers
        if response.startswith("ESCALATE:"):
            confidence -= 0.3

        # Adjust based on tenant payment reliability
        reliability = tenant_context.get("payment_reliability_score", 5)
        if reliability >= 8:
            confidence += 0.1
        elif reliability <= 3:
            confidence -= 0.1

        return max(0.0, min(1.0, confidence))

    def _calculate_suggested_payment(self, tenant_portion: str) -> str:
        """Calculate suggested weekly payment amount."""
        try:
            amount = float(str(tenant_portion).replace('$', ''))
            # Suggest 25% of tenant portion per week over 4 weeks
            suggested = amount * 0.25
            return f"{suggested:.0f}"
        except (ValueError, TypeError):
            return "25"  # Default suggestion