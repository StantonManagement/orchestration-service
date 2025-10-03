"""
Tests for confidence scoring utilities.
"""
import pytest
from decimal import Decimal

from app.utils.confidence_scoring import ConfidenceScorer


class TestConfidenceScorerUnit:
    """Unit tests for ConfidenceScorer functionality."""

    @pytest.fixture
    def scorer(self):
        """Create ConfidenceScorer instance for testing."""
        return ConfidenceScorer()

    def test_scorer_initialization(self, scorer):
        """Test scorer initialization with correct weights."""
        assert scorer.context_relevance_weight == Decimal("0.40")
        assert scorer.conversation_continuity_weight == Decimal("0.25")
        assert scorer.language_appropriateness_weight == Decimal("0.15")
        assert scorer.business_rule_compliance_weight == Decimal("0.20")

        # Verify weights sum to 1.0
        total_weight = (
            scorer.context_relevance_weight
            + scorer.conversation_continuity_weight
            + scorer.language_appropriateness_weight
            + scorer.business_rule_compliance_weight
        )
        assert total_weight == Decimal("1.0")

    def test_calculate_confidence_bounds(self, scorer):
        """Test confidence scores are always within bounds."""
        # Test with various inputs
        test_cases = [
            ("", {}, None, "en"),
            (
                "Valid response",
                {"has_outstanding_balance": True},
                {"recent_messages": []},
                "en",
            ),
            (
                "Another response",
                {},
                {"recent_messages": [{"sender": "user", "text": "test"}]},
                "es",
            ),
        ]

        for response, context, history, lang in test_cases:
            score = scorer.calculate_confidence(response, context, history, lang)
            assert isinstance(score, Decimal)
            assert Decimal("0.0") <= score <= Decimal("1.0")

    def test_context_relevance_payment_scoring(self, scorer):
        """Test context relevance scoring with payment-related terms."""
        base_context = {"has_outstanding_balance": True}

        # Test with payment terms
        payment_response = "You can make a payment for your balance due."
        payment_score = scorer._calculate_context_relevance(
            payment_response, base_context
        )

        # Test without payment terms
        generic_response = "This is a generic response."
        generic_score = scorer._calculate_context_relevance(
            generic_response, base_context
        )

        assert payment_score > generic_score

    def test_context_relevance_language_mention(self, scorer):
        """Test context relevance scoring with language preference mention."""
        spanish_context = {
            "language_preference": "spanish",
            "has_outstanding_balance": False,
        }

        # Test with Spanish language mention
        spanish_response = "Le puedo ayudar en español."
        spanish_score = scorer._calculate_context_relevance(
            spanish_response, spanish_context
        )

        # Test without language mention
        english_response = "I can help you."
        english_score = scorer._calculate_context_relevance(
            english_response, spanish_context
        )

        assert spanish_score > english_score

    def test_conversation_continuity_no_history(self, scorer):
        """Test conversation continuity with no history."""
        response = "This is a response."
        score = scorer._calculate_conversation_continuity(response, None)

        # Should return default score for no history
        assert score == Decimal("0.7")

    def test_conversation_continuity_empty_history(self, scorer):
        """Test conversation continuity with empty history."""
        response = "This is a response."
        score = scorer._calculate_conversation_continuity(
            response, {"recent_messages": []}
        )

        # Should return default score for empty history
        assert score == Decimal("0.7")

    def test_conversation_continuity_with_similarity(self, scorer):
        """Test conversation continuity with semantic similarity."""
        response = "Yes, I can help you with payment assistance."
        history = {
            "recent_messages": [
                {"sender": "user", "text": "Can you help me with payment assistance?"},
                {"sender": "assistant", "text": "I understand you need help."},
            ]
        }

        score = scorer._calculate_conversation_continuity(response, history)

        # Should detect similarity with previous messages
        assert score > Decimal("0.5")

    def test_language_appropriateness_english(self, scorer):
        """Test language appropriateness for English."""
        english_response = "This is an English response."
        score = scorer._calculate_language_appropriateness(english_response, "en")

        assert score == Decimal("1.0")

    def test_language_appropriateness_spanish_detected(self, scorer):
        """Test language appropriateness for Spanish with Spanish text."""
        spanish_response = "Le puedo ayudar en español."
        score = scorer._calculate_language_appropriateness(spanish_response, "es")

        assert score == Decimal("1.0")

    def test_language_appropriateness_spanish_not_detected(self, scorer):
        """Test language appropriateness for Spanish with English text."""
        english_response = "This is an English response."
        score = scorer._calculate_language_appropriateness(english_response, "es")

        assert score == Decimal("0.3")

    def test_language_appropriateness_french_detected(self, scorer):
        """Test language appropriateness for French with French text."""
        french_response = "Je peux vous aider en français avec des accents comme éàêù."
        score = scorer._calculate_language_appropriateness(french_response, "fr")

        assert score == Decimal("1.0")

    def test_business_rule_compliance_professional_tone(self, scorer):
        """Test business rule compliance with professional tone."""
        professional_response = (
            "Please let me know how I can help you. Thank you for your patience."
        )
        score = scorer._calculate_business_rule_compliance(professional_response, {})

        # Should be high for professional tone
        assert score >= Decimal("0.7")

    def test_business_rule_compliance_prohibited_content(self, scorer):
        """Test business rule compliance with prohibited content."""
        prohibited_responses = [
            "You should contact a lawyer about this.",
            "I hate this situation.",
            "You should sue them.",
            "This is illegal and fraudulent.",
        ]

        for response in prohibited_responses:
            score = scorer._calculate_business_rule_compliance(response, {})
            # Should be reduced for prohibited content
            assert score <= Decimal("0.4")

    def test_business_rule_compliance_sms_length(self, scorer):
        """Test business rule compliance with SMS length considerations."""
        short_response = "Short response."
        long_response = (
            "This is a very long response that exceeds the standard SMS character limit and should have a slightly different score."
            * 2
        )

        short_score = scorer._calculate_business_rule_compliance(short_response, {})
        long_score = scorer._calculate_business_rule_compliance(long_response, {})

        # Short response should score slightly higher for SMS appropriateness
        assert short_score > long_score

    def test_semantic_similarity_high(self, scorer):
        """Test semantic similarity with high overlap."""
        text1 = "I need help with my payment arrangement"
        text2 = "Can you help me with my payment arrangement"

        result = scorer._has_semantic_similarity(text1, text2, threshold=0.3)

        assert result is True

    def test_semantic_similarity_low(self, scorer):
        """Test semantic similarity with low overlap."""
        text1 = "The weather is nice today"
        text2 = "I need payment assistance"

        result = scorer._has_semantic_similarity(text1, text2, threshold=0.3)

        assert result is False

    def test_semantic_similarity_edge_cases(self, scorer):
        """Test semantic similarity edge cases."""
        # Empty strings
        assert scorer._has_semantic_similarity("", "test") is False
        assert scorer._has_semantic_similarity("test", "") is False
        assert scorer._has_semantic_similarity("", "") is False

    def test_is_mostly_english_true(self, scorer):
        """Test English detection with mostly English text."""
        english_text = "This is mostly English text with some punctuation."
        result = scorer._is_mostly_english(english_text)

        assert result is True

    def test_is_mostly_english_false(self, scorer):
        """Test English detection with mostly non-English text."""
        # Use text with enough non-ASCII characters to fall below the threshold
        non_english_text = "ñáéíóúü¿¡çë" * 5  # Repeat to ensure below threshold
        result = scorer._is_mostly_english(non_english_text)

        assert result is False

    def test_is_mostly_english_mixed(self, scorer):
        """Test English detection with mixed language text."""
        mixed_text = "This is English mixed with español text."
        result = scorer._is_mostly_english(mixed_text)

        # Should still be mostly English
        assert result is True

    def test_is_mostly_english_edge_cases(self, scorer):
        """Test English detection edge cases."""
        # Empty string
        assert scorer._is_mostly_english("") is True

        # Single ASCII character
        assert scorer._is_mostly_english("a") is True

        # Single non-ASCII character
        assert scorer._is_mostly_english("ñ") is False

    def test_calculate_confidence_comprehensive_example(self, scorer):
        """Test confidence calculation with comprehensive example."""
        response = "I understand you need help with your payment. Please let me know your preferred payment arrangement."
        tenant_context = {
            "has_outstanding_balance": True,
            "language_preference": "en",
            "payment_history": ["2024-01-15: $200"],
        }
        conversation_history = {
            "recent_messages": [
                {"sender": "user", "text": "I need help with my payment"},
                {
                    "sender": "assistant",
                    "text": "I can help you explore payment options",
                },
            ]
        }

        score = scorer.calculate_confidence(
            response, tenant_context, conversation_history, "en"
        )

        # Should be a high confidence score for this good example
        assert Decimal("0.7") <= score <= Decimal("1.0")

        # Verify individual components are reasonable
        context_score = scorer._calculate_context_relevance(response, tenant_context)
        continuity_score = scorer._calculate_conversation_continuity(
            response, conversation_history
        )
        language_score = scorer._calculate_language_appropriateness(response, "en")
        compliance_score = scorer._calculate_business_rule_compliance(
            response, tenant_context
        )

        assert Decimal("0.0") <= context_score <= Decimal("1.0")
        assert Decimal("0.0") <= continuity_score <= Decimal("1.0")
        assert Decimal("0.0") <= language_score <= Decimal("1.0")
        assert Decimal("0.0") <= compliance_score <= Decimal("1.0")
