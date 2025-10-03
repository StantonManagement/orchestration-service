"""
Tests for escalation trigger detection utilities.

Comprehensive test coverage for Story 2.2 AC1 and AC2 requirements.
"""

import pytest
from app.utils.escalation_triggers import (
    EscalationDetector,
    EscalationTrigger,
    EscalationReason
)


class TestEscalationDetector:
    """Test cases for EscalationDetector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = EscalationDetector()

    def test_detect_anger_triggers(self):
        """Test detection of anger-related escalation triggers."""
        message = "I am furious with this service and want to speak to your supervisor!"
        triggers = self.detector.detect_triggers(message)

        assert len(triggers) >= 2
        anger_triggers = [t for t in triggers if t.reason == EscalationReason.ANGER]
        assert len(anger_triggers) >= 2

        # Check for high confidence triggers
        high_confidence = [t for t in anger_triggers if t.confidence >= 0.7]
        assert len(high_confidence) >= 1

    def test_detect_legal_triggers(self):
        """Test detection of legal-related escalation triggers."""
        message = "I'm going to contact my lawyer about this and may file a CFPB complaint."
        triggers = self.detector.detect_triggers(message)

        assert len(triggers) >= 2
        legal_triggers = [t for t in triggers if t.reason == EscalationReason.LEGAL_REQUEST]
        assert len(legal_triggers) >= 2

        # Legal triggers should have high confidence
        high_confidence_legal = [t for t in legal_triggers if t.confidence >= 0.8]
        assert len(high_confidence_legal) >= 1

    def test_detect_complaint_triggers(self):
        """Test detection of formal complaint triggers."""
        message = "I want to file a formal complaint and get written confirmation of this issue."
        triggers = self.detector.detect_triggers(message)

        complaint_triggers = [t for t in triggers if t.reason == EscalationReason.COMPLAINT]
        assert len(complaint_triggers) >= 2

    def test_detect_confusion_triggers(self):
        """Test detection of confusion-related triggers."""
        message = "I don't understand this at all, can you explain this in plain English?"
        triggers = self.detector.detect_triggers(message)

        confusion_triggers = [t for t in triggers if t.reason == EscalationReason.CONFUSION]
        assert len(confusion_triggers) >= 2

    def test_detect_dissatisfaction_triggers(self):
        """Test detection of general dissatisfaction triggers."""
        message = "This service is completely unacceptable and ridiculous. I'm done with this company."
        triggers = self.detector.detect_triggers(message)

        dissatisfaction_triggers = [t for t in triggers if t.reason == EscalationReason.DISSATISFACTION]
        assert len(dissatisfaction_triggers) >= 2

    def test_no_triggers_in_normal_message(self):
        """Test that normal messages don't trigger escalation."""
        message = "Thank you for your help. I understand the payment plan options now."
        triggers = self.detector.detect_triggers(message)

        # Should have minimal or no triggers
        assert len(triggers) <= 1
        if triggers:
            assert all(t.confidence < 0.5 for t in triggers)

    def test_should_escalate_with_anger(self):
        """Test escalation decision with anger triggers."""
        triggers = [
            EscalationTrigger(
                reason=EscalationReason.ANGER,
                confidence=0.8,
                matched_text="furious",
                pattern_type="keyword"
            )
        ]

        assert self.detector.should_escalate(triggers) is True

    def test_should_escalate_with_legal(self):
        """Test escalation decision with legal triggers (even low confidence)."""
        triggers = [
            EscalationTrigger(
                reason=EscalationReason.LEGAL_REQUEST,
                confidence=0.4,
                matched_text="lawyer",
                pattern_type="keyword"
            )
        ]

        # Should escalate for any legal trigger
        assert self.detector.should_escalate(triggers) is True

    def test_should_not_escalate_low_confidence(self):
        """Test no escalation with low confidence triggers."""
        triggers = [
            EscalationTrigger(
                reason=EscalationReason.DISSATISFACTION,
                confidence=0.3,
                matched_text="unhappy",
                pattern_type="keyword"
            )
        ]

        assert self.detector.should_escalate(triggers) is False

    def test_should_not_escalate_empty_list(self):
        """Test no escalation with empty trigger list."""
        assert self.detector.should_escalate([]) is False

    def test_get_primary_trigger(self):
        """Test getting the primary (highest confidence) trigger."""
        triggers = [
            EscalationTrigger(
                reason=EscalationReason.DISSATISFACTION,
                confidence=0.6,
                matched_text="unhappy",
                pattern_type="keyword"
            ),
            EscalationTrigger(
                reason=EscalationReason.ANGER,
                confidence=0.9,
                matched_text="furious",
                pattern_type="regex"
            ),
            EscalationTrigger(
                reason=EscalationReason.LEGAL_REQUEST,
                confidence=0.7,
                matched_text="lawyer",
                pattern_type="keyword"
            )
        ]

        primary = self.detector.get_primary_trigger(triggers)
        assert primary.confidence == 0.9
        assert primary.reason == EscalationReason.ANGER

    def test_get_primary_trigger_empty_list(self):
        """Test getting primary trigger from empty list."""
        assert self.detector.get_primary_trigger([]) is None

    def test_deduplicate_triggers(self):
        """Test trigger deduplication."""
        # Create duplicate triggers with different confidences
        trigger1 = EscalationTrigger(
            reason=EscalationReason.ANGER,
            confidence=0.6,
            matched_text="angry",
            pattern_type="keyword"
        )
        trigger2 = EscalationTrigger(
            reason=EscalationReason.ANGER,
            confidence=0.8,
            matched_text="ANGRY",  # Same text, different case
            pattern_type="regex"
        )

        # Simulate internal deduplication
        unique_triggers = self.detector._deduplicate_triggers([trigger1, trigger2])

        assert len(unique_triggers) == 1
        assert unique_triggers[0].confidence == 0.8  # Should keep higher confidence

    def test_pattern_confidence_calculation(self):
        """Test pattern confidence calculation logic."""
        import re

        # Test legal pattern (should have higher base confidence)
        legal_pattern = r'\b(?i:lawyer|attorney)\b'
        legal_match = re.search(legal_pattern, "I will call my lawyer")
        legal_confidence = self.detector._calculate_pattern_confidence(
            legal_match, legal_pattern, EscalationReason.LEGAL_REQUEST
        )

        # Test anger pattern
        anger_pattern = r'\b(?i:angry|mad)\b'
        anger_match = re.search(anger_pattern, "I am angry")
        anger_confidence = self.detector._calculate_pattern_confidence(
            anger_match, anger_pattern, EscalationReason.ANGER
        )

        # Legal should have higher confidence
        assert legal_confidence > anger_confidence

    def test_keyword_confidence_calculation(self):
        """Test keyword matching and confidence calculation."""
        text = "I want to speak to a supervisor and file a formal complaint"

        # Strong keywords should have higher confidence
        supervisor_triggers = self.detector._match_keywords(text, EscalationReason.ANGER)
        complaint_triggers = self.detector._match_keywords(text, EscalationReason.COMPLAINT)

        assert len(supervisor_triggers) > 0
        assert len(complaint_triggers) > 0

        # Supervisor should be high confidence (strong keyword)
        supervisor_confidence = [t.confidence for t in supervisor_triggers if 'supervisor' in t.matched_text.lower()]
        assert len(supervisor_confidence) > 0
        assert supervisor_confidence[0] >= 0.75

    def test_complex_message_multiple_triggers(self):
        """Test detection in complex message with multiple escalation types."""
        message = """
        I am absolutely furious with this service! This is completely unacceptable.
        I want to speak to your supervisor immediately and may need to contact my lawyer
        about filing a formal CFPB complaint. I don't understand how you can operate this way.
        """

        triggers = self.detector.detect_triggers(message)

        # Should detect multiple types of triggers
        reasons_detected = set(t.reason for t in triggers)
        assert EscalationReason.ANGER in reasons_detected
        assert EscalationReason.LEGAL_REQUEST in reasons_detected
        assert EscalationReason.COMPLAINT in reasons_detected
        assert EscalationReason.CONFUSION in reasons_detected

        # Should definitely escalate
        assert self.detector.should_escalate(triggers) is True

        # Should have multiple high-confidence triggers
        high_confidence_triggers = [t for t in triggers if t.confidence >= 0.7]
        assert len(high_confidence_triggers) >= 3

    def test_case_insensitive_matching(self):
        """Test that pattern matching is case insensitive."""
        message_variants = [
            "I am FURIOUS with this service",
            "I am furious with this service",
            "I am FuRiOuS with this service"
        ]

        for message in message_variants:
            triggers = self.detector.detect_triggers(message)
            anger_triggers = [t for t in triggers if t.reason == EscalationReason.ANGER]
            assert len(anger_triggers) >= 1

    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        # Empty message
        triggers = self.detector.detect_triggers("")
        assert len(triggers) == 0

        # None message (should handle gracefully)
        with pytest.raises(AttributeError):
            self.detector.detect_triggers(None)

        # Very long message
        long_message = "angry " * 1000
        triggers = self.detector.detect_triggers(long_message)
        assert len(triggers) > 0

        # Special characters
        special_message = "I'm angry!!! This is unacceptable???? Contact my lawyer ASAP!!!"
        triggers = self.detector.detect_triggers(special_message)
        assert len(triggers) >= 2