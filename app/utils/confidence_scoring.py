"""
Confidence scoring utilities for AI response evaluation.
"""
from decimal import Decimal
from typing import Dict, Any
import re
import structlog

logger = structlog.get_logger(__name__)


class ConfidenceScorer:
    """Calculates confidence scores for AI responses based on multiple factors."""

    def __init__(self):
        # Weights for different confidence factors
        self.context_relevance_weight = Decimal("0.40")
        self.conversation_continuity_weight = Decimal("0.25")
        self.language_appropriateness_weight = Decimal("0.15")
        self.business_rule_compliance_weight = Decimal("0.20")

    def calculate_confidence(
        self,
        response: str,
        tenant_context: Dict[str, Any],
        conversation_history: Dict[str, Any] = None,
        language_preference: str = "en",
    ) -> Decimal:
        """
        Calculate confidence score for AI response.

        Args:
            response: Generated AI response text
            tenant_context: Tenant payment and communication context
            conversation_history: Recent conversation history (optional)
            language_preference: Tenant's preferred language

        Returns:
            Confidence score between 0.0 and 1.0
        """
        try:
            # Calculate individual confidence factors
            context_score = self._calculate_context_relevance(response, tenant_context)
            continuity_score = self._calculate_conversation_continuity(
                response, conversation_history
            )
            language_score = self._calculate_language_appropriateness(
                response, language_preference
            )
            compliance_score = self._calculate_business_rule_compliance(
                response, tenant_context
            )

            # Weighted average
            total_score = (
                context_score * self.context_relevance_weight
                + continuity_score * self.conversation_continuity_weight
                + language_score * self.language_appropriateness_weight
                + compliance_score * self.business_rule_compliance_weight
            )

            # Ensure score is within bounds
            confidence_score = max(Decimal("0.0"), min(Decimal("1.0"), total_score))

            logger.info(
                "Confidence score calculated",
                confidence_score=float(confidence_score),
                context_score=float(context_score),
                continuity_score=float(continuity_score),
                language_score=float(language_score),
                compliance_score=float(compliance_score),
            )

            return confidence_score

        except Exception as e:
            logger.error("Error calculating confidence score", error=str(e))
            return Decimal("0.5")  # Default to medium confidence on error

    def _calculate_context_relevance(
        self, response: str, tenant_context: Dict[str, Any]
    ) -> Decimal:
        """Calculate how well response relates to tenant context."""
        score = Decimal("0.5")  # Base score

        if not tenant_context:
            return score

        response_lower = response.lower()

        # Check for payment-related terms if tenant has outstanding balance
        if tenant_context.get("has_outstanding_balance"):
            payment_terms = ["payment", "pay", "balance", "amount", "due", "bill"]
            if any(term in response_lower for term in payment_terms):
                score += Decimal("0.3")

        # Check for language preference mention
        if tenant_context.get("language_preference"):
            language_mapping = {
                "spanish": ["español", "habla español", "español"],
                "french": ["français", "parle français"],
                "chinese": ["中文", "华语"],
            }
            preferred_lang = tenant_context["language_preference"].lower()
            if preferred_lang in language_mapping:
                if any(
                    lang_term in response_lower
                    for lang_term in language_mapping[preferred_lang]
                ):
                    score += Decimal("0.2")

        return min(Decimal("1.0"), score)

    def _calculate_conversation_continuity(
        self, response: str, conversation_history: Dict[str, Any] = None
    ) -> Decimal:
        """Calculate response continuity with conversation history."""
        if not conversation_history or not conversation_history.get("recent_messages"):
            return Decimal("0.7")  # Good default for new conversations

        recent_messages = conversation_history["recent_messages"][
            -3:
        ]  # Last 3 messages
        if not recent_messages:
            return Decimal("0.7")

        score = Decimal("0.5")
        response_lower = response.lower()

        # Check for references to previous messages
        for message in recent_messages:
            message_text = message.get("text", "").lower()
            if self._has_semantic_similarity(response_lower, message_text):
                score += Decimal("0.2")

        return min(Decimal("1.0"), score)

    def _calculate_language_appropriateness(
        self, response: str, language_preference: str
    ) -> Decimal:
        """Calculate if response matches language preference."""
        language_patterns = {
            "es": [
                r"\b(el|la|los|las|un|una|de|en|que|por|para|con|sin|sobre|entre|hacia|hasta)\b"
            ],
            "fr": [
                r"\b(le|la|les|un|une|de|du|des|à|au|aux|pour|sur|avec|sans|par|dans)\b"
            ],
            "zh": [r"[\u4e00-\u9fff]"],
        }

        if language_preference == "en" or language_preference not in language_patterns:
            # Default to English check
            if self._is_mostly_english(response):
                return Decimal("1.0")
            else:
                return Decimal("0.3")

        # Check for target language patterns
        patterns = language_patterns.get(language_preference, [])
        for pattern in patterns:
            if re.search(pattern, response, re.IGNORECASE):
                return Decimal("1.0")

        return Decimal("0.3")

    def _calculate_business_rule_compliance(
        self, response: str, tenant_context: Dict[str, Any]
    ) -> Decimal:
        """Calculate compliance with business rules."""
        score = Decimal("0.5")
        response_lower = response.lower()

        # Check for prohibited content
        prohibited_patterns = [
            r"\b(lawyer|attorney|legal|sue|court|lawsuit)\b",
            r"\b(hate|threat|kill|harm|violence)\b",
            r"\b(illegal|fraud|scam)\b",
        ]

        for pattern in prohibited_patterns:
            if re.search(pattern, response_lower):
                score -= Decimal("0.3")

        # Check for professional tone
        professional_indicators = [
            "please",
            "thank",
            "understand",
            "help",
            "assist",
            "option",
        ]
        if any(indicator in response_lower for indicator in professional_indicators):
            score += Decimal("0.2")

        # Check length appropriateness for SMS
        if len(response) <= 160:  # Standard SMS
            score += Decimal("0.1")
        elif len(response) <= 1600:  # Extended SMS
            score += Decimal("0.05")

        return max(Decimal("0.0"), min(Decimal("1.0"), score))

    def _has_semantic_similarity(
        self, text1: str, text2: str, threshold: float = 0.3
    ) -> bool:
        """Simple semantic similarity check using word overlap."""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return False

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        similarity = len(intersection) / len(union)
        return similarity >= threshold

    def _is_mostly_english(self, text: str, threshold: float = 0.7) -> bool:
        """Check if text is mostly English using character analysis."""
        if not text:
            return True

        # Count English characters vs non-ASCII
        english_chars = sum(1 for c in text if ord(c) < 128)
        total_chars = len(text)

        return (english_chars / total_chars) >= threshold if total_chars > 0 else True
